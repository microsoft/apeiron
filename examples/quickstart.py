"""Apeiron quickstart — a minimal end-to-end app built on the toolkit.

What it shows:
  1. Auth: Azure OpenAI via cached browser / az-login (no API key needed).
  2. A single-shot completion through ``LLMCaller`` (gpt-4.1, provider=OPENAI).
  3. The same question routed to Claude via the GitHub Copilot SDK
     (claude-sonnet-4.5, provider=COPILOT).
  4. Structured parsing with a ``Prompt`` (markdown-fenced answer block).
  5. Token usage / cost for the OpenAI call.

Run:
    python examples/quickstart.py
    python examples/quickstart.py --question "Name 3 prime numbers." --model gpt-4.1
    python examples/quickstart.py --no-copilot        # skip the Copilot/Claude call

Requires a populated .env (AZURE_OPENAI_ENDPOINT) and, for the Copilot call,
the GitHub Copilot CLI + copilot SDK on PATH.
"""
import argparse
import os
import sys
import tempfile
from typing import Optional

# Make the package importable when run from anywhere.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_ROOT, ".env"))
except Exception:
    pass

from sllm.const import Roles, find_model_card, Providers
from sllm.llm import Dialog, LLMCaller, Prompt
from sllm.log import NoLog


def _make_caller() -> LLMCaller:
    # LLMCaller builds its Azure OpenAI client via cached browser / az-login.
    return LLMCaller(config={"random_seed": 7})


def _new_dialog(name: str) -> Dialog:
    # NoLog = in-memory, no files written. (LogBase still needs a log_dir.)
    log_base = NoLog(name, {"log_dir": tempfile.gettempdir()})
    return Dialog(_messages=[], log_base=log_base, session_name=name)


def ask(caller: LLMCaller, model: str, question: str, system: Optional[str], prompt: Prompt):
    """Single-shot: fresh dialog -> optional system + user message -> call model."""
    dialog = _new_dialog(f"quickstart-{model}")
    if system:
        dialog.send_message(system, role=Roles.SYSTEM, creator="system")
    dialog.send_message(question, role=Roles.USER, creator="user")
    return caller.call(dialog, prompt, model=model)


def _answer_block(msg) -> Optional[str]:
    if not msg.parsed:
        return None
    blocks = msg.parsed.get("md_tags", {}).get("answer")
    return blocks[0].strip() if blocks else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Apeiron quickstart end-to-end demo")
    ap.add_argument("--question", default="What is the capital of France? Answer in one word.")
    ap.add_argument("--model", default="gpt-4.1", help="OpenAI model card name")
    ap.add_argument("--copilot-model", default="claude-sonnet-4.5", help="Copilot/Claude model card name")
    ap.add_argument("--no-copilot", action="store_true", help="skip the Claude-via-Copilot call")
    args = ap.parse_args()

    system = "You are a concise assistant. Put your final answer inside a ```answer ... ``` block."
    # A Prompt carries parsing config (here: extract a fenced ```answer``` block).
    prompt = Prompt(path="quickstart", prompt="(messages carry the question)", md_tags=["answer"])

    print(f"Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
    print(f"Question: {args.question}\n")

    caller = _make_caller()

    # --- 1) OpenAI (gpt-4.1) ---
    print(f"=== {args.model} (provider=OPENAI) ===")
    msg = ask(caller, args.model, args.question, system, prompt)
    print("raw:", msg.content)
    ans = _answer_block(msg)
    if ans:
        print("parsed answer block:", ans)
    cost = msg.cost
    if cost is not None:
        print(str(cost).strip())
    print()

    # --- 2) Claude via Copilot ---
    if not args.no_copilot:
        print(f"=== {args.copilot_model} (provider=COPILOT) ===")
        card = find_model_card(args.copilot_model)
        assert card.provider == Providers.COPILOT, f"{args.copilot_model} is not a COPILOT model"
        try:
            cmsg = ask(caller, args.copilot_model, args.question, system, prompt)
            print("raw:", cmsg.content)
            cans = _answer_block(cmsg)
            if cans:
                print("parsed answer block:", cans)
        except Exception as e:  # noqa: BLE001
            print(f"Copilot call failed ({type(e).__name__}): {e}")
            print("(needs the GitHub Copilot CLI + copilot SDK installed.)")
        print()

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
