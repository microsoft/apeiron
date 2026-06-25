"""Unit tests for sllm.copilot_client and the llm.py COPILOT routing.

Credential- and network-free: the live Copilot SDK call is mocked. The live
end-to-end check lives in tests/smoke_live.py (run manually).
"""
import pytest

from sllm import copilot_client


def test_flatten_prompt_combines_roles():
    text = copilot_client.CopilotClaudeClient._flatten_prompt([
        {"role": "system", "content": "be terse"},
        {"role": "user", "content": "hi"},
    ])
    assert "[system]" in text
    assert "be terse" in text
    assert "user: hi" in text


def test_build_provider_config_none():
    assert copilot_client.build_provider_config(None) is None


def test_build_provider_config_unsupported_raises():
    with pytest.raises(ValueError):
        copilot_client.build_provider_config("bedrock")


def test_build_provider_config_anthropic_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        copilot_client.build_provider_config("anthropic")


def test_build_provider_config_anthropic_ok(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    cfg = copilot_client.build_provider_config("anthropic")
    assert cfg == {"type": "anthropic", "api_key": "sk-test"}


def test_event_helpers_handle_dict_and_nested():
    assert copilot_client._event_type({"type": "assistant.message"}) == "assistant.message"
    assert copilot_client._event_payload({"data": {"content": "x"}}) == {"content": "x"}
    assert copilot_client._event_payload({"content": "y"}) == {"content": "y"}


class _FakeDialog:
    openai = [{"role": "user", "content": "ping"}]


class _FakePrompt:
    parser = None
    functions = {}


def test_call_copilot_builds_assistant_message(monkeypatch):
    # Importing sllm.llm pulls in sllm.utils, which requires optional runtime
    # deps (e.g. filelock). Skip cleanly if the env doesn't have them.
    llm = pytest.importorskip("sllm.llm")
    from sllm.const import Roles

    # Mock the live SDK call.
    monkeypatch.setattr(
        copilot_client.CopilotClaudeClient,
        "complete",
        lambda self, messages, model, **kw: "pong",
    )

    # Skip LLMCaller.__init__ (which would build a real Azure client).
    caller = llm.LLMCaller.__new__(llm.LLMCaller)
    msg = caller._call_copilot(_FakeDialog(), _FakePrompt(), "claude-sonnet-4.5")

    assert msg.role == Roles.ASSISTANT
    assert msg.content == "pong"
    assert msg.function_calls == []
    assert msg.model == "claude-sonnet-4.5"


class _FakeInvocation:
    def __init__(self, arguments, tool_call_id="tc1"):
        self.arguments = arguments
        self.tool_call_id = tool_call_id
        self.tool_name = "multiply"


def test_build_tools_creates_tool_with_schema():
    spec = {
        "name": "multiply",
        "description": "Multiply two ints.",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
        "execute": lambda args, call_id: ("42", True),
    }
    tools = copilot_client.CopilotClaudeClient._build_tools([spec])
    assert len(tools) == 1
    tool = tools[0]
    assert tool.name == "multiply"
    assert tool.parameters["properties"] == spec["properties"]
    assert tool.parameters["required"] == ["a", "b"]
    assert tool.skip_permission is True


def test_build_tools_handler_executes_and_returns_success():
    seen = {}

    def _execute(args, call_id):
        seen["args"] = args
        seen["call_id"] = call_id
        return ("product is 437", True)

    spec = {"name": "multiply", "description": "d", "properties": {}, "required": [],
            "execute": _execute}
    tool = copilot_client.CopilotClaudeClient._build_tools([spec])[0]
    # The SDK calls handler(invocation) with a single positional arg.
    result = tool.handler(_FakeInvocation({"a": 23, "b": 19}))
    assert seen["args"] == {"a": 23, "b": 19}
    assert seen["call_id"] == "tc1"
    assert result.result_type == "success"
    assert result.text_result_for_llm == "product is 437"


def test_build_tools_handler_parses_string_arguments():
    captured = {}
    spec = {"name": "f", "description": "d", "properties": {}, "required": [],
            "execute": lambda args, cid: (captured.setdefault("args", args), "ok") and ("ok", True)}
    tool = copilot_client.CopilotClaudeClient._build_tools([spec])[0]
    tool.handler(_FakeInvocation('{"x": 1}'))
    assert captured["args"] == {"x": 1}


def test_build_tools_handler_reports_failure_on_exception():
    def _boom(args, call_id):
        raise ValueError("nope")
    spec = {"name": "f", "description": "d", "properties": {}, "required": [], "execute": _boom}
    tool = copilot_client.CopilotClaudeClient._build_tools([spec])[0]
    result = tool.handler(_FakeInvocation({}))
    assert result.result_type == "failure"
    assert "nope" in (result.error or "")


class _Func:
    """Minimal stand-in for sllm.models.Function for the tool-spec path."""
    def __init__(self, name, fn):
        self.name = name
        self.description = "d"
        self.properties = {"x": {"type": "integer"}}
        self.required = ["x"]
        self._fn = fn

    def __call__(self, function_call):
        function_call.result = self._fn(**function_call.arguments)
        function_call.result_str = str(function_call.result)
        return function_call


class _PromptWithFunc:
    parser = None

    def __init__(self, functions):
        self.functions = {f.name: f for f in functions}


def test_call_copilot_records_tool_calls(monkeypatch):
    """_call_copilot should expose tool_specs that execute the linked functions
    and record resolved calls on extra['copilot_tool_calls']."""
    llm = pytest.importorskip("sllm.llm")

    captured = {}

    def _fake_complete(self, messages, model, tool_specs=None, **kw):
        captured["tool_specs"] = tool_specs
        # Simulate the SDK invoking the registered tool.
        if tool_specs:
            text, ok = tool_specs[0]["execute"]({"x": 21}, "tc9")
            captured["tool_result"] = (text, ok)
        return "final answer"

    monkeypatch.setattr(copilot_client.CopilotClaudeClient, "complete", _fake_complete)

    fn = _Func("double", lambda x: x * 2)
    prompt = _PromptWithFunc([fn])
    caller = llm.LLMCaller.__new__(llm.LLMCaller)
    msg = caller._call_copilot(_FakeDialog(), prompt, "claude-sonnet-4.5")

    assert captured["tool_specs"] is not None
    assert captured["tool_specs"][0]["name"] == "double"
    assert captured["tool_result"] == ("42", True)
    assert msg.content == "final answer"
    assert msg.function_calls == []  # final answer, not an unresolved tool-call
    calls = msg.extra.get("copilot_tool_calls")
    assert calls and calls[0]["name"] == "double"
    assert calls[0]["result"] == "42"
    assert calls[0]["success"] is True
