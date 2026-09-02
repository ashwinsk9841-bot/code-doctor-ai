"""
Configuration management for Code Doctor AI
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration"""

    # AI Provider Settings
    AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic")
    AI_API_KEY = os.getenv("AI_API_KEY", "")
    AI_MODEL = os.getenv("AI_MODEL", "")

    # OpenAI Settings (alternative)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Application Settings
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    ENABLE_SECURITY_SCAN = os.getenv("ENABLE_SECURITY_SCAN", "true").lower() == "true"
    ENABLE_TEST_GENERATION = os.getenv("ENABLE_TEST_GENERATION", "true").lower() == "true"
    ENABLE_AI_ANALYSIS = os.getenv("ENABLE_AI_ANALYSIS", "true").lower() == "true"

    # Repository scanning limits
    MAX_REPOSITORY_MB = int(os.getenv("MAX_REPOSITORY_MB", "200"))
    MAX_FILES = int(os.getenv("MAX_FILES", "3000"))
    MAX_FILE_ANALYZE_BYTES = int(os.getenv("MAX_FILE_ANALYZE_BYTES", "524288"))  # 512KB

    # Timeouts
    GITHUB_REQUEST_TIMEOUT = int(os.getenv("GITHUB_REQUEST_TIMEOUT", "30"))
    TEST_TIMEOUT_SECONDS = int(os.getenv("TEST_TIMEOUT_SECONDS", "180"))

    # Supported Languages -> extensions
    SUPPORTED_LANGUAGES = {
        "python": [".py"],
        "javascript": [".js", ".jsx", ".mjs", ".cjs"],
        "typescript": [".ts", ".tsx"],
        "java": [".java"],
        "c": [".c", ".h"],
        "cpp": [".cpp", ".hpp", ".cc", ".cxx"],
        "csharp": [".cs"],
        "go": [".go"],
        "rust": [".rs"],
        "php": [".php"],
        "ruby": [".rb"],
        "swift": [".swift"],
        "kotlin": [".kt", ".kts"],
        "html": [".html", ".htm"],
        "css": [".css", ".scss", ".sass", ".less"],
        "sql": [".sql"],
        "shell": [".sh", ".bash", ".zsh"],
        "json": [".json", ".json5"],
        "yaml": [".yaml", ".yml"],
        "toml": [".toml"],
        "xml": [".xml", ".xhtml"],
        "markdown": [".md", ".markdown"],
        "dockerfile": ["dockerfile"],
        "make": ["makefile"],
    }

    # Files / directories always ignored during repository discovery
    IGNORED_DIRS = {
        ".git", "node_modules", "venv", ".venv", "__pycache__",
        "dist", "build", "coverage", ".pytest_cache", ".tox", ".mypy_cache",
        ".idea", ".vscode", "target", ".next", ".nuxt", "vendor",
        "site-packages", "env", ".env", "htmlcov", "bower_components",
        "Pods", ".gradle", ".svn", ".hg", ".cache", "temp", ".eggs",
    }
    IGNORED_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
        ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar", ".exe", ".dll", ".so",
        ".dylib", ".bat", ".cmd", ".ps1", ".vbs", ".jar", ".class", ".o",
        ".a", ".obj", ".pyc", ".pyo", ".woff", ".woff2", ".ttf", ".eot",
        ".mp4", ".mp3", ".avi", ".mov", ".wav", ".bin", ".dat", ".db",
        ".sqlite", ".sqlite3", ".lock", ".map", ".min.js", ".min.css",
        ".eot", ".pem", ".key", ".crt", ".xls", ".xlsx", ".doc", ".docx",
        ".ppt", ".pptx", ".woff", ".lockb", ".tfvars", ".ipynb",
        ".egg", ".whl", ".iso", ".dmg", ".msi", ".db-journal", ".DS_Store",
    }
    # Keep lockfiles out of source scanning but still analyze manifests
    MANIFEST_FILENAMES = {
        "requirements.txt", "pyproject.toml", "package.json", "package-lock.json",
        "yarn.lock", "Pipfile", "Gopkg.toml", "go.mod", "Cargo.toml", "Gemfile",
        "composer.json", "build.gradle", "build.gradle.kts", "pom.xml", "setup.py",
        "conda.yml", "environment.yml", "Podfile", "mix.exs", "pubspec.yaml",
        "vendor.json", "Godeps.json",
    }

    # Issue Categories / Severity
    CATEGORIES = {
        "BUG": "🐛",
        "SECURITY": "🔒",
        "DEPENDENCY": "📦",
        "PERFORMANCE": "⚡",
        "CODE_QUALITY": "💡",
        "CONFIGURATION": "⚙️",
        "TEST": "🧪",
        "OTHER": "📋",
    }
    SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    SEVERITY_ORDER = {s: i for i, s in enumerate(SEVERITIES)}

    # Backwards-compatible alias (previously ISSUE_CATEGORIES w/ severity emojis)
    ISSUE_CATEGORIES = CATEGORIES

    @classmethod
    def validate(cls) -> "tuple[bool, str]":
        """Validate configuration"""
        if cls.AI_PROVIDER not in ("anthropic", "openai", "auto"):
            return False, (
                f"Unknown AI_PROVIDER '{cls.AI_PROVIDER}'. "
                "Supported: anthropic, openai, auto."
            )

        if not cls.AI_API_KEY and not cls.OPENAI_API_KEY:
            return False, (
                "No API key configured. Set AI_API_KEY or OPENAI_API_KEY "
                "in your .env file or Streamlit secrets."
            )

        if cls.AI_PROVIDER == "anthropic" and not cls.AI_API_KEY:
            return False, "Anthropic provider selected but AI_API_KEY not set."

        if cls.AI_PROVIDER == "openai" and not cls.OPENAI_API_KEY:
            return False, "OpenAI provider selected but OPENAI_API_KEY not set."

        return True, "Configuration valid"

    @classmethod
    def get_extensions_for_language(cls, language: str) -> list:
        """Get file extensions for a language"""
        return cls.SUPPORTED_LANGUAGES.get(language.lower(), [])

    @classmethod
    def detect_language_from_extension(cls, filename: str) -> str:
        """Detect language from file extension"""
        name = Path(filename)
        base = name.name.lower().lstrip(".")
        if base == "dockerfile":
            return "dockerfile"
        if base == "makefile":
            return "make"
        ext = name.suffix.lower()
        for lang, extensions in cls.SUPPORTED_LANGUAGES.items():
            if ext in extensions:
                return lang
        return "text"


# Backwards-compatible alias for existing UI/tests
ISSUE_CATEGORIES = dict(Config.CATEGORIES)
SUPPORTED_LANGUAGES = dict(Config.SUPPORTED_LANGUAGES)
