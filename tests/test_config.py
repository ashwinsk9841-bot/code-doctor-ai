"""Tests for config module"""
import pytest
import os
from config import Config


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
    monkeypatch.setattr(Config, "AI_API_KEY", "")
    monkeypatch.setattr(Config, "OPENAI_API_KEY", "")

    is_valid, message = Config.validate()
    assert not is_valid
    assert "api key" in message.lower()
