"""Tool-calling with Claude via the GitHub Copilot SDK.

Registers two Apeiron ``Function``s (a calculator and a mock weather lookup) and
asks ``claude-sonnet-4.5`` (provider=COPILOT) a question that requires both. The
Copilot SDK runs the full tool loop internally: the model calls the tools, their
linked Python functions execute, and the model returns a final answer that uses
the results. The resolved calls are recorded on ``msg.extra['copilot_tool_calls']``.

Run:
    python examples/tool_calling.py
    python examples/tool_calling.py --question "What is 8 * 47?"

Requires a populated .env (AZURE_OPENAI_ENDPOINT) plus the GitHub Copilot CLI +
copilot SDK on PATH for the Copilot/Claude call.
"""
import argparse
import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_ROOT, ".env"))
except Exception:
    pass

from sllm.models import Function
from sllm.log import NoLog
from sllm.llm import LLMCaller, Dialog, Prompt
from sllm.const import Roles


def multiply(a, b):
    """Real Python implementation behind the 'multiply' tool."""
    return a * b


def get_weather(city):
    """Mock weather lookup behind the 'get_weather' tool."""
    return f"The weather in {city} is 21C and sunny."


def _build_prompt() -> Prompt:
    mult = Function(
        name="multiply",
        description="Multiply two integers and return their product.",
        properties={
            "a": {"type": "integer", "description": "first operand"},
            "b": {"type": "integer", "description": "second operand"},
        },
        required=["a", "b"],
    )
    mult.link_function(multiply)

    weather = Function(
        name="get_weather",
        description="Get the current weather for a given city.",
        properties={"city": {"type": "string", "description": "city name"}},
        required=["city"],
    )
    weather.link_function(get_weather)

    return Prompt(
        path="tool_calling_demo",
        prompt="(messages carry the question)",
        _functions=[mult, weather],
        md_tags=["answer"],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Claude-via-Copilot tool-calling demo")
    ap.add_argument(
        "--question",
        default="What is 23 multiplied by 19, and what's the weather in Paris? "
                "Use the tools, then give both facts in the answer block.",
    )
    ap.add_argument("--model", default="claude-sonnet-4.5")
    args = ap.parse_args()

    prompt = _build_prompt()
    caller = LLMCaller(config={"random_seed": 7})

    dialog = Dialog(
        _messages=[],
        log_base=NoLog("tool_calling", {"log_dir": tempfile.gettempdir()}),
        session_name="tool_calling",
    )
    dialog.send_message(
        "You are a precise assistant. You MUST use the provided tools to compute "
        "or look up values rather than guessing. Put the final answer inside a "
        "```answer ... ``` block.",
        role=Roles.SYSTEM, creator="system",
    )
    dialog.send_message(args.question, role=Roles.USER, creator="user")

    print(f"Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
    print(f"Model: {args.model} (provider=COPILOT)")
    print(f"Question: {args.question}\n")

    msg = caller.call(dialog, prompt, model=args.model)

    print("=== final answer ===")
    print(msg.content)

    tool_calls = msg.extra.get("copilot_tool_calls") or []
    print(f"\n=== tools invoked by the model ({len(tool_calls)}) ===")
    for tc in tool_calls:
        status = "ok" if tc["success"] else f"FAILED: {tc['error']}"
        print(f"  - {tc['name']}({tc['arguments']}) -> {status}")

    blocks = (msg.parsed or {}).get("md_tags", {}).get("answer")
    if blocks:
        print("\n=== parsed answer block ===")
        print(blocks[0].strip())

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
