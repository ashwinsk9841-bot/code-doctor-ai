"""Tests for the AI provider factory and OpenAI provider configuration."""
import pytest

from core.ai_provider import (
    OpenAIProvider,
    AnthropicProvider,
    OpenCodeZenProvider,
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


# ---------------------------------------------------------------------------
# OpenCode Zen provider
# ---------------------------------------------------------------------------

def test_create_opencode_zen_provider_defaults():
    """OpenCode Zen provider defaults to the free big-pickle model and Zen base URL."""
    provider = OpenCodeZenProvider("sk-zen-test-key")
    assert isinstance(provider, OpenCodeZenProvider)
    assert provider.provider_name == "opencode_zen"
    assert provider.model == "big-pickle"
    assert provider.base_url == "https://opencode.ai/zen/v1"


def test_create_opencode_zen_provider_custom():
    provider = OpenCodeZenProvider("sk-zen-test-key", model="mimo-v2.5-free")
    assert provider.model == "mimo-v2.5-free"


def test_create_opencode_zen_missing_key_raises():
    import core.ai_provider as ap
    with pytest.raises(ap.AuthenticationError):
        ap.OpenCodeZenProvider("")


def test_create_opencode_zen_requires_package(monkeypatch):
    """Missing openai package -> ProviderError, not a raw crash."""
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("No module named 'openai'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    import importlib
    import core.ai_provider as ap
    importlib.reload(ap)

    with pytest.raises(ap.ProviderError):
        ap.OpenCodeZenProvider("sk-zen-test-key")

    monkeypatch.undo()


def test_factory_opencode_zen_via_zen_key():
    """Factory returns an OpenCodeZenProvider when zen_key is provided."""
    import core.ai_provider as ap
    provider = ap.create_ai_provider(
        "opencode_zen",
        "", "", "",
        zen_key="sk-zen-test-key",
        zen_model="",
    )
    assert isinstance(provider, ap.OpenCodeZenProvider)
    assert provider.model == "big-pickle"


def test_factory_opencode_zen_uses_zen_model():
    import core.ai_provider as ap
    provider = ap.create_ai_provider(
        "opencode_zen",
        "", "", "",
        zen_key="sk-zen-test-key",
        zen_model="mimo-v2.5-free",
    )
    assert isinstance(provider, ap.OpenCodeZenProvider)
    assert provider.model == "mimo-v2.5-free"


def test_factory_opencode_zen_fallback_to_generic_model():
    import core.ai_provider as ap
    provider = ap.create_ai_provider(
        "opencode_zen",
        "", "gpt-4-turbo", "",
        zen_key="sk-zen-test-key",
        zen_model="",
    )
    assert isinstance(provider, ap.OpenCodeZenProvider)
    assert provider.model == "gpt-4-turbo"


def test_factory_auto_prefers_opencode_zen():
    """With 'auto', the free OpenCode Zen key is chosen first."""
    import core.ai_provider as ap
    provider = ap.create_ai_provider(
        "auto",
        "sk-ant-test", "claude-x",
        extra_key="sk-openai-test",
        zen_key="sk-zen-test-key",
    )
    assert isinstance(provider, ap.OpenCodeZenProvider)
    assert provider.model == "claude-x"


def test_classify_opencode_zen_model_not_found():
    import core.ai_provider as ap
    # A nonexistent free model id should map to model_unavailable.
    class Fake:
        status_code = 404
        def __str__(self):
            return "Model 'not-a-real-model' not found"
    err = ap.OpenCodeZenProvider._classify(Fake())
    assert err.kind == "model_unavailable"
    assert isinstance(err, ap.ModelUnavailableError)


def test_classify_opencode_zen_authentication():
    import core.ai_provider as ap
    class Fake:
        status_code = 401
        def __str__(self):
            return "Authentication failed"
    err = ap.OpenCodeZenProvider._classify(Fake())
    assert err.kind == "authentication"
    assert isinstance(err, ap.AuthenticationError)


# ---------------------------------------------------------------------------
# Rate-limit retry / backoff
# ---------------------------------------------------------------------------

def test_retry_with_backoff_retries_on_rate_limit(monkeypatch):
    """A 429 rate-limit error is retried and eventually succeeds."""
    import core.ai_provider as ap
    calls = {"n": 0}

    def classify(e):
        return ap.RateLimitedError() if isinstance(e, RuntimeError) else e

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("429 rate limit")
        return "ok"

    sleeps = []
    monkeypatch.setattr(ap.time, "sleep", lambda s: sleeps.append(s))
    result = ap._retry_with_backoff(fn, classify, max_attempts=3,
                                    initial_delay=0.0, backoff=2.0)
    assert result == "ok"
    assert calls["n"] == 3
    assert sleeps == [0.0, 0.0]


def test_retry_with_backoff_raises_after_exhaustion():
    """Persistent rate-limit raises RateLimitedError after max attempts."""
    import core.ai_provider as ap

    def classify(e):
        return ap.RateLimitedError()

    def fn():
        raise RuntimeError("429 rate limit")

    import pytest
    with pytest.raises(ap.RateLimitedError):
        ap._retry_with_backoff(fn, classify, max_attempts=2,
                               initial_delay=0.0, backoff=2.0)


def test_retry_with_backoff_passthrough_other_errors(monkeypatch):
    """Non-rate-limit errors are classified and raised without retry."""
    import core.ai_provider as ap

    def classify(e):
        return ap.AuthenticationError("bad key")

    def fn():
        raise RuntimeError("unauthorized")

    monkeypatch.setattr(ap.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("no sleep")))
    with pytest.raises(ap.AuthenticationError):
        ap._retry_with_backoff(fn, classify, max_attempts=3,
                               initial_delay=0.0, backoff=2.0)


# ---------------------------------------------------------------------------
# Batched multi-file analysis
# ---------------------------------------------------------------------------

def test_analyze_many_attributes_files_and_dedupes():
    """analyze_many batches files into one request and tags issues by file."""
    from core.ai_provider import AIProvider

    class P(AIProvider):
        provider_name = "opencode_zen"
        def __init__(self):
            self.calls = 0
        def _normalize_model(self):
            return "big-pickle"
        def complete(self, system, user_message, max_tokens=4000):
            self.calls += 1
            return ('{"issues": ['
                    '{"file": "a.py", "title": "X", "line": 1},'
                    '{"file": "b.py", "title": "Y"},'
                    '{"file": "missing.py", "title": "Z"}], '
                    '"overall_quality": "GOOD"}')

    provider = P()
    files = [{"path": "a.py", "content": "a"}, {"path": "b.py", "content": "b"}]
    result = provider.analyze_many(files)
    assert provider.calls == 1  # exactly one batched request
    assert result["issues"][0]["file"] == "a.py"
    assert result["issues"][1]["file"] == "b.py"
    # Unknown file falls back to the last provided file.
    assert result["issues"][2]["file"] == "b.py"
