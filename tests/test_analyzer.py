"""Tests for analyzer module"""
from unittest.mock import Mock
from core.analyzer import CodeAnalyzer
from core.security_scanner import SecurityScanner


def make_provider():
    provider = Mock()
    provider.analyze_code.return_value = {"issues": [], "overall_quality": "GOOD"}
    provider.explain_code.return_value = "This code defines a function."
    return provider


def test_analyze_full_success():
    analyzer = CodeAnalyzer(make_provider())
    result = analyzer.analyze_full("def test(): pass", "python", enable_security=False)
    assert result["success"] is True
    assert "static_analysis" in result
    assert "overall_summary" in result


def test_analyze_full_with_security():
    analyzer = CodeAnalyzer(make_provider())
    result = analyzer.analyze_full("password = 'admin123'", "python", enable_security=True)
    assert result["success"] is True
    assert "security_scan" in result
    assert result["overall_summary"]["total_issues"] >= 0


def test_analyze_full_catches_syntax_error():
    analyzer = CodeAnalyzer(make_provider())
    result = analyzer.analyze_full("def broken(:\n  pass", "python", enable_security=False)
    issues = result["issues"]
    assert any(i["category"] == "BUG" and i["severity"] == "HIGH" for i in issues)


def test_explain_code():
    provider = make_provider()
    analyzer = CodeAnalyzer(provider)
    explanation = analyzer.explain_code("def test(): pass", "python")
    assert explanation


def test_analyze_repository(tmp_path):
    (tmp_path / "mod.py").write_text("import os\nAPI_KEY = 'sk-abc123'\ndef f():\n    return 1\n")
    analyzer = CodeAnalyzer(make_provider())
    result = analyzer.analyze_repository(tmp_path, "owner/repo", enable_security=True)
    assert result["success"] is True
    assert result["files_scanned"] >= 1
    assert result["overall_summary"]["total_issues"] >= 0
    assert any(i["severity"] == "HIGH" for i in result["security_issues"])


def test_language_breakdown(tmp_path):
    (tmp_path / "a.py").write_text("print(1)")
    (tmp_path / "b.js").write_text("console.log(1)")
    analyzer = CodeAnalyzer(make_provider())
    result = analyzer.analyze_repository(tmp_path, "o/r", enable_security=False, enable_ai=False)
    breakdown = result["language_summary"]
    assert breakdown.get("python", 0) >= 1
