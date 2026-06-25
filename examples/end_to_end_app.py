"""End-to-end Apeiron app: a multi-tool "concierge" agent.

A complete, runnable application built on the toolkit's high-level ``Agent``,
which gives ONE unified API across providers:

  * Auth      - Azure / Copilot via cached browser / az-login (no API key).
  * Agent     - sllm.llm.Agent runs the tool-calling loop. For OpenAI it drives
                the loop externally (call -> execute tool -> feed back -> repeat);
                for Claude-via-Copilot the SDK resolves tools internally and the
                Agent gets the final answer in one step. Same code either way.
  * Tools     - three registered Apeiron Functions the model can call:
                  - calculate(expression): safe arithmetic (ast-based, no eval)
                  - get_weather(city): mock lookup
                  - word_count(text): utility
  * Parsing   - a Prompt extracts a fenced ```answer``` block.
  * Reporting - prints, per task, the answer + which tools were invoked.

Run:
    python examples/end_to_end_app.py
    python examples/end_to_end_app.py --compare            # also run gpt-4.1
    python examples/end_to_end_app.py --ask "What is 144 / 12?"
"""
import argparse
import ast
import operator
import os
import sys
import tempfile
from typing import List, Optional, Tuple

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
from sllm.llm import LLMCaller, Agent, Prompt


# --------------------------------------------------------------------------- #
# Tool implementations (the real Python behind the model's tool calls)
# --------------------------------------------------------------------------- #
_ALLOWED_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("unsupported expression")


def calculate(expression):
    """Safely evaluate a basic arithmetic expression (no eval, ast-only)."""
    return _safe_eval(ast.parse(expression, mode="eval").body)


def get_weather(city):
    """Mock weather lookup."""
    return f"The weather in {city} is 21C and sunny."


def word_count(text):
    """Count words in a string."""
    return len(text.split())


def _build_functions() -> List[Function]:
    calc = Function(
        name="calculate",
        description="Evaluate a basic arithmetic expression, e.g. '23 * 19' or '144 / 12'.",
        properties={"expression": {"type": "string", "description": "arithmetic expression"}},
        required=["expression"],
    )
    calc.link_function(calculate)

    weather = Function(
        name="get_weather",
        description="Get the current weather for a given city.",
        properties={"city": {"type": "string", "description": "city name"}},
        required=["city"],
    )
    weather.link_function(get_weather)

    wc = Function(
        name="word_count",
        description="Count the number of words in a piece of text.",
        properties={"text": {"type": "string", "description": "text to count"}},
        required=["text"],
    )
    wc.link_function(word_count)
    return [calc, weather, wc]


SYSTEM = (
    "You are a precise concierge assistant. You MUST use the provided tools to "
    "compute values, look up weather, or count words rather than guessing. "
    "Put your final, user-facing answer inside a ```answer ... ``` block."
)


def _make_agent(model: str, caller: LLMCaller) -> Agent:
    log_base = NoLog(f"concierge-{model}", {"log_dir": tempfile.gettempdir()})
    system_prompt = Prompt(path="concierge_system", prompt=SYSTEM)  # no functions
    return Agent(
        name="concierge",
        system_prompt=system_prompt,
        model=model,
        llm_caller=caller,
        log_base=log_base,
        max_interrupt_times=5,  # cap on tool-call rounds (OpenAI external loop)
    )


def run_task(agent: Agent, functions: List[Function], task: str):
    """Fresh dialog -> system + task (with tools) -> agent.call() runs the loop."""
    dialog = agent.init_dialog(session_name=f"{agent.model}-task")
    task_prompt = Prompt(
        path="concierge_task",
        prompt="{task}",
        _functions=functions,
        md_tags=["answer"],
    )
    agent.send_message(dialog, task_prompt, prompt_args={"task": task}, creator="user")
    response, _dialog, interrupts = agent.call(dialog)
    return response, interrupts


def _answer_block(msg) -> Optional[str]:
    blocks = (msg.parsed or {}).get("md_tags", {}).get("answer")
    return blocks[0].strip() if blocks else None


def _tools_used(msg, interrupts) -> List[Tuple[str, dict, bool]]:
    # Copilot resolves tools internally -> recorded on extra; OpenAI -> interrupts.
    copilot = msg.extra.get("copilot_tool_calls")
    if copilot:
        return [(tc["name"], tc["arguments"], tc["success"]) for tc in copilot]
    return [(fc.name, fc.arguments, fc.success) for fc in (interrupts or [])]


def _report(model: str, task: str, msg, interrupts) -> None:
    print(f"\n>>> [{model}] {task}")
    ans = _answer_block(msg) or msg.content
    print(f"    answer: {ans}")
    used = _tools_used(msg, interrupts)
    if used:
        rendered = ", ".join(
            f"{name}({args})" + ("" if ok else " [FAILED]") for name, args, ok in used
        )
        print(f"    tools : {rendered}")
    if msg.cost is not None:
        print(f"    cost  : {str(msg.cost).strip().replace(chr(10), ' ')}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Apeiron end-to-end concierge agent")
    ap.add_argument("--ask", action="append", help="a task (repeatable); overrides defaults")
    ap.add_argument("--model", default="claude-sonnet-4.5", help="primary model (Copilot/Claude)")
    ap.add_argument("--compare", action="store_true", help="also run gpt-4.1 (OpenAI) on each task")
    args = ap.parse_args()

    tasks: List[str] = args.ask or [
        "What is 23 multiplied by 19, and what's the weather in Paris?",
        "How many words are in the sentence 'the quick brown fox jumps over the lazy dog'?",
        "What is 144 divided by 12?",
    ]

    print(f"Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
    print(f"Primary model: {args.model} | compare={args.compare}")
    print(f"Tools: calculate, get_weather, word_count | Tasks: {len(tasks)}")

    caller = LLMCaller(config={"random_seed": 7})
    functions = _build_functions()

    primary = _make_agent(args.model, caller)
    compare = _make_agent("gpt-4.1", caller) if args.compare else None

    for task in tasks:
        try:
            msg, interrupts = run_task(primary, functions, task)
            _report(args.model, task, msg, interrupts)
        except Exception as e:  # noqa: BLE001
            print(f"\n>>> [{args.model}] {task}\n    ERROR ({type(e).__name__}): {e}")
        if compare is not None:
            try:
                msg, interrupts = run_task(compare, functions, task)
                _report("gpt-4.1", task, msg, interrupts)
            except Exception as e:  # noqa: BLE001
                print(f">>> [gpt-4.1] {task}\n    ERROR ({type(e).__name__}): {e}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
