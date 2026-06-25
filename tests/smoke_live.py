"""Live smoke tests for the two new features.

Run directly (NOT collected by pytest — it makes live calls):
    python tests/smoke_live.py            # run auth + copilot smoke
    python tests/smoke_live.py introspect # dump the installed copilot SDK API

Single-call / single-worker by design so it's runnable on a laptop.
"""
import os
import sys
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load .env the same way the app does.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except Exception:
    pass


def hr(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def introspect_copilot():
    import inspect
    hr("COPILOT SDK INTROSPECTION")
    import copilot
    print("copilot version:", getattr(copilot, "__version__", "?"))

    def sig(obj, name):
        try:
            return str(inspect.signature(obj))
        except (TypeError, ValueError):
            return "(no signature)"

    cc = copilot.CopilotClient
    print("\nCopilotClient.create_session:", sig(cc.create_session, "create_session"))
    print("CopilotClient.list_models:", sig(cc.list_models, "list_models"))

    sess = copilot.CopilotSession
    print("\nCopilotSession public members:", [m for m in dir(sess) if not m.startswith('_')])
    for m in ('send', 'send_message', 'prompt', 'on_event', 'on', 'subscribe', 'events', 'stream', 'run', 'wait', 'close', 'end'):
        if hasattr(sess, m):
            print(f"  CopilotSession.{m}:", sig(getattr(sess, m), m))

    set_ = getattr(copilot, 'SessionEventType', None)
    if set_ is not None:
        try:
            print("\nSessionEventType values:", [e.name + '=' + repr(e.value) for e in set_])
        except TypeError:
            print("\nSessionEventType members:", [m for m in dir(set_) if not m.startswith('_')])

    se = getattr(copilot, 'SessionEvent', None)
    if se is not None:
        print("\nSessionEvent public members:", [m for m in dir(se) if not m.startswith('_')])

    pc = getattr(copilot, 'ProviderConfig', None)
    if pc is not None:
        print("\nProviderConfig.__init__:", sig(pc.__init__, '__init__'))
        print("ProviderConfig public members:", [m for m in dir(pc) if not m.startswith('_')])

    sevents = getattr(copilot, 'session_events', None)
    if sevents is not None:
        print("\ncopilot.session_events dir:", [m for m in dir(sevents) if not m.startswith('_')])

    print("\nCopilotSession.send_and_wait:", sig(sess.send_and_wait, 'send_and_wait'))
    print("CopilotSession.get_events:", sig(sess.get_events, 'get_events'))
    amd = getattr(sevents, 'AssistantMessageData', None)
    if amd is not None:
        print("\nAssistantMessageData fields:", [m for m in dir(amd) if not m.startswith('_')])
        try:
            print("AssistantMessageData.__init__:", sig(amd.__init__, '__init__'))
        except Exception:
            pass
    smc = getattr(copilot, 'SystemMessageConfig', None)
    if smc is not None:
        print("\nSystemMessageConfig.__init__:", sig(smc.__init__, '__init__'))
    sd = getattr(sevents, 'SessionEventData', None)
    if sd is not None:
        print("SessionEventData public members:", [m for m in dir(sd) if not m.startswith('_')])


def smoke_auth():
    hr("AUTH SMOKE — cached browser login / az login -> Azure token")
    from sllm.auth import get_azure_credential, AZURE_COGNITIVE_SCOPE, azure_openai_auth_kwargs
    print("AZURE_OPENAI_ENDPOINT:", os.getenv("AZURE_OPENAI_ENDPOINT"))
    print("AZURE_OPENAI_AUTH_MODE:", os.getenv("AZURE_OPENAI_AUTH_MODE", "interactive (default)"))
    print("AZURE_AI_FOUNDRY_KEY set:", bool(os.getenv("AZURE_AI_FOUNDRY_KEY")))
    try:
        cred = get_azure_credential()
        tok = cred.get_token(AZURE_COGNITIVE_SCOPE)
        print(f"OK: acquired Entra token (len={len(tok.token)}, expires_on={tok.expires_on})")
    except Exception as e:
        print("FAILED to acquire token:")
        traceback.print_exc()
        return False
    try:
        kwargs = azure_openai_auth_kwargs()
        print("azure_openai_auth_kwargs keys:", list(kwargs.keys()))
    except Exception:
        traceback.print_exc()
    return True


def smoke_auth_completion():
    hr("AUTH SMOKE — tiny Azure OpenAI completion via token")
    from sllm.auth import build_azure_openai_client
    model = os.getenv("SMOKE_AOAI_MODEL", "gpt-4.1")
    try:
        client = build_azure_openai_client()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with the single word: pong"}],
            max_completion_tokens=8,
        )
        print(f"OK ({model}):", resp.choices[0].message.content)
        return True
    except Exception:
        print(f"completion failed (model/deployment '{model}' — set SMOKE_AOAI_MODEL to your deployment):")
        traceback.print_exc()
        return False


def smoke_copilot():
    hr("COPILOT SMOKE — Claude via GitHub Copilot SDK")
    print("COPILOT_GITHUB_TOKEN set:", bool(os.getenv("COPILOT_GITHUB_TOKEN")))
    from sllm.copilot_client import CopilotClaudeClient, _AsyncBridge, _maybe_await
    model = os.getenv("SMOKE_COPILOT_MODEL", "claude-sonnet-4.5")

    # List available models first so we can confirm the exact Claude id.
    try:
        async def _models():
            client = await CopilotClaudeClient._ensure_client()
            return await _maybe_await(client.list_models())
        models = _AsyncBridge.run(_models())
        names = []
        for m in models:
            n = getattr(m, "id", None) or getattr(m, "name", None) or str(m)
            names.append(n)
        print("Available models:", names)
        claude = [n for n in names if "claude" in str(n).lower()]
        print("Claude models:", claude)
        if claude and model not in names:
            model = claude[0]
            print(f"Using detected Claude model: {model}")
    except Exception:
        print("list_models failed:")
        traceback.print_exc()

    try:
        client = CopilotClaudeClient()
        text = client.complete(
            messages=[{"role": "user", "content": "Reply with the single word: pong"}],
            model=model,
            timeout=120.0,
        )
        print(f"OK ({model}): {text!r}")
        return bool(text)
    except Exception:
        print("copilot completion failed:")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "introspect":
        introspect_copilot()
        sys.exit(0)
    results = {}
    results["auth_token"] = smoke_auth()
    if results["auth_token"]:
        results["auth_completion"] = smoke_auth_completion()
    results["copilot"] = smoke_copilot()
    hr("SUMMARY")
    for k, v in results.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
