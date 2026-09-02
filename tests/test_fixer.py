"""Tests for fixer module"""
import pytest
from unittest.mock import Mock
from core.fixer import CodeFixer


@pytest.fixture
def mock_ai_provider():
    provider = Mock()
    provider.fix_code.return_value = "def test():\n    return True"
    return provider


def test_fix_code_no_issues(mock_ai_provider):
    fixer = CodeFixer(mock_ai_provider)
    code = "def test(): pass"
    result = fixer.fix_code(code, "python", [])
    assert result["success"] is True
    assert result["fixed_code"] == code


def test_fix_code_secret_replacement():
    """Deterministic replacement of hardcoded credentials."""
    fixer = CodeFixer(None)
    code = 'API_KEY = "sk-1234567890abcdefg"'
    result = fixer.fix_code(code, "python", [{"category": "SECURITY", "title": "Hardcoded credential"}])
    assert result["success"] is True
    assert "os.environ" in result["fixed_code"]
    assert "sk-1234567890abcdefg" not in result["fixed_code"]


def test_fix_code_with_ai(mock_ai_provider):
    fixer = CodeFixer(mock_ai_provider)
    result = fixer.fix_code("def test(): pass", "python",
                            [{"category": "BUG", "title": "Missing return", "line": 1}])
    assert result["success"] is True
    assert result["fixed_code"]


def test_replace_secret_reads_env():
    from core.fixer import _replace_secret_assignment
    new = _replace_secret_assignment('PASSWORD = "hunter2"')
    assert "os.environ" in new
    assert "hunter2" not in new


def test_apply_security_fix_to_repo(tmp_path):
    code = 'TOKEN = "ghp_1234567890abcdefghij"\nprint(TOKEN)'
    f = tmp_path / "config.py"
    f.write_text(code)
    record = {"path": "config.py", "language": "python", "content": code}
    issue = {
        "file": "config.py", "line": 1,
        "title": "Hardcoded TOKEN", "source": "security",
    }
    fixer = CodeFixer(None)
    result = fixer.apply_fix_to_repo(tmp_path, issue, {"config.py": record})
    assert result["applied"] is True
    new_content = f.read_text()
    assert "ghp_1234567890abcdefghij" not in new_content
    assert "os.environ" in new_content


def test_unsafe_path_rejected(tmp_path):
    fixer = CodeFixer(None)
    record = {"path": "config.py"}
    issue = {"file": "../../etc/passwd", "line": 1, "title": "x", "source": "security"}
    result = fixer.apply_fix_to_repo(tmp_path, issue, record)
    assert result["applied"] is False
    assert "unsafe" in result["error"].lower() or "missing" in result["error"].lower()
