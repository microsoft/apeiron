"""Unit tests for sllm.auth (cached interactive browser login + API key fallback).

These tests are network- and browser-free: the credential chain is monkeypatched
so no real Azure login is ever attempted.
"""
import pytest

from sllm import auth


def test_record_name_rejects_path_separators():
    with pytest.raises(ValueError):
        auth.CachedInteractiveBrowserCredential(record_name="bad/name")
    with pytest.raises(ValueError):
        auth.CachedInteractiveBrowserCredential(record_name="bad\\name")


def test_record_path_under_apeiron_auth_dir():
    cred = auth.CachedInteractiveBrowserCredential(record_name="unit-test")
    path = cred._record_path
    assert path.name == "unit-test.json"
    assert path.parent.name == "auth"
    assert path.parent.parent.name == ".apeiron"


def test_auth_kwargs_key_mode_returns_api_key(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_AUTH_MODE", "key")
    monkeypatch.setenv("MY_KEY", "secret-123")
    kwargs = auth.azure_openai_auth_kwargs(api_key_env="MY_KEY")
    assert kwargs == {"api_key": "secret-123"}


def test_auth_kwargs_key_mode_missing_key_raises(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_AUTH_MODE", "key")
    monkeypatch.delenv("MY_KEY", raising=False)
    with pytest.raises(RuntimeError):
        auth.azure_openai_auth_kwargs(api_key_env="MY_KEY")


def test_auth_kwargs_interactive_token_success(monkeypatch):
    # Token acquisition succeeds -> return a token provider, not the API key.
    monkeypatch.setenv("AZURE_OPENAI_AUTH_MODE", "interactive")

    class _FakeCred:
        def get_token(self, *scopes, **kwargs):
            return "ok"

    monkeypatch.setattr(auth, "get_azure_credential", lambda: _FakeCred())
    monkeypatch.setattr(auth, "get_azure_token_provider", lambda scope: (lambda: "token"))
    kwargs = auth.azure_openai_auth_kwargs(api_key_env="MY_KEY", verify=True)
    assert "azure_ad_token_provider" in kwargs
    assert "api_key" not in kwargs


def test_auth_kwargs_interactive_falls_back_to_key(monkeypatch):
    # Token acquisition fails and an API key is present -> fall back to the key.
    monkeypatch.setenv("AZURE_OPENAI_AUTH_MODE", "interactive")
    monkeypatch.setenv("MY_KEY", "fallback-key")

    class _FailingCred:
        def get_token(self, *scopes, **kwargs):
            raise RuntimeError("no interactive login available")

    monkeypatch.setattr(auth, "get_azure_credential", lambda: _FailingCred())
    kwargs = auth.azure_openai_auth_kwargs(api_key_env="MY_KEY", verify=True)
    assert kwargs == {"api_key": "fallback-key"}


def test_auth_kwargs_interactive_no_verify_skips_token_check(monkeypatch):
    # verify=False -> lazy token provider, no eager get_token() call.
    monkeypatch.setenv("AZURE_OPENAI_AUTH_MODE", "interactive")

    def _boom():
        raise AssertionError("get_azure_credential should not be called when verify=False")

    monkeypatch.setattr(auth, "get_azure_credential", _boom)
    monkeypatch.setattr(auth, "get_azure_token_provider", lambda scope: (lambda: "token"))
    kwargs = auth.azure_openai_auth_kwargs(api_key_env="MY_KEY", verify=False)
    assert "azure_ad_token_provider" in kwargs
