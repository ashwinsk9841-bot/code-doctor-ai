"""
Security scanner for Code Doctor AI.

Local, deterministic pattern-based scanning of a file or a whole repository.
Detects hardcoded secrets, dangerous function usage, injection-style patterns,
unsafe deserialization, path traversal, and more.

Secrets are NEVER printed — matched secret values are replaced with masked
placeholders such as ``sk-********``.
"""
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import Config


def mask_secret(value: str, label: str = "secret") -> str:
    """Mask a sensitive value, keeping only a short prefix for context."""
    if not value:
        return f"{label}-********"
    prefix = value[:3]
    return f"{prefix}-********"


# ---- Generic secret regexes applied across languages ----
SECRET_PATTERNS = [
    (re.compile(r"(?i)(sk-[A-Za-z0-9_\-]{16,})"), "OpenAI-style API key"),
    (re.compile(r"(?i)(ghp_[A-Za-z0-9]{20,})"), "GitHub personal access token"),
    (re.compile(r"(?i)(gho_[A-Za-z0-9]{20,})"), "GitHub OAuth token"),
    (re.compile(r"(?i)(AKIA[0-9A-Z]{16})"), "AWS access key id"),
    (re.compile(r"(?i)(AIza[0-9A-Za-z_\-]{20,})"), "Google API key"),
    (re.compile(r"(?i)(xox[baprs]-[0-9A-Za-z-]{10,})"), "Slack token"),
    (re.compile(r"(?i)(sk-ant-[A-Za-z0-9_\-]{16,})"), "Anthropic API key"),
    (re.compile(r"\b(eyJ[A-Za-z0-9_\-\.]{20,})\b"), "JWT token"),
    (re.compile(r"(?i)(-----BEGIN [A-Z]+ PRIVATE KEY-----)"), "Private key"),
]

ASSIGNMENT_PATTERNS = [
    re.compile(r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|token|auth|private[_-]?key)\s*[:=]\s*['\"]([^'\"]{6,})['\"]"),
    re.compile(r"(?i)\b(bearer)\s+([A-Za-z0-9._\-]{10,})\b"),
]

# ---- Language-agnostic dangerous-pattern database ----
DANGEROUS_PATTERNS: Dict[str, List[Dict[str, Any]]] = {}


def _lang(*langs: str) -> set:
    return set(langs)


PATTERNS = [
    {
        "langs": {"python"},
        "regex": r"\beval\s*\(",
        "severity": "HIGH",
        "title": "Use of eval()",
        "category": "SECURITY",
        "description": "eval() executes arbitrary strings as code and is a common code-injection vector.",
        "fix": "Use ast.literal_eval() for literal data or refactor to avoid dynamic evaluation.",
    },
    {
        "langs": {"python"},
        "regex": r"\bexec\s*\(",
        "severity": "HIGH",
        "title": "Use of exec()",
        "category": "SECURITY",
        "description": "exec() runs arbitrary Python code supplied at runtime.",
        "fix": "Avoid exec() entirely; use explicit, structured logic.",
    },
    {
        "langs": {"python"},
        "regex": r"\b(pickle|shelve|marshal)\.(loads?|dumps?)\s*\(",
        "severity": "HIGH",
        "title": "Unsafe deserialization",
        "category": "SECURITY",
        "description": "Pickling untrusted data can execute arbitrary code during unpickling.",
        "fix": "Prefer JSON for untrusted data or validate the pickle source.",
    },
    {
        "langs": {"python"},
        "regex": r"\bos\.system\s*\(",
        "severity": "HIGH",
        "title": "os.system() command execution",
        "category": "SECURITY",
        "description": "os.system() invokes a shell; combined with user input it enables command injection.",
        "fix": "Use subprocess.run(..., shell=False) with an argument list.",
    },
    {
        "langs": {"python"},
        "regex": r"\bsubprocess\.(?:call|run|Popen|check_output)\s*\([^)]*shell\s*=\s*True",
        "severity": "HIGH",
        "title": "Shell=True subprocess",
        "category": "SECURITY",
        "description": "shell=True passes strings to a shell, enabling command injection.",
        "fix": "Use shell=False and pass a list of arguments.",
    },
    {
        "langs": {"python", "javascript", "typescript", "php", "ruby", "java", "csharp", "go"},
        "regex": r"['\"].*\b(SELECT|INSERT|UPDATE|DELETE)\b.*['\"].*\+",
        "severity": "HIGH",
        "title": "Possible SQL injection (string concatenation)",
        "category": "SECURITY",
        "description": "A SQL statement appears to be built by string concatenation, which can be injected.",
        "fix": "Use parameterized queries / prepared statements with bound parameters.",
    },
    {
        "langs": {"python", "javascript", "typescript", "php", "ruby", "java", "csharp", "go"},
        "regex": r"\.(execute|executemany|query)\s*\([^)]*\+",
        "severity": "HIGH",
        "title": "SQL executed with string concatenation",
        "category": "SECURITY",
        "description": "A query is executed with string concatenation, risking SQL injection.",
        "fix": "Use parameterized queries / prepared statements.",
    },
    {
        "langs": {"javascript", "typescript"},
        "regex": r"\.innerHTML\s*=",
        "severity": "HIGH",
        "title": "XSS via innerHTML",
        "category": "SECURITY",
        "description": "Assigning unsanitized data to innerHTML can inject scripts.",
        "fix": "Use textContent or sanitize/escape the input.",
    },
    {
        "langs": {"javascript", "typescript"},
        "regex": r"\bdocument\.write\s*\(",
        "severity": "MEDIUM",
        "title": "Unsafe document.write()",
        "category": "SECURITY",
        "description": "document.write() with user input can lead to DOM XSS.",
        "fix": "Use explicit DOM APIs and escape content.",
    },
    {
        "langs": {"javascript", "typescript"},
        "regex": r"dangerouslySetInnerHTML",
        "severity": "MEDIUM",
        "title": "React dangerouslySetInnerHTML",
        "category": "SECURITY",
        "description": "Rendering unsanitized HTML via dangerouslySetInnerHTML risks XSS.",
        "fix": "Sanitize with a library such as DOMPurify.",
    },
    {
        "langs": {"javascript", "typescript", "java", "php", "python", "ruby"},
        "regex": r"\beval\s*\(",
        "severity": "HIGH",
        "title": "Use of eval()",
        "category": "SECURITY",
        "description": "eval() executes arbitrary strings as code.",
        "fix": "Avoid eval(); parse structured data instead.",
    },
    {
        "langs": {"javascript", "typescript"},
        "regex": r"localStorage\s*\.\w+\s*\([^)]*(password|token|secret)",
        "severity": "MEDIUM",
        "title": "Sensitive data in localStorage",
        "category": "SECURITY",
        "description": "localStorage is accessible to any script on the origin.",
        "fix": "Avoid storing secrets client-side; use httpOnly cookies or server sessions.",
    },
    {
        "langs": {"java"},
        "regex": r"Runtime\.getRuntime\(\)\.exec",
        "severity": "HIGH",
        "title": "Command execution",
        "category": "SECURITY",
        "description": "Runtime.exec() with user input can run arbitrary commands.",
        "fix": "Validate input and prefer safer APIs that avoid a shell.",
    },
    {
        "langs": {"php"},
        "regex": r"\beval\s*\(",
        "severity": "HIGH",
        "title": "Use of eval()",
        "category": "SECURITY",
        "description": "eval() executes arbitrary PHP code.",
        "fix": "Avoid eval() with any untrusted input.",
    },
    {
        "langs": {"sql"},
        "regex": r"(?i)\bdrop\s+table\b",
        "severity": "HIGH",
        "title": "Destructive SQL command",
        "category": "SECURITY",
        "description": "DROP TABLE can delete data. Ensure it is intentional and access-controlled.",
        "fix": "Review access controls; consider safeguards.",
    },
]

# Path traversal / dangerous filesystem usage (language-generic)
DANGEROUS_FILESYSTEM = [
    {
        "regex": r"\braw_input\b",
        "severity": "LOW",
        "title": "Legacy raw_input()",
        "category": "CODE_QUALITY",
        "description": "raw_input() is Python 2 only and undefined in Python 3.",
        "fix": "Use input().",
    },
]


class SecurityScanner:
    """Scan files or a repository for security issues."""

    def __init__(self):
        self._compiled: Dict[str, List[Dict[str, Any]]] = {}
        for p in PATTERNS:
            for lang in p["langs"]:
                compiled = dict(p)
                compiled["compiled"] = re.compile(p["regex"], re.IGNORECASE | re.MULTILINE)
                self._compiled.setdefault(lang, []).append(compiled)

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------
    def scan_code(self, code: str, language: str,
                  path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scan a single source string. Returns a list of issue dicts."""
        issues: List[Dict[str, Any]] = []
        lang = (language or "").lower()
        offset_line = 1

        # Dangerous patterns for this language
        for pattern_info in self._compiled.get(lang, []):
            for m in pattern_info["compiled"].finditer(code):
                line = _line_of(code, m.start()) + offset_line - 1
                issues.append(self._make_issue(pattern_info, code, m, line, path))

        # Secret detection (generic)
        for rx, label in SECRET_PATTERNS:
            for m in rx.finditer(code):
                line = _line_of(code, m.start()) + offset_line - 1
                issues.append({
                    "issue_id": _issue_id("SEC"),
                    "title": f"Hardcoded {label}",
                    "category": "SECURITY",
                    "severity": "HIGH",
                    "confidence": 0.9,
                    "file": path,
                    "line": line,
                    "line_end": line,
                    "description": (
                        f"A {label} looks hardcoded in source. Send keys via "
                        "environment variables or a secure secret manager."
                    ),
                    "why_it_matters": "Committed secrets can be extracted and abused.",
                    "evidence": "Values are masked for safety.",
                    "matched_secret": mask_secret(m.group(1), label),
                    "recommended_fix": "Remove the key and load it from an environment variable.",
                    "fixable": True,
                    "verification_method": "Confirm no secret literals remain in source.",
                    "source": "security",
                })

        for rx in ASSIGNMENT_PATTERNS:
            for m in rx.finditer(code):
                line = _line_of(code, m.start()) + offset_line - 1
                label = m.group(1) if m.lastindex and m.lastindex >= 1 else "credential"
                issues.append({
                    "issue_id": _issue_id("SEC"),
                    "title": f"Hardcoded {label}",
                    "category": "SECURITY",
                    "severity": "HIGH",
                    "confidence": 0.85,
                    "file": path,
                    "line": line,
                    "line_end": line,
                    "description": (
                        f"A credential-like value ({label}) appears to be assigned "
                        "directly in code."
                    ),
                    "why_it_matters": "Hardcoded credentials are a common breach vector.",
                    "evidence": _context_line(code, line),
                    "recommended_fix": (
                        "Move the secret to an environment variable or secret manager."
                    ),
                    "fixable": True,
                    "verification_method": "Check that no literal credentials remain.",
                    "source": "security",
                })

        return _dedupe(issues)

    def _downgrade_test_usage(self, issues: List[Dict[str, Any]],
                              code: str) -> List[Dict[str, Any]]:
        """
        Reduce false positives for known "intentional in tests" patterns.

        When a flagged pattern sits inside a `pytest.raises(...)` / `assertRaises`
        block (i.e. the code deliberately triggers the dangerous path to assert
        that it is rejected), we downgrade the finding to INFO with a clear note
        instead of reporting a HIGH vulnerability.
        """
        for iss in issues:
            title = iss.get("title", "").lower()
            if "deserialization" not in title and "eval" not in title:
                continue
            line = iss.get("line", 1)
            window = "\n".join(code.split("\n")[max(0, line - 12): line + 12])
            if re.search(r"\bpytest\.raises\s*\(|\bassertRaises\s*\(|\bassert .*(raises|raiseswith|error)", window, re.IGNORECASE):
                iss["severity"] = "INFO"
                iss["confidence"] = 0.35
                iss["fixable"] = False
                iss["description"] = (
                    iss.get("description", "")
                    + " This appears inside an exception-assertion test block "
                      "(pytest.raises/assertRaises), likely intentional to verify "
                      "that the dangerous input is rejected."
                )
        return issues

    def scan_file(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scan one parsed file record."""
        content = record.get("content")
        if content is None or record.get("success") is False:
            return []
        issues = self.scan_code(content, record.get("language", "text"),
                                path=record.get("path"))
        issues = self._downgrade_test_usage(issues, content)
        return issues

    def scan_repository(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Scan a list of file records, returning aggregated issues."""
        all_issues: List[Dict[str, Any]] = []
        for record in records:
            all_issues.extend(self.scan_file(record))
        return _dedupe(all_issues)

    def _make_issue(self, pattern_info: Dict[str, Any], code: str,
                    match: "re.Match", line: int, path: Optional[str]) -> Dict[str, Any]:
        return {
            "issue_id": _issue_id("SEC"),
            "title": pattern_info["title"],
            "category": pattern_info.get("category", "SECURITY"),
            "severity": pattern_info.get("severity", "HIGH"),
            "confidence": 0.9,
            "file": path,
            "line": line,
            "line_end": _line_of(code, match.end()),
            "description": pattern_info["description"],
            "why_it_matters": "Security weaknesses may be exploitable by attackers.",
            "evidence": _safe_evidence(code, match),
            "recommended_fix": pattern_info["fix"],
            "fixable": True,
            "verification_method": "Re-run security scan and confirm the pattern is gone.",
            "source": "security",
        }

    def get_summary(self, vulnerabilities: List[Dict[str, Any]]) -> Dict[str, int]:
        """Summary counts of vulnerabilities by severity."""
        summary = {"total": len(vulnerabilities), "critical": 0, "high": 0,
                   "medium": 0, "low": 0}
        for v in vulnerabilities:
            sev = v.get("severity", "MEDIUM").upper()
            key = sev.lower()
            if key in summary:
                summary[key] += 1
            elif sev == "INFO":
                summary["low"] += 1
        return summary


def _issue_id(source: str) -> str:
    import uuid
    return f"{source}-{uuid.uuid4().hex[:8]}"


def _line_of(text: str, index: int) -> int:
    return text[:index].count("\n") + 1


def _context_line(code: str, line: int) -> str:
    lines = code.split("\n")
    if 1 <= line <= len(lines):
        return _mask_literals(lines[line - 1].strip())
    return ""


def _mask_literals(snippet: str) -> str:
    """Mask quoted string literals so secrets never leak into evidence/reports."""
    return re.sub(
        r"['\"]([^'\"]{4,})['\"]",
        lambda m: "'********'",
        snippet,
    )


def _safe_evidence(code: str, match: "re.Match") -> str:
    """Return a safe (secret-free) snippet of the matched line."""
    line = _line_of(code, match.start())
    snippet = _context_line(code, line)
    snippet = _mask_literals(snippet)
    return snippet[:200]


def _dedupe(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate issues that share file+line+title."""
    seen = {}
    result = []
    for iss in issues:
        key = (iss.get("file"), iss.get("line"), iss.get("title"))
        if key in seen:
            continue
        seen[key] = True
        result.append(iss)
    return result
