"""
Test execution for Code Doctor AI.

Detects project type, package manager and test framework, then runs the
appropriate tests in an isolated subprocess with a timeout. Captures exit code,
stdout/stderr, duration and parses failure summaries. Commands are chosen only
from a known-safe allowlist based on detected framework.
"""
import subprocess
import sys
import shutil
import time
from pathlib import Path
from typing import Dict, Any, List, Optional


def _decode_bytes(data: Optional[bytes]) -> str:
    """Decode subprocess bytes to string safely, ignoring unrecognised bytes."""
    if data is None:
        return ""
    for enc in ("utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("latin-1", errors="replace")

from config import Config


class TestRunnerError(Exception):
    __test__ = False


FRAMEWORK_COMMANDS = {
    "pytest": (sys.executable, ["-m", "pytest", "-q", "--tb=short"]),
    "unittest": (sys.executable, ["-m", "unittest", "discover", "-s", ".", "-q"]),
    "jest": ("npx", ["jest", "--ci", "--runInBand"]),
    "vitest": ("npx", ["vitest", "run"]),
    "mocha": ("npx", ["mocha", "--reporter", "spec"]),
    "go test": ("go", ["test", "./..."]),
    "cargo test": ("cargo", ["test"]),
    "junit": ("mvn", ["test"]),
    "phpunit": ("./vendor/bin/phpunit", []),
    "rspec": ("./vendor/bin/rspec", []),
}

# Commands resolved via module (python -m ...) need special availability checks.
MODULE_COMMANDS = {"pytest", "unittest"}


class TestRunner:
    """Detect and run tests for a repository."""

    __test__ = False  # not a pytest test collection

    def __init__(self, root: Path, framework: Optional[str] = None):
        self.root = root
        self.framework = framework or self.detect(root)

    def detect(self, root: Path) -> str:
        if (root / "pyproject.toml").exists():
            text = _read(root / "pyproject.toml")
            if "pytest" in text:
                return "pytest"
        if (root / "pytest.ini").exists() or (root / "setup.cfg").exists() and "pytest" in _read(root / "setup.cfg"):
            return "pytest"
        if (root / "requirements.txt").exists() and "pytest" in _read(root / "requirements.txt"):
            return "pytest"
        if (root / "package.json").exists():
            text = _read(root / "package.json")
            for fw in ("vitest", "jest", "mocha"):
                if fw in text:
                    return fw
        # Heuristic: test files imply a framework even without explicit config.
        py = _find_test_files(root, patterns=("test_*.py", "*_test.py"))
        if py:
            return "pytest"
        if (root / "package.json").exists() and _find_test_files(
                root, patterns=("*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts", "__tests__/*")):
            return "jest"
        if (root / "go.mod").exists():
            return "go test"
        if (root / "Cargo.toml").exists():
            return "cargo test"
        if (root / "pom.xml").exists() or (root / "build.gradle").exists():
            return "junit"
        return "unknown"

    def available(self) -> bool:
        if self.framework == "unknown":
            return False
        if self.framework in MODULE_COMMANDS:
            return _module_available(self.framework)
        command, _ = FRAMEWORK_COMMANDS.get(self.framework, (None, []))
        if command in (None, ""):
            return False
        return shutil.which(command) is not None

    def run(self) -> Dict[str, Any]:
        """Run the detected tests with a timeout. Returns a structured result."""
        if self.framework == "unknown":
            return {
                "status": "BLOCKED", "framework": "unknown",
                "reason": "Could not detect a supported test framework.",
                "tests": 0, "passed": 0, "failed": 0, "exit_code": None,
                "stdout": "", "stderr": "", "duration_ms": 0,
            }

        command, base_args = FRAMEWORK_COMMANDS[self.framework]
        args = [command] + base_args

        if self.framework in MODULE_COMMANDS:
            if not _module_available(self.framework):
                return {
                    "status": "BLOCKED", "framework": self.framework,
                    "reason": f"Module '{self.framework}' not importable (is it installed?).",
                    "tests": 0, "passed": 0, "failed": 0, "exit_code": None,
                    "stdout": "", "stderr": "", "duration_ms": 0,
                }
        elif not shutil.which(command):
            return {
                "status": "BLOCKED", "framework": self.framework,
                "reason": f"Command '{command}' not found on PATH.",
                "tests": 0, "passed": 0, "failed": 0, "exit_code": None,
                "stdout": "", "stderr": "", "duration_ms": 0,
            }

        start = time.time()
        try:
            proc = subprocess.run(
                args,
                cwd=str(self.root),
                capture_output=True,
                timeout=Config.TEST_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "FAIL", "framework": self.framework,
                "reason": f"Tests timed out after {Config.TEST_TIMEOUT_SECONDS}s.",
                "tests": 0, "passed": 0, "failed": 0, "exit_code": None,
                "stdout": "", "stderr": "Timeout exceeded.", "duration_ms": 0,
            }
        except Exception as e:
            return {
                "status": "BLOCKED", "framework": self.framework,
                "reason": f"Failed to execute tests: {e}", "tests": 0,
                "passed": 0, "failed": 0, "exit_code": None,
                "stdout": "", "stderr": str(e), "duration_ms": 0,
            }

        duration_ms = int((time.time() - start) * 1000)
        stdout = _decode_bytes(proc.stdout)
        stderr = _decode_bytes(proc.stderr)
        status = "PASS" if proc.returncode == 0 else "FAIL"
        tests, passed, failed = self._parse_summary(self.framework, stdout, stderr)

        return {
            "status": status,
            "framework": self.framework,
            "reason": "" if status == "PASS" else "At least one test failed.",
            "tests": tests, "passed": passed, "failed": failed,
            "exit_code": proc.returncode,
            "stdout": stdout[-8000:],
            "stderr": stderr[-8000:],
            "duration_ms": duration_ms,
        }

    def _parse_summary(self, framework: str, stdout: str, stderr: str):
        combined = stdout + "\n" + stderr
        if framework == "pytest":
            m = _re_search(r"(\d+) passed", combined)
            passed = int(m) if m else 0
            m = _re_search(r"(\d+) failed", combined)
            failed = int(m) if m else (1 if "FAILED" in combined else 0)
            m = _re_search(r"(\d+) (?:test|item)", combined)
            total = int(m) if m else (passed + failed)
            return total, passed, failed
        if framework in ("jest", "vitest", "mocha"):
            m = _re_search(r"Tests:\s+(\d+)", combined)
            total = int(m) if m else 0
            m = _re_search(r"Tests:\s+\d+\s+failed", combined)
            failed = 1 if m else 0
            passed = total - failed if total else 0
            return total, passed, failed
        if framework == "go test":
            failed = combined.count("FAIL") - combined.count("FAIL\t")
            m = _re_search(r"ok\s+\S+\s+", combined)
            total = 0
            return total, 0, max(failed, 0)
        return 0, 0, 0


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _find_test_files(root: Path, patterns: tuple) -> bool:
    import glob
    for pat in patterns:
        hits = list(root.glob(pat))
        if hits:
            return True
    return False


def _module_available(module: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(module) is not None


def _re_search(pattern: str, text: str):
    import re
    m = re.search(pattern, text)
    return m.group(1) if m else None
