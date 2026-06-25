"""Azure authentication helpers for Apeiron.

Provides cached interactive browser login for connecting to Azure resources
(Azure OpenAI / AI Foundry, CUA), with API keys as a secondary fallback.

This uses cached interactive browser login with API keys as a fallback:
  - ``CachedInteractiveBrowserCredential`` persists an ``AuthenticationRecord``
    so the browser only opens on first login; later runs acquire tokens
    silently from the OS-encrypted MSAL token cache.
  - ``azure_openai_auth_kwargs`` returns the right kwargs for the OpenAI SDK,
    preferring an Entra ID token (az login / cached browser) and falling back
    to an API key from the environment.

Auth mode is controlled by the ``AZURE_OPENAI_AUTH_MODE`` environment variable:
  - ``interactive`` (default): try az login, then cached interactive browser
    login; if no token can be acquired, fall back to the API key env var.
  - ``key``: use the API key env var only (no interactive login).
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from azure.identity import (
    AuthenticationRecord,
    AzureCliCredential,
    ChainedTokenCredential,
    CredentialUnavailableError,
    InteractiveBrowserCredential,
    TokenCachePersistenceOptions,
    get_bearer_token_provider,
)
from azure.core.credentials import AccessToken, TokenCredential

_logger = logging.getLogger(__name__)

# Standard scope for Azure OpenAI / Cognitive Services data-plane access.
AZURE_COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"

# Default API version used across the codebase.
DEFAULT_API_VERSION = "2025-04-01-preview"


class CachedInteractiveBrowserCredential(TokenCredential):
    """InteractiveBrowserCredential wrapper with persistent AuthenticationRecord caching.

    On first use the browser opens for interactive login. The resulting
    ``AuthenticationRecord`` is saved under ``~/.apeiron/auth/<record_name>.json``
    so that subsequent runs silently acquire tokens from the OS-encrypted MSAL
    token cache without re-opening the browser.

    Args:
        record_name: Filename stem for the persisted AuthenticationRecord.
        **kwargs: Forwarded to ``InteractiveBrowserCredential`` (e.g. ``client_id``,
            ``additionally_allowed_tenants``, ``timeout``).
    """

    _AUTH_DIR = Path.home() / ".apeiron" / "auth"

    def __init__(self, *, record_name: str = "apeiron-azcli", **kwargs: Any):
        if any(sep in record_name for sep in ("/", "\\")):
            raise ValueError("record_name must be a filename-only value without path separators.")
        self._record_name = record_name
        self._credential_kwargs = kwargs
        self._credential: Optional[InteractiveBrowserCredential] = None
        self._persisted = False

    @property
    def _record_path(self) -> Path:
        return self._AUTH_DIR / f"{self._record_name}.json"

    def _load_record(self) -> Optional[AuthenticationRecord]:
        path = self._record_path
        if path.exists():
            try:
                return AuthenticationRecord.deserialize(path.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                _logger.warning("Failed to load auth record from %s: %s", path, e)
        return None

    def _save_record(self, record: AuthenticationRecord) -> None:
        try:
            self._AUTH_DIR.mkdir(parents=True, exist_ok=True)
            self._record_path.write_text(record.serialize(), encoding="utf-8")
            try:
                os.chmod(self._record_path, 0o600)  # best effort (no-op on Windows)
            except OSError:
                pass
        except Exception as e:  # noqa: BLE001
            _logger.warning("Failed to save auth record to %s: %s", self._record_path, e)

    def _get_credential(self) -> InteractiveBrowserCredential:
        if self._credential is None:
            record = self._load_record()
            self._credential = InteractiveBrowserCredential(
                cache_persistence_options=TokenCachePersistenceOptions(),
                authentication_record=record,
                **self._credential_kwargs,
            )
            if record is not None:
                self._persisted = True
        return self._credential

    def get_token(self, *scopes: str, **kwargs: Any) -> AccessToken:
        credential = self._get_credential()
        if not self._persisted:
            try:
                record = credential.authenticate(scopes=list(scopes))
                self._save_record(record)
            except Exception as e:  # noqa: BLE001
                _logger.debug("Could not persist auth record: %s", e)
            self._persisted = True
        return credential.get_token(*scopes, **kwargs)


def get_azure_credential() -> ChainedTokenCredential:
    """Credential chain for Azure resources: az login first, then cached browser login.

    ``AzureCliCredential`` is tried first (silent, no browser) for developers
    already authenticated via ``az login``; ``CachedInteractiveBrowserCredential``
    opens the browser only on first login and caches the record afterward.
    """
    return ChainedTokenCredential(
        AzureCliCredential(additionally_allowed_tenants=["*"]),
        CachedInteractiveBrowserCredential(
            record_name="apeiron-azcli",
            additionally_allowed_tenants=["*"],
        ),
    )


def get_azure_token_provider(scope: str = AZURE_COGNITIVE_SCOPE):
    """Return a bearer-token provider callable for the OpenAI SDK's ``azure_ad_token_provider``."""
    return get_bearer_token_provider(get_azure_credential(), scope)


def azure_openai_auth_kwargs(
    api_key_env: str = "AZURE_AI_FOUNDRY_KEY",
    scope: str = AZURE_COGNITIVE_SCOPE,
    *,
    verify: Optional[bool] = None,
) -> Dict[str, Any]:
    """Build the auth kwargs for ``AzureOpenAI`` / ``AsyncAzureOpenAI``.

    Primary: Entra ID token via az login / cached interactive browser login.
    Secondary: API key from the ``api_key_env`` environment variable.

    Controlled by ``AZURE_OPENAI_AUTH_MODE``:
      - ``interactive`` (default): prefer the token credential; if a token cannot
        be acquired (e.g. headless/CI with no cached login) and an API key is
        present, fall back to the key.
      - ``key``: use the API key only.

    Set ``AZURE_OPENAI_AUTH_VERIFY=0`` (or pass ``verify=False``) to skip the
    eager token check and always return a lazy token provider in interactive
    mode (the browser/login is then triggered on the first request instead).
    """
    mode = os.getenv("AZURE_OPENAI_AUTH_MODE", "interactive").strip().lower()
    api_key = os.getenv(api_key_env)

    if mode == "key":
        if not api_key:
            raise RuntimeError(
                f"AZURE_OPENAI_AUTH_MODE=key but {api_key_env} is not set in the environment."
            )
        return {"api_key": api_key}

    if verify is None:
        verify = os.getenv("AZURE_OPENAI_AUTH_VERIFY", "1").strip().lower() not in ("0", "false", "no")

    if verify:
        # Eagerly try to acquire a token so we can cleanly fall back to the API
        # key when interactive login is unavailable (e.g. headless environments).
        try:
            get_azure_credential().get_token(scope)
        except (CredentialUnavailableError, Exception) as e:  # noqa: BLE001
            if api_key:
                _logger.warning(
                    "Interactive/az-login auth unavailable (%s); falling back to API key %s.",
                    type(e).__name__,
                    api_key_env,
                )
                return {"api_key": api_key}
            raise

    return {"azure_ad_token_provider": get_azure_token_provider(scope)}


def build_azure_openai_client(
    endpoint: Optional[str] = None,
    api_version: str = DEFAULT_API_VERSION,
    api_key_env: str = "AZURE_AI_FOUNDRY_KEY",
    scope: str = AZURE_COGNITIVE_SCOPE,
    *,
    is_async: bool = False,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
):
    """Construct an (Async)AzureOpenAI client using cached browser login or an API key.

    A bounded request ``timeout`` is always applied so a stalled endpoint fails fast
    instead of hanging the whole pipeline indefinitely (a single synchronous
    completion call cannot otherwise be interrupted by an outer asyncio timeout).
    The default is generous enough for slow reasoning models but can be tuned via
    the AZURE_OPENAI_TIMEOUT (seconds) and AZURE_OPENAI_MAX_RETRIES env vars.
    """
    from openai import AzureOpenAI, AsyncAzureOpenAI

    endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
    auth_kwargs = azure_openai_auth_kwargs(api_key_env=api_key_env, scope=scope)
    client_cls = AsyncAzureOpenAI if is_async else AzureOpenAI
    if timeout is None:
        timeout = float(os.getenv("AZURE_OPENAI_TIMEOUT", "3600"))  # seconds
    if max_retries is None:
        max_retries = int(os.getenv("AZURE_OPENAI_MAX_RETRIES", "2"))
    return client_cls(
        api_version=api_version,
        azure_endpoint=endpoint,
        timeout=timeout,
        max_retries=max_retries,
        **auth_kwargs,
    )
