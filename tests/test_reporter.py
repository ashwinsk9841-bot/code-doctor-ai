"""Tests for reporter"""
from core.reporter import Reporter
from core.analyzer import CodeAnalyzer
from unittest.mock import Mock


def test_health_score_clean():
    assert Reporter.health_score({"total_issues": 0}) == 95.0


def test_health_score_with_issues():
    s = {"total_issues": 10, "critical": 2, "high": 3, "medium": 5, "low": 0, "info": 0}
    score = Reporter.health_score(s)
    assert 0 <= score <= 100


def test_generate_markdown_report():
    provider = Mock()
    provider.analyze_code.return_value = {"issues": [], "overall_quality": "GOOD"}
    analyzer = CodeAnalyzer(provider)
    summary = {
        "total_issues": 0, "critical": 0, "high": 0, "medium": 0, "low": 0,
        "info": 0, "security_issues": 0, "dependency_issues": 0, "ai_issues": 0,
        "lines_of_code": 10, "files_scanned": 1, "file_total": 1, "complexity": 1,
    }
    analysis = {
        "overall_summary": summary,
        "issues": [],
        "files_scanned": 1,
        "file_total": 1,
        "ai_status": "ok",
        "test_result": None,
        "repo": "owner/repo",
    }
    report = Reporter.generate_markdown_report(analysis, repo="owner/repo")
    assert "Executive Summary" in report
    assert "Issue Details" in report
    assert "owner/repo" in report


def test_generate_markdown_report_with_issues():
    analysis = {
        "overall_summary": {
            "total_issues": 1, "critical": 1, "high": 0, "medium": 0, "low": 0,
            "info": 0, "security_issues": 1, "dependency_issues": 0, "ai_issues": 0,
            "lines_of_code": 5, "files_scanned": 1, "file_total": 1, "complexity": 2,
        },
        "issues": [{
            "title": "Hardcoded secret", "category": "SECURITY", "severity": "HIGH",
            "confidence": 0.9, "file": "a.py", "line": 3, "description": "x",
            "evidence": "API_KEY = '****'", "why_it_matters": "y",
            "recommended_fix": "use env", "fixable": True,
            "verification_status": "NOT_VERIFIED",
        }],
        "files_scanned": 1, "file_total": 1, "ai_status": "ok",
        "test_result": {"framework": "pytest", "status": "PASS", "tests": 3,
                        "passed": 3, "failed": 0},
    }
    report = Reporter.generate_markdown_report(analysis)
    assert "Hardcoded secret" in report
    assert "pytest" in report
    assert "PASS" in report


def test_generate_json_report_strips_content():
    analysis = {
        "overall_summary": {"total_issues": 0},
        "files": [{"path": "a.py", "content": "secret", "abs_path": "/tmp/a.py"}],
        "issues": [],
    }
    js = Reporter.generate_json_report(analysis)
    assert "secret" not in js
    assert "a.py" in js
