"""Tests for config module"""
import pytest
import os
from config import Config


@pytest.fixture(autouse=True)
def _reset_secrets_loaded():
    """Each test starts with a fresh secrets-load state."""
    Config._secrets_loaded = False
    yield
    Config._secrets_loaded = False


def test_supported_languages():
    """Test supported languages configuration"""
    assert "python" in Config.SUPPORTED_LANGUAGES
    assert ".py" in Config.SUPPORTED_LANGUAGES["python"]
    assert "javascript" in Config.SUPPORTED_LANGUAGES
    assert ".js" in Config.SUPPORTED_LANGUAGES["javascript"]


def test_detect_language_from_extension():
    """Test language detection from file extension"""
    assert Config.detect_language_from_extension("test.py") == "python"
    assert Config.detect_language_from_extension("app.js") == "javascript"
    assert Config.detect_language_from_extension("main.go") == "go"
    assert Config.detect_language_from_extension("file.unknown") == "text"


def test_get_extensions_for_language():
    """Test getting extensions for a language"""
    py_exts = Config.get_extensions_for_language("python")
    assert ".py" in py_exts

    js_exts = Config.get_extensions_for_language("javascript")
    assert ".js" in js_exts
    assert ".jsx" in js_exts


def test_issue_categories():
    """Test issue categories configuration"""
    categories = Config.ISSUE_CATEGORIES
    for cat in ("BUG", "SECURITY", "DEPENDENCY", "PERFORMANCE",
                "CODE_QUALITY", "CONFIGURATION", "TEST", "OTHER"):
        assert cat in categories

    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
        assert sev in Config.SEVERITIES


def test_validate_with_api_key(monkeypatch):
    """Test config validation with API key"""
    monkeypatch.setattr(Config, "AI_API_KEY", "test-key")
    monkeypatch.setattr(Config, "AI_PROVIDER", "anthropic")

    is_valid, message = Config.validate()
    assert is_valid
    assert "valid" in message.lower()


def test_validate_without_api_key(monkeypatch):
    """Test config validation without API key"""
    monkeypatch.setattr(Config, "AI_PROVIDER", "auto")
    monkeypatch.setattr(Config, "AI_API_KEY", "")
    monkeypatch.setattr(Config, "OPENAI_API_KEY", "")
    monkeypatch.setattr(Config, "OPENCODE_ZEN_API_KEY", "")

    is_valid, message = Config.validate()
    assert not is_valid
    assert "api key" in message.lower()


def test_effective_model_defaults(monkeypatch):
    """effective_model returns sensible defaults when no model is configured."""
    monkeypatch.setattr(Config, "AI_PROVIDER", "anthropic")
    monkeypatch.setattr(Config, "AI_MODEL", "")
    monkeypatch.setattr(Config, "OPENAI_MODEL", "")
    assert Config.effective_model("anthropic") == "claude-sonnet-4-20250514"
    assert Config.effective_model("openai") == "gpt-4o"
    # Explicit model takes precedence
    monkeypatch.setattr(Config, "AI_MODEL", "claude-x")
    assert Config.effective_model("anthropic") == "claude-x"


def test_effective_model_openai_precedence(monkeypatch):
    """OPENAI_MODEL beats a generic AI_MODEL for the openai provider."""
    monkeypatch.setattr(Config, "OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setattr(Config, "AI_MODEL", "gpt-4-turbo")
    assert Config.effective_model("openai") == "gpt-4o-mini"
    # When OPENAI_MODEL is empty, fall back to the generic model
    monkeypatch.setattr(Config, "OPENAI_MODEL", "")
    assert Config.effective_model("openai") == "gpt-4-turbo"


def test_load_from_secrets_is_safe_outside_streamlit():
    """Calling load_from_secrets with no Streamlit secrets must not raise."""
    Config.load_from_secrets()  # should not raise even without secrets.toml
    assert Config._secrets_loaded is True


def test_validate_openai_with_key(monkeypatch):
    """OpenAI provider is valid when OPENAI_API_KEY is set."""
    monkeypatch.setattr(Config, "AI_PROVIDER", "openai")
    monkeypatch.setattr(Config, "AI_API_KEY", "")
    monkeypatch.setattr(Config, "OPENAI_API_KEY", "sk-test")
    is_valid, _ = Config.validate()
    assert is_valid


def test_default_provider_is_opencode_zen(monkeypatch):
    """OpenCode Zen is the code-level default provider (free, no paid credits)."""
    import importlib
    import config as cfg
    import dotenv
    # Neutralize any ambient AI_PROVIDER env var / .env override so we assert the
    # code-level default. Patch the underlying dotenv loader so the reload's
    # `from dotenv import load_dotenv` picks up the stub (no .env re-read).
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda **kw: None)
    importlib.reload(cfg)
    assert cfg.Config.AI_PROVIDER == "opencode_zen"


def test_opencode_zen_default_model():
    """OpenCode Zen defaults to the free big-pickle model."""
    assert Config.OPENCODE_ZEN_MODEL == "big-pickle"


def test_effective_model_opencode_zen(monkeypatch):
    """effective_model('opencode_zen') uses OPENCODE_ZEN_MODEL, then big-pickle."""
    monkeypatch.setattr(Config, "OPENCODE_ZEN_MODEL", "")
    monkeypatch.setattr(Config, "AI_MODEL", "")
    assert Config.effective_model("opencode_zen") == "big-pickle"
    # Explicit zen model wins
    monkeypatch.setattr(Config, "OPENCODE_ZEN_MODEL", "mimo-v2.5-free")
    assert Config.effective_model("opencode_zen") == "mimo-v2.5-free"
    # Falls back to the generic AI_MODEL if zen model empty
    monkeypatch.setattr(Config, "OPENCODE_ZEN_MODEL", "")
    monkeypatch.setattr(Config, "AI_MODEL", "gpt-4-turbo")
    assert Config.effective_model("opencode_zen") == "gpt-4-turbo"


def test_validate_opencode_zen_with_key(monkeypatch):
    """OpenCode Zen provider is valid when OPENCODE_ZEN_API_KEY is set."""
    monkeypatch.setattr(Config, "AI_PROVIDER", "opencode_zen")
    monkeypatch.setattr(Config, "OPENCODE_ZEN_API_KEY", "sk-zen-test")
    monkeypatch.setattr(Config, "AI_API_KEY", "")
    monkeypatch.setattr(Config, "OPENAI_API_KEY", "")
    is_valid, _ = Config.validate()
    assert is_valid


def test_validate_unknown_provider(monkeypatch):
    """Unknown providers are rejected."""
    monkeypatch.setattr(Config, "AI_PROVIDER", "bogus")
    is_valid, message = Config.validate()
    assert not is_valid
    assert "opencode_zen" in message
