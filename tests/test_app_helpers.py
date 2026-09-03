"""Tests for app-level helper functions (AI status messaging, back-navigation)."""
import pytest


@pytest.fixture
def app_mod():
    from app import _friendly_ai_status, _back_target
    return _friendly_ai_status, _back_target


def test_friendly_ai_status_rate_limit():
    from app import _friendly_ai_status
    msg = _friendly_ai_status("error:rate_limit:Too Many Requests")
    assert "rate-limited" in msg
    assert "Too Many Requests" in msg


def test_friendly_ai_status_quota():
    from app import _friendly_ai_status
    msg = _friendly_ai_status("error:quota:Insufficient credits")
    assert "quota" in msg or "credits" in msg


def test_friendly_ai_status_generic():
    from app import _friendly_ai_status
    assert "error" in _friendly_ai_status("error:provider:boom")
    # Non-error statuses pass through untouched.
    assert _friendly_ai_status("ok") == "ok"


def test_back_target_prefers_results_views():
    from app import _back_target
    assert _back_target("issues") == "issues"
    assert _back_target("tests") == "tests"
    assert _back_target("dashboard") == "dashboard"


def test_back_target_fallback_dashboard():
    from app import _back_target
    assert _back_target("landing") == "landing"
    assert _back_target("scanning") == "dashboard"
    assert _back_target(None) == "dashboard"
    assert _back_target("report") == "dashboard"
