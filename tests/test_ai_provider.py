"""Tests for the AI provider factory and OpenAI provider configuration."""
import pytest

from core.ai_provider import (
    OpenAIProvider,
    AnthropicProvider,
    create_ai_provider,
    AuthenticationError,
    ModelUnavailableError,
    classify_provider_error,
)
from core.ai_provider import ProviderError


def test_create_openai_provider_honors_extra_model():
    """OPENAI_MODEL (extra_model) must take precedence over the generic model."""
    provider = create_ai_provider(
        "openai",
        "",                       # AI_API_KEY empty
        "",                       # AI_MODEL empty
        extra_key="sk-test-openai-key",
        extra_model="gpt-4o-mini",
    )
    assert isinstance(provider, OpenAIProvider)
    assert provider.provider_name == "openai"
    assert provider.model == "gpt-4o-mini"


def test_create_openai_provider_falls_back_to_generic_model():
    """When OPENAI_MODEL is empty, fall back to the generic model."""
    provider = create_ai_provider(
        "openai",
        "",
        "gpt-4-turbo",            # generic model
        extra_key="sk-test-openai-key",
        extra_model="",
    )
    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "gpt-4-turbo"


def test_create_openai_provider_default_model():
    """With no models configured, default to gpt-4o."""
    provider = create_ai_provider(
        "openai",
        "",
        "",
        extra_key="sk-test-openai-key",
        extra_model="",
    )
    assert provider.model == "gpt-4o"


def test_create_provider_missing_key_raises():
    """No key anywhere should raise AuthenticationError (no silent misconfig)."""
    with pytest.raises(AuthenticationError):
        create_ai_provider("openai", "", "", extra_key="", extra_model="")


def test_openai_provider_requires_package(monkeypatch):
    """Simulate the openai package being missing -> ProviderError, not raw crash."""
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("No module named 'openai'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    # Re-import the module so its module-level `openai` reference is not cached.
    import importlib
    import core.ai_provider as ap
    importlib.reload(ap)

    with pytest.raises(ap.ProviderError):
        ap.OpenAIProvider("sk-test-key", "gpt-4o")

    monkeypatch.undo()


def test_classify_model_unavailable_requires_not():
    """'model ... not ... found' should classify as model_unavailable."""
    class Fake:
        def __init__(self, msg):
            self.message = msg
        def __str__(self):
            return self.message
    msg, kind = classify_provider_error(Fake("anthropic: model not found"))
    assert kind == "model_unavailable"


def test_classify_rate_limit():
    class Fake:
        def __str__(self):
            return "Rate limit hit: 429 too many requests"
    msg, kind = classify_provider_error(Fake())
    assert kind == "rate_limit"


def test_classify_authentication_error_passthrough():
    import core.ai_provider as ap
    err = ap.AuthenticationError("bad key")
    msg, kind = classify_provider_error(err)
    assert kind == "authentication"
    assert "key" in msg.lower()


def test_model_unavailable_error_kind():
    import core.ai_provider as ap
    err = ap.ModelUnavailableError()
    assert err.kind == "model_unavailable"
