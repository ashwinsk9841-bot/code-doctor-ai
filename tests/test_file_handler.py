"""Tests for file handler module"""
import pytest
from utils.file_handler import FileHandler


def test_sanitize_filename():
    """Test filename sanitization"""
    assert FileHandler.sanitize_filename("test.py") == "test.py"
    # Path traversal components must be stripped (disallowed on Windows)
    assert ".." not in FileHandler.sanitize_filename("../../../etc/passwd")
    assert FileHandler.sanitize_filename("file<>test.js") == "file__test.js"


def test_validate_file_valid():
    """Test file validation - valid file"""
    is_valid, msg = FileHandler.validate_file("test.py", 1000, 10000)
    assert is_valid
    assert msg == ""


def test_validate_file_too_large():
    """Test file validation - file too large"""
    is_valid, msg = FileHandler.validate_file("test.py", 11000, 10000)
    assert not is_valid
    assert "too large" in msg.lower()


def test_validate_file_dangerous_extension():
    """Test file validation - dangerous extension"""
    is_valid, msg = FileHandler.validate_file("malware.exe", 1000, 10000)
    assert not is_valid
    assert "not allowed" in msg.lower()


def test_validate_file_unsupported_extension():
    """Test file validation - unsupported extension"""
    is_valid, msg = FileHandler.validate_file("data.bin", 1000, 10000)
    assert not is_valid
    assert "not supported" in msg.lower()


def test_read_file_safely_utf8():
    """Test safe file reading - UTF-8"""
    content = "print('hello')".encode('utf-8')
    success, decoded, encoding = FileHandler.read_file_safely(content, "test.py")
    assert success
    assert decoded == "print('hello')"
    assert encoding == "utf-8"


def test_read_file_safely_latin1():
    """Test safe file reading - Latin-1"""
    content = "café".encode('latin-1')
    success, decoded, encoding = FileHandler.read_file_safely(content, "test.txt")
    assert success
    assert "café" in decoded or "caf" in decoded


def test_format_file_size():
    """Test file size formatting"""
    assert "B" in FileHandler.format_file_size(500)
    assert "KB" in FileHandler.format_file_size(2048)
    assert "MB" in FileHandler.format_file_size(2 * 1024 * 1024)


def test_fetch_from_github_invalid_url():
    """Test GitHub fetch with invalid URL"""
    result = FileHandler.fetch_from_github("not-a-github-url")
    assert not result["success"]
    assert "invalid" in result["error"].lower()


def test_is_text_file():
    """Test text file detection"""
    assert FileHandler.is_text_file("test.py") == True
    assert FileHandler.is_text_file("data.json") == True
    assert FileHandler.is_text_file("image.png") == False
