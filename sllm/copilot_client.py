"""Claude (and other models) via the GitHub Copilot SDK (github-copilot-sdk).

Bridges the async, event-driven Copilot SDK into Apeiron's synchronous LLM
interface so Claude models can be called through a GitHub Copilot subscription
— or through your own Anthropic key via BYOK.

Verified against ``copilot`` SDK v1.0.1:
  - ``client = CopilotClient(github_token=...); await client.start()``
  - ``session = await client.create_session(model=..., provider=..., streaming=...)``
  - ``session.on(handler)`` registers a ``SessionEvent`` listener (returns an
    unsubscribe callable); ``await session.send_and_wait(prompt, timeout=...)``
    blocks until the turn completes.
  - assistant text arrives on ``assistant.message`` events (``content`` field),
    with ``assistant.message_delta`` / ``assistant.streaming_delta`` as a
    streaming fallback.

Prerequisites:
  - The GitHub Copilot CLI must be installed and on PATH.
  - The ``copilot`` SDK must be installed.
  - Auth: ``COPILOT_GITHUB_TOKEN`` env var, or the Copilot CLI's logged-in
    session (SDK default), or BYOK via ``ANTHROPIC_API_KEY`` (provider='anthropic').
"""

import asyncio
import inspect
import json
import os
import threading
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

_logger = logging.getLogger(__name__)

# BYOK providers supported by the Copilot SDK ProviderConfig.
_SUPPORTED_BYOK_PROVIDERS = {"aoai", "anthropic"}


async def _maybe_await(value: Any) -> Any:
    """Await ``value`` if it is awaitable, otherwise return it as-is.

    Lets this module work whether the SDK methods are coroutines or plain calls.
    """
    if inspect.isawaitable(value):
        return await value
    return value


class _AsyncBridge:
    """Runs async Copilot SDK coroutines from synchronous code on a shared loop."""

    _loop: Optional[asyncio.AbstractEventLoop] = None
    _thread: Optional[threading.Thread] = None
    _lock = threading.Lock()

    @classmethod
    def get_loop(cls) -> asyncio.AbstractEventLoop:
        with cls._lock:
            if cls._loop is not None:
                return cls._loop
            cls._loop = asyncio.new_event_loop()
            cls._thread = threading.Thread(
                target=cls._loop.run_forever, daemon=True, name="copilot-async-bridge"
            )
            cls._thread.start()
            return cls._loop

    @classmethod
    def run(cls, coro):
        loop = cls.get_loop()
        if threading.current_thread() is cls._thread:
            raise RuntimeError("_AsyncBridge.run() called from the event loop thread — would deadlock.")
        return asyncio.run_coroutine_threadsafe(coro, loop).result()


def resolve_github_token() -> Optional[str]:
    """Resolve a GitHub Copilot token. Returns None to fall back to CLI auth."""
    token = os.environ.get("COPILOT_GITHUB_TOKEN")
    if token:
        _logger.debug("Using GitHub Copilot token from COPILOT_GITHUB_TOKEN.")
        return token
    _logger.debug("No COPILOT_GITHUB_TOKEN set; falling back to Copilot CLI auth.")
    return None


def build_provider_config(provider: Optional[str]) -> Optional[Dict[str, Any]]:
    """Build a Copilot SDK provider config (BYOK), or None for native Copilot models.

    - ``anthropic``: route Claude calls to your own Anthropic endpoint using
      ``ANTHROPIC_API_KEY``.
    - ``aoai``: route to your Azure OpenAI endpoint using a cached/az-login token.
    """
    if provider is None:
        return None
    if provider not in _SUPPORTED_BYOK_PROVIDERS:
        raise ValueError(
            f"Unsupported BYOK provider '{provider}'. Supported: {', '.join(sorted(_SUPPORTED_BYOK_PROVIDERS))}"
        )
    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("provider='anthropic' requires ANTHROPIC_API_KEY in the environment.")
        return {"type": "anthropic", "api_key": api_key}
    # aoai
    from sllm.auth import get_azure_token_provider, AZURE_COGNITIVE_SCOPE
    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
    bearer = get_azure_token_provider(AZURE_COGNITIVE_SCOPE)()
    return {"type": "aoai", "endpoint": endpoint, "api_version": api_version, "bearer_token": bearer}


def _event_payload(event: Any) -> Dict[str, Any]:
    """Best-effort extraction of an event's data dict (handles flat or nested)."""
    if hasattr(event, "to_dict"):
        try:
            d = event.to_dict()
        except Exception:  # noqa: BLE001
            d = {}
    elif isinstance(event, dict):
        d = event
    else:
        d = {}
    data = d.get("data")
    return data if isinstance(data, dict) else d


def _event_type(event: Any) -> Optional[str]:
    rt = getattr(event, "raw_type", None)
    if rt is not None:
        return rt
    if isinstance(event, dict):
        return event.get("type") or event.get("raw_type")
    return None


class CopilotClaudeClient:
    """Synchronous wrapper around the async Copilot SDK for single-shot completions."""

    _client = None      # shared started Copilot SDK client
    _started = False
    _client_lock = threading.Lock()

    def __init__(self, provider: Optional[str] = None):
        self.provider = provider

    @classmethod
    async def _ensure_client(cls):
        if cls._client is not None and cls._started:
            return cls._client
        with cls._client_lock:
            if cls._client is None:
                try:
                    from copilot import CopilotClient
                except ImportError as e:  # noqa: BLE001
                    raise ImportError(
                        "The 'copilot' (github-copilot-sdk) package is required for Claude-via-Copilot. "
                        "Install the GitHub Copilot CLI and the copilot SDK, then set COPILOT_GITHUB_TOKEN."
                    ) from e
                client_kwargs: Dict[str, Any] = {}
                token = resolve_github_token()
                if token:
                    client_kwargs["github_token"] = token
                cls._client = CopilotClient(**client_kwargs)
        if not cls._started:
            await _maybe_await(cls._client.start())
            cls._started = True
        return cls._client

    @staticmethod
    def _flatten_prompt(messages: List[Dict[str, Any]]) -> str:
        """Flatten a chat-style message list into a single prompt string."""
        parts: List[str] = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if isinstance(content, list):  # multimodal blocks -> join text parts
                content = "\n".join(
                    part.get("text", "") for part in content if isinstance(part, dict)
                )
            if role in ("system", "developer"):
                parts.append(f"[system]\n{content}")
            else:
                parts.append(f"{role}: {content}")
        return "\n\n".join(parts)

    @staticmethod
    def _build_tools(tool_specs: List[Dict[str, Any]]) -> List[Any]:
        """Turn provider-agnostic tool specs into Copilot ``Tool`` objects.

        Each spec is a dict with keys:
          - ``name`` (str), ``description`` (str)
          - ``properties`` (dict) / ``required`` (list): JSON-schema params
          - ``execute`` (Callable[[dict, str], Tuple[str, bool]]): runs the tool
            with the model-provided arguments and the tool_call_id, returning
            ``(text_result_for_llm, success)``.

        The handler is sync and returns a ``ToolResult``; the SDK drives the
        full call loop internally (model -> tool -> model -> ... -> final text).
        """
        from copilot import Tool, ToolResult

        tools: List[Any] = []
        for spec in tool_specs:
            execute = spec["execute"]

            def _handler(invocation: Any, _execute=execute) -> Any:
                # NOTE: when a Tool is constructed directly (vs. via define_tool),
                # the SDK calls handler(invocation) with a single positional arg.
                args = getattr(invocation, "arguments", None)
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (ValueError, TypeError):
                        args = {}
                if not isinstance(args, dict):
                    args = {}
                call_id = getattr(invocation, "tool_call_id", "") or ""
                try:
                    text, ok = _execute(args, call_id)
                except Exception as e:  # noqa: BLE001 - surface tool errors to the model
                    return ToolResult(text_result_for_llm=f"Error: {e}", result_type="failure", error=str(e))
                return ToolResult(
                    text_result_for_llm=text or "",
                    result_type="success" if ok else "failure",
                    error=None if ok else (text or "tool failed"),
                )

            tools.append(
                Tool(
                    name=spec["name"],
                    description=spec.get("description", ""),
                    handler=_handler,
                    parameters={
                        "type": "object",
                        "properties": spec.get("properties", {}) or {},
                        "required": spec.get("required", []) or [],
                    },
                    skip_permission=True,  # caller's own registered functions
                )
            )
        return tools

    def complete(
        self,
        messages: List[Dict[str, Any]],
        model: str = "claude-sonnet-4.5",
        *,
        provider: Optional[str] = None,
        timeout: float = 120.0,
        tool_specs: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> str:
        """Run a completion against a Claude (or other) model via Copilot.

        If ``tool_specs`` is provided, the Copilot SDK runs the full tool-calling
        loop internally: the model may invoke the registered tools (whose
        handlers execute the caller's functions), and the returned string is the
        model's final assistant text after all tool calls have resolved.
        """
        provider = provider if provider is not None else self.provider
        prompt = self._flatten_prompt(messages)
        provider_config = build_provider_config(provider)
        tools = self._build_tools(tool_specs) if tool_specs else None

        async def _run() -> str:
            client = await self._ensure_client()
            session_kwargs: Dict[str, Any] = {"model": model, "streaming": True}
            if provider_config is not None:
                session_kwargs["provider"] = provider_config
            if tools:
                session_kwargs["tools"] = tools
                try:
                    from copilot import PermissionHandler
                    session_kwargs["on_permission_request"] = PermissionHandler.approve_all
                except Exception:  # noqa: BLE001 - skip_permission already set per tool
                    pass
            session = await _maybe_await(client.create_session(**session_kwargs))

            messages_full: List[str] = []
            deltas: List[str] = []

            def _on_event(event: Any) -> None:
                etype = _event_type(event)
                payload = _event_payload(event)
                if etype == "assistant.message":
                    text = payload.get("content")
                    if text:
                        messages_full.append(str(text))
                elif etype in ("assistant.message_delta", "assistant.streaming_delta"):
                    chunk = payload.get("content") or payload.get("delta") or payload.get("text")
                    if chunk:
                        deltas.append(str(chunk))
                elif etype in ("model.call_failure", "session.error"):
                    _logger.warning("Copilot session error event: %s", payload)

            unsubscribe = session.on(_on_event)
            final_event = None
            try:
                final_event = await _maybe_await(
                    session.send_and_wait(prompt, timeout=timeout)
                )
            finally:
                if callable(unsubscribe):
                    try:
                        unsubscribe()
                    except Exception:  # noqa: BLE001
                        pass
                disconnect = getattr(session, "disconnect", None)
                if callable(disconnect):
                    try:
                        await _maybe_await(disconnect())
                    except Exception:  # noqa: BLE001
                        pass

            if messages_full:
                return messages_full[-1]
            if final_event is not None:
                payload = _event_payload(final_event)
                text = payload.get("content") or payload.get("text")
                if text:
                    return str(text)
            if deltas:
                return "".join(deltas)
            return ""

        return _AsyncBridge.run(_run())
