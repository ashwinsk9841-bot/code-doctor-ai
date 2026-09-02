"""Tests for validators module"""
import pytest
from utils.validators import Validators


def test_validate_file_size_valid():
    """Test file size validation - valid size"""
    size_1mb = 1 * 1024 * 1024
    assert Validators.validate_file_size(size_1mb) == True


def test_validate_file_size_invalid():
    """Test file size validation - exceeds limit"""
    from config import Config
    size_too_large = Config.MAX_FILE_SIZE_BYTES + 1
    assert Validators.validate_file_size(size_too_large) == False


def test_validate_code_empty():
    """Test code validation - empty code"""
    assert Validators.validate_code("") == (False, "Code cannot be empty")
    assert Validators.validate_code("   ") == (False, "Code cannot be empty")


def test_validate_code_valid():
    """Test code validation - valid code"""
    code = "print('hello')"
    is_valid, msg = Validators.validate_code(code)
    assert is_valid
    assert msg == ""


def test_validate_language_valid():
    """Test language validation - supported language"""
    assert Validators.validate_language("python") == (True, "")
    assert Validators.validate_language("javascript") == (True, "")


def test_validate_language_invalid():
    """Test language validation - unsupported language"""
    is_valid, msg = Validators.validate_language("cobol")
    assert not is_valid
    assert "not supported" in msg.lower()


def test_sanitize_input_xss():
    """Test input sanitization - XSS attempts"""
    malicious = "<script>alert('xss')</script>"
    sanitized = Validators.sanitize_input(malicious)
    assert "<script>" not in sanitized
    assert "&lt;script&gt;" in sanitized


def test_sanitize_input_sql():
    """Test input sanitization - SQL injection attempts are HTML-escaped"""
    malicious = "'; DROP TABLE users; --"
    sanitized = Validators.sanitize_input(malicious)
    # HTML escaping keeps the payload inert while preserving the text
    assert "DROP" in sanitized
    assert "<" not in sanitized


def test_validate_github_url_valid():
    """Test GitHub URL validation - valid URLs"""
    valid_urls = [
        "https://github.com/user/repo/blob/main/file.py",
        "https://github.com/org/project/blob/develop/src/app.js"
    ]
    for url in valid_urls:
        is_valid, msg = Validators.validate_github_url(url)
        assert is_valid, f"Failed for {url}: {msg}"


def test_validate_github_url_invalid():
    """Test GitHub URL validation - invalid URLs"""
    invalid_urls = [
        "https://gitlab.com/user/repo/file.py",
        "not-a-url",
        "https://github.com/incomplete"
    ]
    for url in invalid_urls:
        is_valid, msg = Validators.validate_github_url(url)
        assert not is_valid
