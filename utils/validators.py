"""
Input validation utilities for Code Doctor AI.
"""
import html
import re
from typing import Tuple
from urllib.parse import urlparse

from config import Config


class Validators:
    """Input validation for Code Doctor AI."""

    # ------------------------------------------------------------------
    # GitHub URL validation
    # ------------------------------------------------------------------
    @staticmethod
    def validate_github_repo_url(url: str) -> Tuple[bool, str]:
        """Validate a GitHub repository URL (owner/repo without /blob)."""
        url = (url or "").strip()
        if not url:
            return False, "No GitHub URL provided."
        if not re.match(r"^https?://(?:www\.)?github\.com/", url, re.IGNORECASE):
            return False, "Not a GitHub URL. Expected: https://github.com/<owner>/<repo>"
        path = urlparse(url).path.strip("/").rstrip(".git")
        parts = path.split("/")
        if len(parts) < 2 or not all(parts) or any("/" in p for p in parts[:2]):
            return False, "Invalid repository path. Expected owner/repo."
        if len(parts) > 2:
            return False, "Repository URL should not include a file or /blob path."
        return True, ""

    @staticmethod
    def validate_github_url(url: str) -> Tuple[bool, str]:
        """Compat alias: accept repository and raw/raw/blob URLs."""
        url = (url or "").strip()
        if not url:
            return False, "No GitHub URL provided."
        if not re.match(r"^https?://(?:www\.)?github\.com/", url, re.IGNORECASE):
            return False, "Not a GitHub URL."
        parsed = urlparse(url)
        path = parsed.path.strip("/").rstrip(".git")
        parts = path.split("/")
        if len(parts) < 2:
            return False, "Invalid GitHub path."
        if parts[0] == "raw" or parts[1] == "raw":
            return True, ""
        # blob / tree paths are still repository URLs
        return True, ""

    # ------------------------------------------------------------------
    # File size
    # ------------------------------------------------------------------
    @staticmethod
    def validate_file_size(size_bytes: int) -> bool:
        """Return True if size is within the configured limit."""
        return size_bytes <= Config.MAX_FILE_SIZE_BYTES

    # ------------------------------------------------------------------
    # Code validation
    # ------------------------------------------------------------------
    @staticmethod
    def validate_code(code: str, max_length: int = 100000) -> Tuple[bool, str]:
        """Validate code input; returns (is_valid, message)."""
        if not code or not code.strip():
            return False, "Code cannot be empty"
        if len(code) > max_length:
            return False, f"Code too long ({len(code)} characters). Maximum: {max_length}"
        if len(code.encode("utf-8")) > Config.MAX_FILE_SIZE_BYTES:
            mb = Config.MAX_FILE_SIZE_MB
            return False, f"Code exceeds maximum size of {mb}MB"
        return True, ""

    # alias used by older callers
    validate_code_input = validate_code

    # ------------------------------------------------------------------
    # Language validation
    # ------------------------------------------------------------------
    @staticmethod
    def validate_language(language: str, supported_languages: list = None) -> Tuple[bool, str]:
        """Validate a language identifier."""
        if not language:
            return False, "No language provided"
        langs = supported_languages or list(Config.SUPPORTED_LANGUAGES.keys())
        if language.lower() in [str(l).lower() for l in langs]:
            return True, ""
        return False, f"Language '{language}' is not supported"

    def validate_language_legacy(self, *args):
        return Validators.validate_language(*args)

    # ------------------------------------------------------------------
    # Sanitization
    # ------------------------------------------------------------------
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Sanitize user input. HTML-escapes markup, strips null bytes."""
        if not text:
            return ""
        text = text.replace("\x00", "")
        text = html.escape(text)  # turns <script> into &lt;script&gt;
        return text.strip()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        from utils.file_handler import FileHandler
        return FileHandler.sanitize_filename(filename)

    # ------------------------------------------------------------------
    # Token estimation
    # ------------------------------------------------------------------
    @staticmethod
    def estimate_tokens(text: str) -> int:
        return len(text) // 4

    @staticmethod
    def should_truncate(text: str, max_tokens: int = 8000) -> Tuple[bool, int]:
        estimated = Validators.estimate_tokens(text)
        return estimated > max_tokens, estimated

    @staticmethod
    def truncate_code_smart(code: str, max_tokens: int = 8000) -> Tuple[str, bool]:
        estimated_tokens = Validators.estimate_tokens(code)
        if estimated_tokens <= max_tokens:
            return code, False
        max_chars = max_tokens * 4
        lines = code[:max_chars].split("\n")
        truncated = "\n".join(lines[:-1])
        truncated += "\n\n# ... (code truncated due to length) ..."
        return truncated, True
