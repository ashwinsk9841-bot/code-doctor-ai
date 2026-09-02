"""
File handling utilities for Code Doctor AI
"""
from pathlib import Path
from typing import Optional, Tuple
import mimetypes

class FileHandler:
    """Handle file uploads and validation"""

    ALLOWED_EXTENSIONS = {
        ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".h",
        ".cpp", ".hpp", ".cc", ".cxx", ".cs", ".go", ".rs", ".php",
        ".rb", ".swift", ".kt", ".html", ".htm", ".css", ".scss",
        ".sass", ".sql", ".sh", ".bash", ".json", ".yaml", ".yml",
        ".xml", ".md", ".txt"
    }

    DANGEROUS_EXTENSIONS = {
        ".exe", ".dll", ".so", ".dylib", ".bat", ".cmd", ".ps1",
        ".vbs", ".jar", ".app", ".deb", ".rpm", ".msi", ".dmg"
    }

    @classmethod
    def validate_file(cls, filename: str, file_size: int, max_size_bytes: int) -> Tuple[bool, str]:
        """
        Validate uploaded file
        Returns: (is_valid, error_message)
        """
        if not filename:
            return False, "No filename provided"

        # Sanitize filename
        safe_filename = cls.sanitize_filename(filename)
        if not safe_filename:
            return False, "Invalid filename"

        # Check extension
        ext = Path(filename).suffix.lower()

        if ext in cls.DANGEROUS_EXTENSIONS:
            return False, f"File type {ext} is not allowed for security reasons"

        if ext not in cls.ALLOWED_EXTENSIONS:
            return False, f"File type {ext} is not supported. Supported types: {', '.join(sorted(cls.ALLOWED_EXTENSIONS))}"

        # Check file size
        if file_size > max_size_bytes:
            max_mb = max_size_bytes / (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            return False, f"File too large ({actual_mb:.2f}MB). Maximum size: {max_mb:.0f}MB"

        return True, ""

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Sanitize filename to prevent path traversal attacks
        """
        # Remove path components
        filename = Path(filename).name

        # Remove dangerous characters
        dangerous_chars = ['..', '/', '\\', '\x00', '<', '>', ':', '"', '|', '?', '*']
        for char in dangerous_chars:
            filename = filename.replace(char, '_')

        # Limit length
        if len(filename) > 255:
            stem = Path(filename).stem[:200]
            suffix = Path(filename).suffix
            filename = f"{stem}{suffix}"

        return filename.strip()

    @classmethod
    def read_file_safely(cls, file_content: bytes, filename: str) -> Tuple[bool, str, str]:
        """
        Safely read file content and decode to string
        Returns: (success, content_or_error, detected_encoding)
        """
        encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'ascii']

        for encoding in encodings_to_try:
            try:
                content = file_content.decode(encoding)
                return True, content, encoding
            except (UnicodeDecodeError, AttributeError):
                continue

        return False, "Unable to decode file. Please ensure it's a text file with valid encoding.", "unknown"

    @classmethod
    def get_mime_type(cls, filename: str) -> str:
        """Get MIME type for file"""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "text/plain"

    @classmethod
    def is_text_file(cls, filename: str) -> bool:
        """Check if file is a text file"""
        mime_type = cls.get_mime_type(filename)
        return mime_type.startswith('text/') or mime_type == 'application/json'

    @classmethod
    def format_file_size(cls, size_bytes: int) -> str:
        """Format file size for display"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    @classmethod
    def fetch_from_github(cls, url: str) -> dict:
        """
        Fetch code from GitHub URL
        Returns: dict with success, content, filename, language
        """
        import re
        import urllib.request
        import urllib.error

        result = {"success": False, "content": "", "filename": "", "language": ""}

        # Parse GitHub URL
        # https://github.com/user/repo/blob/branch/path/to/file.py
        pattern = r'github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)'
        match = re.search(pattern, url)

        if not match:
            result["error"] = "Invalid GitHub URL format. Expected: https://github.com/user/repo/blob/branch/path/file"
            return result

        user, repo, branch, filepath = match.groups()

        # Convert to raw URL
        raw_url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{filepath}"

        try:
            with urllib.request.urlopen(raw_url, timeout=10) as response:
                content_bytes = response.read()

            # Decode content
            success, content, _ = cls.read_file_safely(content_bytes, filepath)
            if not success:
                result["error"] = content
                return result

            filename = filepath.split('/')[-1]
            from config import Config
            language = Config.detect_language_from_extension(filename)

            result["success"] = True
            result["content"] = content
            result["filename"] = filename
            result["language"] = language

        except urllib.error.HTTPError as e:
            if e.code == 404:
                result["error"] = "File not found on GitHub. Check the URL and branch name."
            else:
                result["error"] = f"HTTP error {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            result["error"] = f"Network error: {str(e.reason)}"
        except Exception as e:
            result["error"] = f"Failed to fetch: {str(e)}"

        return result
