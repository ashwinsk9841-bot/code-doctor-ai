"""
Configuration management for Code Doctor AI

Reads configuration from (in order of precedence):
1. Streamlit secrets (st.secrets) — used on Streamlit Community Cloud
2. Environment variables — used in CI / manual deployment
3. .env file (via python-dotenv) — used for local development
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root regardless of the current working directory.
_PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    """Read a configuration value from the environment."""
    return os.getenv(name, default)


class Config:
    """Application configuration"""

    # AI Provider Settings
    AI_PROVIDER = _env("AI_PROVIDER", "gemini")
    AI_API_KEY = _env("AI_API_KEY", "")
    AI_MODEL = _env("AI_MODEL", "")

    # Google Gemini Settings (default provider)
    GEMINI_API_KEY = _env("GEMINI_API_KEY", "")
    GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-3.5-flash-lite")

    # OpenAI Settings (alternative)
    OPENAI_API_KEY = _env("OPENAI_API_KEY", "")
    OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o")

    # Default models per provider (used when AI_MODEL / OPENAI_MODEL are empty)
    _DEFAULT_MODELS = {
        "anthropic": "claude-sonnet-4-20250514",
        "openai": "gpt-4o",
        "gemini": "gemini-3.5-flash-lite",
    }

    # AI request timeouts & rate-limit retry
    AI_REQUEST_TIMEOUT = int(os.getenv("AI_REQUEST_TIMEOUT", "120"))
    AI_RETRY_MAX = int(os.getenv("AI_RETRY_MAX", "5"))
    AI_RETRY_INITIAL_DELAY = float(os.getenv("AI_RETRY_INITIAL_DELAY", "2.0"))
    AI_RETRY_BACKOFF = float(os.getenv("AI_RETRY_BACKOFF", "2.0"))

    # Whether load_from_secrets() has already been called
    _secrets_loaded = False

    @classmethod
    def load_from_secrets(cls) -> None:
        """Overlay Streamlit secrets onto Config attributes.

        Safe to call even outside a running Streamlit app — it simply returns
        without doing anything when ``st.secrets`` is unavailable (e.g. in
        tests or plain Python scripts).
        """
        if cls._secrets_loaded:
            return
        cls._secrets_loaded = True
        try:
            import streamlit as st
            if not st.secrets:
                return
            _secrets = st.secrets
        except Exception:
            return

        secret_map = {
            "AI_PROVIDER": "AI_PROVIDER",
            "AI_API_KEY": "AI_API_KEY",
            "AI_MODEL": "AI_MODEL",
            "GEMINI_API_KEY": "GEMINI_API_KEY",
            "GEMINI_MODEL": "GEMINI_MODEL",
            "OPENAI_API_KEY": "OPENAI_API_KEY",
            "OPENAI_MODEL": "OPENAI_MODEL",
        }
        for secret_key, attr in secret_map.items():
            try:
                if secret_key in st.secrets:
                    value = str(st.secrets[secret_key]).strip()
                    if value:
                        setattr(cls, attr, value)
            except Exception:
                continue

    @classmethod
    def effective_model(cls, provider: str = "") -> str:
        """Return the model that will actually be used for *provider*."""
        provider = (provider or cls.AI_PROVIDER).lower()
        if provider == "gemini":
            return (cls.GEMINI_MODEL or cls.AI_MODEL
                    or cls._DEFAULT_MODELS.get("gemini", "gemini-3.5-flash-lite"))
        if provider == "openai":
            return cls.OPENAI_MODEL or cls.AI_MODEL or cls._DEFAULT_MODELS.get("openai", "gpt-4o")
        return cls.AI_MODEL or cls._DEFAULT_MODELS.get("anthropic", "claude-sonnet-4-20250514")

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
        """Validate configuration.  Returns (is_valid, message)."""
        cls.load_from_secrets()

        if cls.AI_PROVIDER not in ("anthropic", "openai", "gemini", "auto"):
            return False, (
                f"Unknown AI_PROVIDER '{cls.AI_PROVIDER}'. "
                "Supported values: gemini, anthropic, openai, auto."
            )

        provider = cls.AI_PROVIDER.lower()

        if provider in ("gemini", "auto") and cls.GEMINI_API_KEY:
            return True, "Configuration valid."

        if provider in ("anthropic", "auto") and cls.AI_API_KEY:
            return True, "Configuration valid."

        if provider in ("openai", "auto") and cls.OPENAI_API_KEY:
            return True, "Configuration valid."

        # No usable key found
        return False, (
            "No API key configured. Add **GEMINI_API_KEY** (recommended), "
            "**AI_API_KEY** (Anthropic), or **OPENAI_API_KEY** (OpenAI) to "
            "your Streamlit secrets or to your local `.env` file."
        )

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
