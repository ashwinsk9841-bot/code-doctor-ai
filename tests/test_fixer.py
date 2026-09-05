"""Tests for fixer module"""
from pathlib import Path

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


def test_apply_many_batches_ai_fix_per_file(tmp_path):
    """AI-fixable issues in the same file share a single AI fix_code request."""
    from unittest.mock import Mock
    f = tmp_path / "app.py"
    original = "def f():\n    return 0\n"
    f.write_text(original)

    ai = Mock()
    ai.fix_code.return_value = "def f():\n    return 42\n"

    fixer = CodeFixer(ai)
    issues = [
        {"issue_id": "A", "file": "app.py", "line": 2, "language": "python",
         "source": "parser", "fixable": True, "title": "bad return"},
        {"issue_id": "B", "file": "app.py", "line": 1, "language": "python",
         "source": "parser", "fixable": True, "title": "other"},
    ]
    results = fixer.apply_many_fixes_to_repo(tmp_path, issues, {"app.py": {"path": "app.py"}})
    # One AI call handled both issues from the same file.
    assert ai.fix_code.call_count == 1
    assert all(r["applied"] for r in results)
    assert f.read_text().strip() == "def f():\n    return 42".strip()
    assert {r["issue_id"] for r in results} == {"A", "B"}


def test_apply_many_deterministic_security_per_issue(tmp_path):
    """Security issues are still fixed deterministically (one per issue)."""
    from unittest.mock import Mock
    f = tmp_path / "cfg.py"
    f.write_text('TOKEN = "sk-1234567890abcdefghij"\nprint(TOKEN)')

    ai = Mock()
    fixer = CodeFixer(ai)
    issues = [{"issue_id": "S1", "file": "cfg.py", "line": 1,
               "source": "security", "fixable": True, "title": "Hardcoded TOKEN"}]
    results = fixer.apply_many_fixes_to_repo(tmp_path, issues, {"cfg.py": {"path": "cfg.py"}})
    assert results[0]["applied"] is True
    new = f.read_text()
    assert "sk-1234567890abcdefghij" not in new
    assert "os.environ" in new


def test_apply_fix_repo_root_in_raw_short_name_form():
    """Regression: repo_root may be in raw (8.3 short-name) form, e.g.
    ``C:\\Users\\ASHWIN~1\\...`` from ``tempfile.gettempdir()``, while the
    target file is resolved to the long-name form (``ASHWIN S\\...``).
    ``relative_to`` is lexical, so the fixer must normalise repo_root before
    comparing. Previously this crashed Apply Fix with
    ``ValueError: ... is not in the subpath of ...`` for e.g. SETUP.md."""
    import tempfile
    import uuid

    repo_root = Path(tempfile.gettempdir()) / f"codedoctor_fixer_raw_{uuid.uuid4().hex}"
    repo_root.mkdir(parents=True, exist_ok=True)
    try:
        target = repo_root / "SETUP.md"
        target.write_text('API_KEY = "sk-1234567890abcdefghij"\n')

        issue = {"file": "SETUP.md", "line": 1,
                 "title": "Hardcoded credential", "source": "security"}
        fixer = CodeFixer(None)
        result = fixer.apply_fix_to_repo(repo_root, issue,
                                         {"SETUP.md": {"path": "SETUP.md"}})
        assert result["applied"] is True
        assert "os.environ" in target.read_text()
        backup = (repo_root / ".codedoctor_backups" / "SETUP.md.bak")
        assert backup.exists()
    finally:
        import shutil
        shutil.rmtree(repo_root, ignore_errors=True)


def test_apply_many_fixes_repo_root_in_raw_short_name_form():
    """Same raw-root regression for the batched apply path (reaches _backup via
    _ai_fix_many)."""
    import tempfile
    import uuid
    from unittest.mock import Mock

    repo_root = Path(tempfile.gettempdir()) / f"codedoctor_fixer_raw_many_{uuid.uuid4().hex}"
    repo_root.mkdir(parents=True, exist_ok=True)
    try:
        target = repo_root / "app.py"
        target.write_text("def f():\n    return 0\n")

        ai = Mock()
        ai.fix_code.return_value = "import os\n\ndef f():\n    return 42\n"
        fixer = CodeFixer(ai)
        issues = [{"issue_id": "A", "file": "app.py", "line": 2, "language": "python",
                   "source": "parser", "fixable": True, "title": "dead return"}]
        results = fixer.apply_many_fixes_to_repo(repo_root, issues,
                                                 {"app.py": {"path": "app.py"}})
        assert results[0]["applied"] is True
        assert "return 42" in target.read_text()
        assert (repo_root / ".codedoctor_backups" / "app.py.bak").exists()
    finally:
        import shutil
        shutil.rmtree(repo_root, ignore_errors=True)


def test_apply_fix_accepts_absolute_file_path_inside_repo(tmp_path):
    """An absolute issue file path that resides inside the repo must still be
    mapped safely (normalised against repo_root) rather than rejected."""
    f = tmp_path / "config.py"
    f.write_text('TOKEN = "sk-1234567890abcdefghij"\nprint(TOKEN)')

    issue = {"file": str(f.resolve()), "line": 1,
             "title": "Hardcoded TOKEN", "source": "security"}
    fixer = CodeFixer(None)
    result = fixer.apply_fix_to_repo(tmp_path, issue,
                                     {"config.py": {"path": "config.py"}})
    assert result["applied"] is True
    assert "os.environ" in f.read_text()
