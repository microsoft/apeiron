"""Regression tests for Dialog.openai message serialization.

Network- and credential-free: uses a fake llm-side message with a stub
raw_response. Guards the api_type comparison bug where an APITypes enum was
compared against a string value, causing llm-side (assistant / tool-call)
messages to be silently dropped from the serialized history -- which broke the
OpenAI tool-calling loop ("messages with role 'tool' must be a response to a
preceding message with 'tool_calls'").
"""
import tempfile
import types

import pytest


def _dialog(name="dlg"):
    llm = pytest.importorskip("sllm.llm")
    from sllm.log import NoLog
    return llm.Dialog(_messages=[], log_base=NoLog(name, {"log_dir": tempfile.gettempdir()}),
                      session_name=name), llm


def test_openai_serializes_llm_side_completion_message():
    dialog, llm = _dialog()
    from sllm.models import Message, FunctionCall
    from sllm.const import Roles

    sentinel_assistant_msg = {"role": "assistant", "tool_calls": ["<stub>"]}
    raw_response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=sentinel_assistant_msg)]
    )

    # A tool-call assistant message coming from the LLM side (COMPLETION api_type).
    msg = Message(
        role=Roles.TOOL_CALL,
        content="Tool calls: ...",
        creator="assistant",
        raw_response=raw_response,
        function_calls=[FunctionCall(id="tc1", name="f", arguments={})],
        extra={},  # defaults to COMPLETION api_type
    )
    dialog.append(msg)

    serialized = dialog.openai
    # The assistant tool-call message MUST be present (was dropped before the fix).
    assert sentinel_assistant_msg in serialized


def test_openai_serializes_user_then_tool_sequence():
    dialog, llm = _dialog("seq")
    from sllm.models import Message, FunctionCall
    from sllm.const import Roles

    dialog.append(Message(role=Roles.USER, content="hi", creator="user"))

    raw_response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message={"role": "assistant", "tool_calls": ["x"]})]
    )
    dialog.append(Message(
        role=Roles.TOOL_CALL, content="calls", creator="assistant",
        raw_response=raw_response,
        function_calls=[FunctionCall(id="tc1", name="f", arguments={})],
    ))
    dialog.append(Message(
        role=Roles.TOOL, content="42", creator="function",
        extra={"tool_call_id": "tc1"},
    ))

    serialized = dialog.openai
    roles = [m["role"] if isinstance(m, dict) else getattr(m, "role", None) for m in serialized]
    # user -> assistant(tool_calls) -> tool : the assistant must precede the tool msg.
    assert roles[0] == "user"
    assert roles[1] == "assistant"
    assert roles[2] == "tool"
