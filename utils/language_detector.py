"""
Language detection and file type handling utilities
"""
from pathlib import Path
from typing import Optional
import re

class LanguageDetector:
    """Detect programming language from code content and file extension"""

    # Language patterns for content-based detection
    LANGUAGE_PATTERNS = {
        "python": [
            r'^\s*import\s+\w+',
            r'^\s*from\s+\w+\s+import',
            r'^\s*def\s+\w+\s*\(',
            r'^\s*class\s+\w+\s*[:\(]',
        ],
        "javascript": [
            r'^\s*function\s+\w+\s*\(',
            r'^\s*const\s+\w+\s*=',
            r'^\s*let\s+\w+\s*=',
            r'^\s*var\s+\w+\s*=',
            r'console\.log\(',
        ],
        "typescript": [
            r'^\s*interface\s+\w+',
            r'^\s*type\s+\w+\s*=',
            r':\s*(string|number|boolean|any)',
        ],
        "java": [
            r'^\s*public\s+class\s+\w+',
            r'^\s*private\s+(static\s+)?[a-zA-Z<>]+\s+\w+',
            r'^\s*import\s+java\.',
        ],
        "c": [
            r'#include\s*<[^>]+>',
            r'^\s*int\s+main\s*\(',
            r'^\s*struct\s+\w+',
        ],
        "cpp": [
            r'#include\s*<iostream>',
            r'std::',
            r'^\s*class\s+\w+\s*{',
        ],
        "csharp": [
            r'^\s*using\s+System',
            r'^\s*namespace\s+\w+',
            r'^\s*public\s+class\s+\w+',
        ],
        "go": [
            r'^\s*package\s+\w+',
            r'^\s*import\s+\(',
            r'^\s*func\s+\w+\s*\(',
        ],
        "rust": [
            r'^\s*fn\s+\w+\s*\(',
            r'^\s*let\s+mut\s+\w+',
            r'^\s*use\s+std::',
        ],
        "php": [
            r'<\?php',
            r'^\s*function\s+\w+\s*\(',
            r'\$\w+\s*=',
        ],
        "ruby": [
            r'^\s*def\s+\w+',
            r'^\s*class\s+\w+',
            r'^\s*require\s+',
        ],
    }

    EXTENSION_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".go": "go",
        ".rs": "rust",
        ".php": "php",
        ".rb": "ruby",
        ".swift": "swift",
        ".kt": "kotlin",
        ".html": "html",
        ".htm": "html",
        ".css": "css",
        ".scss": "css",
        ".sass": "css",
        ".sql": "sql",
        ".sh": "shell",
        ".bash": "shell",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".xml": "xml",
        ".md": "markdown",
    }

    @classmethod
    def detect_from_filename(cls, filename: str) -> str:
        """Detect language from file extension"""
        ext = Path(filename).suffix.lower()
        return cls.EXTENSION_MAP.get(ext, "text")

    @classmethod
    def detect_from_content(cls, code: str) -> Optional[str]:
        """Detect language from code content using regex patterns"""
        if not code or not code.strip():
            return None

        scores = {}
        for language, patterns in cls.LANGUAGE_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, code, re.MULTILINE):
                    score += 1
            if score > 0:
                scores[language] = score

        if scores:
            return max(scores, key=scores.get)
        return None

    @classmethod
    def detect(cls, code: str, filename: Optional[str] = None) -> str:
        """
        Detect language from both filename and content
        Filename takes precedence if available
        """
        if filename:
            lang_from_file = cls.detect_from_filename(filename)
            if lang_from_file != "text":
                return lang_from_file

        lang_from_content = cls.detect_from_content(code)
        if lang_from_content:
            return lang_from_content

        return "text"

    @classmethod
    def is_supported(cls, filename: str) -> bool:
        """Check if file extension is supported"""
        ext = Path(filename).suffix.lower()
        return ext in cls.EXTENSION_MAP

    @classmethod
    def get_language_name(cls, language: str) -> str:
        """Get display name for language"""
        names = {
            "python": "Python",
            "javascript": "JavaScript",
            "typescript": "TypeScript",
            "java": "Java",
            "c": "C",
            "cpp": "C++",
            "csharp": "C#",
            "go": "Go",
            "rust": "Rust",
            "php": "PHP",
            "ruby": "Ruby",
            "swift": "Swift",
            "kotlin": "Kotlin",
            "html": "HTML",
            "css": "CSS",
            "sql": "SQL",
            "shell": "Shell",
            "json": "JSON",
            "yaml": "YAML",
            "xml": "XML",
            "markdown": "Markdown",
            "text": "Plain Text",
        }
        return names.get(language.lower(), language.title())
