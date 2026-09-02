"""
Test generation for Code Doctor AI.

Detects the repository's testing framework/package manager where possible,
then generates an appropriate test for a given source file. Also provides
framework detection helpers shared with the test runner.
"""
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from .ai_provider import AIProvider, classify_provider_error

# Map a language to likely test frameworks (in priority order)
FRAMEWORK_HINTS = {
    "python": ["pytest", "unittest"],
    "javascript": ["jest", "vitest", "mocha", "jasmine"],
    "typescript": ["jest", "vitest", "mocha"],
    "java": ["junit", "junit5", "testng"],
    "go": ["go test"],
    "rust": ["cargo test"],
    "ruby": ["rspec", "minitest"],
    "csharp": ["xunit", "nunit", "mstest"],
    "php": ["phpunit"],
}


def detect_package_manager(root: Path) -> Optional[str]:
    for name in ("package.json", "yarn.lock", "pnpm-lock.yaml", "package-lock.json"):
        if (root / name).exists():
            if name == "package.json":
                return "npm" if "lock" not in str(name) else "npm"
            if name == "yarn.lock":
                return "yarn"
            if name == "pnpm-lock.yaml":
                return "pnpm"
    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
        return "pip"
    if (root / "go.mod").exists():
        return "go"
    return None


def detect_test_framework(root: Path, language: str) -> str:
    """Detect the most likely test framework available in the repo."""
    lang = (language or "").lower()

    # Inspect config files for strong signals.
    if (root / "pyproject.toml").exists():
        text = _read(root / "pyproject.toml")
        if "pytest" in text:
            return "pytest"
    if (root / "package.json").exists():
        text = _read(root / "package.json")
        for fw in ("vitest", "jest", "mocha", "jasmine"):
            if fw in text:
                return fw
    if (root / "pom.xml").exists():
        return "junit"
    if (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
        return "junit"
    if (root / "Cargo.toml").exists():
        return "cargo test"
    if (root / "go.mod").exists():
        return "go test"

    hints = FRAMEWORK_HINTS.get(lang, [])
    return hints[0] if hints else "unknown"


class TestGenerator:
    """Generate a test for a source file."""

    __test__ = False  # not a pytest test collection

    def __init__(self, ai_provider: Optional[AIProvider] = None):
        self.ai_provider = ai_provider

    def generate_for_file(self, source_content: str, language: str,
                          framework: str, file_path: str = "") -> Dict[str, Any]:
        if self.ai_provider is None:
            return {"success": False, "error": "AI provider not configured."}
        try:
            test_code = self.ai_provider.generate_tests(source_content, language, framework)
            return {
                "success": True,
                "test_code": test_code,
                "framework": framework,
                "test_count": self._count_tests(test_code, language),
                "file_path": file_path,
            }
        except Exception as e:
            msg, _ = classify_provider_error(e)
            return {"success": False, "error": msg}

    def generate_tests(self, code: str, language: str) -> dict:
        """Backwards-compatible single-snippet test generator."""
        if self.ai_provider is None:
            return {"success": False, "error": "AI provider not configured.",
                    "test_code": "", "test_count": 0}
        fw = FRAMEWORK_HINTS.get((language or "").lower(), ["unknown"])[0]
        try:
            test_code = self.ai_provider.generate_tests(code, language, fw)
            test_code = self._clean_code_response(test_code, language)
            return {
                "success": True,
                "test_code": test_code,
                "framework": fw,
                "test_count": self._count_tests(test_code, language),
                "explanation": f"Generated tests using {fw}.",
            }
        except Exception as e:
            msg, _ = classify_provider_error(e)
            return {"success": False, "error": msg, "test_code": "", "test_count": 0}

    def _clean_code_response(self, response: str, language: str) -> str:
        import re
        m = re.search(r"```(?:[a-zA-Z0-9_+-]*)\s*\n(.*?)```", response, re.DOTALL)
        return m.group(1).strip() if m else response.strip()

    def _count_tests(self, test_code: str, language: str) -> int:
        patterns = {
            "python": [r"def test_\w+", r"class Test\w+"],
            "javascript": [r"\bit\s*\(", r"\btest\s*\(", r"\bdescribe\s*\("],
            "typescript": [r"\bit\s*\(", r"\btest\s*\(", r"\bdescribe\s*\("],
            "java": [r"@Test"],
            "go": [r"func Test\w+"],
            "rust": [r"#\[test\]"],
        }
        lang = (language or "").lower()
        count = 0
        for pattern in patterns.get(lang, []):
            count += len(re.findall(pattern, test_code))
        return max(count, 1)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
