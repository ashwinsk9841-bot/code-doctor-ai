"""Tests for repository ingestion"""
import pytest
from core.repository import Repository, RepositoryError


def test_parse_url_valid():
    parsed = Repository.parse_url("https://github.com/user/repo")
    assert parsed == {"owner": "user", "repo": "repo", "branch": None}


def test_parse_url_with_git_suffix():
    parsed = Repository.parse_url("https://github.com/user/repo.git")
    assert parsed["owner"] == "user"
    assert parsed["repo"] == "repo"


def test_parse_url_invalid():
    parsed = Repository.parse_url("https://gitlab.com/user/repo")
    assert "error" in parsed


def test_parse_url_empty():
    parsed = Repository.parse_url("   ")
    assert "error" in parsed


def test_check_exists_invalid():
    result = Repository.check_exists("not-a-url")
    assert result["success"] is False


def test_is_within(tmp_path):
    repo = Repository(tmp_path, "o", "r", "main")
    inside = tmp_path / "sub" / "file.py"
    inside.parent.mkdir()
    inside.touch()
    assert repo.is_within(inside) is True
    outside = tmp_path.parent / "other.py"
    outside.touch()
    assert repo.is_within(outside) is False
