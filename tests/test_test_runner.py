"""Tests for test runner and verifier"""
from pathlib import Path
from core.test_runner import TestRunner
from core.verifier import Verifier


def test_detect_unknown(tmp_path):
    runner = TestRunner(tmp_path)
    assert runner.framework == "unknown"


def test_detect_pytest(tmp_path):
    (tmp_path / "requirements.txt").write_text("pytest\n")
    runner = TestRunner(tmp_path)
    assert runner.framework == "pytest"


def test_detect_package_json_jest(tmp_path):
    (tmp_path / "package.json").write_text('{"devDependencies": {"jest": "^29"}}')
    runner = TestRunner(tmp_path)
    assert runner.framework == "jest"


def test_runner_blocked_when_unknown(tmp_path):
    runner = TestRunner(tmp_path)
    result = runner.run()
    assert result["status"] == "BLOCKED"


def test_parse_summary_pytest():
    runner = TestRunner(Path("."), "pytest")
    total, passed, failed = runner._parse_summary(
        "pytest", "==== 5 passed, 2 failed in 1.2s ====", "")
    assert passed == 5
    assert failed == 2


def test_verifier_secret_fix_pass(tmp_path):
    verifier = Verifier(tmp_path)
    issue = {
        "title": "Hardcoded TOKEN", "verification_method": "use env",
        "file": "a.py",
    }
    result = verifier.verify_fix(issue, [], run_tests=False)
    assert result["status"] == "PASS"


def test_verifier_not_verified(tmp_path):
    verifier = Verifier(tmp_path)
    issue = {"title": "Some bug", "verification_method": "rerun analysis", "file": "a.py"}
    result = verifier.verify_fix(issue, [], run_tests=False)
    assert result["status"] == "NOT_VERIFIED"


def test_verify_syntax_python():
    verifier = Verifier(Path("."))
    assert verifier.verify_syntax("def f():\n    return 1", "a.py") is True
    assert verifier.verify_syntax("def broken(:", "a.py") is False


def test_verify_syntax_json():
    verifier = Verifier(Path("."))
    assert verifier.verify_syntax('{"a": 1}', "a.json") is True
    assert verifier.verify_syntax("{bad", "a.json") is False
