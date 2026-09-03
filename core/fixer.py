"""
Fix engine for Code Doctor AI.

Applies MINIMAL, targeted changes rather than rewriting whole files. Provides a
backup mechanism, syntax validation after edits, and a deterministic patch model
for fixing security issues (masked secrets replaced with env-var references),
as well as an optional AI-driven whole-snippet rewrite for complex fixes.
"""
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from .ai_provider import AIProvider, classify_provider_error


@dataclass
class AppliedChange:
    file: str
    line: int
    original: str
    new: str
    reason: str
    risk: str = "low"
    verification: str = "NOT_VERIFIED"


class CodeFixer:
    """Apply fixes to files (or snippet text) and validate them."""

    def __init__(self, ai_provider: Optional[AIProvider] = None):
        self.ai_provider = ai_provider

    # ------------------------------------------------------------------
    # Repository-level fixing
    # ------------------------------------------------------------------
    def apply_fix_to_repo(self, repo_root: Path, issue: Dict[str, Any],
                          files_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Apply a single deterministic fix for the given issue."""
        rel_path = issue.get("file")
        if not rel_path:
            return {"applied": False, "error": "Issue has no associated file."}

        absolute = (repo_root / rel_path).resolve() if rel_path != "<input>" else None
        if absolute is None or not absolute.exists() or not _is_within(repo_root, absolute):
            return {"applied": False, "error": "Unsafe or missing target file path."}

        source = issue.get("source")
        result = {"applied": False, "changes": []}

        # Attempt a deterministic fix for a known issue source.
        if source == "security":
            fix_result = self._fix_security(repo_root, absolute, issue)
            if fix_result["applied"]:
                return fix_result

        # Fallback: AI full-file rewrite for fixable issues.
        if self.ai_provider is not None:
            return self._ai_fix_repo(repo_root, absolute, issue)

        return {"applied": False, "error": "No deterministic or AI fix available."}

    def apply_many_fixes_to_repo(self, repo_root: Path,
                                 issues: List[Dict[str, Any]],
                                 files_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply fixes for MANY issues, batching AI rewrites per file.

        Deterministic security fixes are applied individually. AI-driven rewrites
        are grouped by file so a single ``fix_code`` request handles every AI-fixable
        issue in that file (instead of one request per issue), reducing API/rate-limit
        pressure. ``files_map`` is the parsed file records; the list returned matches
        the input ``issues`` order with an ``applied``/``error`` result per issue.
        """
        results: List[Dict[str, Any]] = []
        security_batches: List[Dict[str, Any]] = []
        ai_batches: Dict[str, List[Dict[str, Any]]] = {}  # file -> issues

        for issue in issues:
            if issue.get("source") == "security":
                security_batches.append(issue)
            else:
                fpath = issue.get("file")
                if fpath:
                    ai_batches.setdefault(fpath, []).append(issue)

        applied_by_id: Dict[str, bool] = {}

        for issue in security_batches:
            res = self.apply_fix_to_repo(repo_root, issue, files_map)
            applied_by_id[issue.get("issue_id")] = res.get("applied", False)
            results.append({"issue_id": issue.get("issue_id"), **res})

        for fpath, batch in ai_batches.items():
            absolute = (repo_root / fpath).resolve()
            if absolute is None or not absolute.exists() or not _is_within(repo_root, absolute):
                for issue in batch:
                    applied_by_id[issue.get("issue_id")] = False
                    results.append({"issue_id": issue.get("issue_id"),
                                    "applied": False, "changes": [],
                                    "error": "Unsafe or missing target file path."})
                continue
            batch_res = self._ai_fix_many(repo_root, absolute, batch)
            # Apply the same file-level result to each issue in the batch.
            if batch_res.get("applied"):
                for issue in batch:
                    applied_by_id[issue.get("issue_id")] = True
                    results.append({"issue_id": issue.get("issue_id"), **batch_res,
                                    "changes": batch_res.get("changes", [])})
            else:
                for issue in batch:
                    applied_by_id[issue.get("issue_id")] = False
                    results.append({"issue_id": issue.get("issue_id"), **batch_res})

        return results

    def _ai_fix_many(self, repo_root: Path, absolute: Path,
                     issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """AI-rewrite a single file to fix ALL of its issues in one request."""
        try:
            original_text = absolute.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return {"applied": False, "error": f"Could not read file: {e}"}

        language = issues[0].get("language") if issues else "text"
        try:
            fixed = self.ai_provider.fix_code(original_text, language, issues)
        except Exception as e:
            msg, _ = classify_provider_error(e)
            return {"applied": False, "error": f"AI fix failed: {msg}"}

        if not fixed or fixed.strip() == original_text.strip():
            return {"applied": False, "error": "AI produced no change."}

        if not self._validate_syntax(fixed, issues[0].get("file") if issues else None):
            return {"applied": False, "error": "AI fix produced invalid syntax; not applied."}

        backup = self._backup(repo_root, absolute)
        absolute.write_text(fixed, encoding="utf-8")
        return {
            "applied": True,
            "backup": backup,
            "changes": [{"file": issues[0].get("file"), "line": issues[0].get("line"),
                         "original": "<file rewritten>", "new": "<rewritten>",
                         "reason": f"AI-driven fix applied for {len(issues)} issue(s).",
                         "risk": "medium", "verification": "NOT_VERIFIED"}],
        }

    def _fix_security(self, repo_root: Path, absolute: Path,
                      issue: Dict[str, Any]) -> Dict[str, Any]:
        """Replace hardcoded secret literals with environment-variable reads."""
        if "credential" not in issue.get("title", "").lower() and \
           "hardcoded" not in issue.get("title", "").lower():
            return {"applied": False, "error": "not_a_secret_fix"}

        try:
            original_text = absolute.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return {"applied": False, "error": f"Could not read file: {e}"}

        text = original_text
        changes: List[AppliedChange] = []
        line = issue.get("line", 1)
        lines = text.split("\n")
        if line < 1 or line > len(lines):
            return {"applied": False, "error": "Line out of range."}

        old_line = lines[line - 1]
        new_line = _replace_secret_assignment(old_line)

        if new_line == old_line:
            return {"applied": False, "error": "Could not locate a secret to replace."}

        lines[line - 1] = new_line
        text = "\n".join(lines)

        if not self._validate_syntax(text, issue.get("file")):
            return {"applied": False, "error": "Fix produced invalid syntax; not applied."}

        backup = self._backup(repo_root, absolute)
        absolute.write_text(text, encoding="utf-8")

        changes.append(AppliedChange(
            file=issue.get("file"), line=line,
            original=old_line, new=new_line,
            reason="Replaced hardcoded credential with environment variable read.",
            risk="low", verification="NOT_VERIFIED",
        ))
        return {"applied": True, "backup": backup, "changes": [asdict(c) for c in changes]}

    def _ai_fix_repo(self, repo_root: Path, absolute: Path,
                     issue: Dict[str, Any]) -> Dict[str, Any]:
        try:
            original_text = absolute.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return {"applied": False, "error": f"Could not read file: {e}"}

        try:
            fixed = self.ai_provider.fix_code(original_text, issue.get("language", "text"), [issue])
        except Exception as e:
            msg, _ = classify_provider_error(e)
            return {"applied": False, "error": f"AI fix failed: {msg}"}

        if not fixed or fixed.strip() == original_text.strip():
            return {"applied": False, "error": "AI produced no change."}

        if not self._validate_syntax(fixed, issue.get("file")):
            return {"applied": False, "error": "AI fix produced invalid syntax; not applied."}

        backup = self._backup(repo_root, absolute)
        absolute.write_text(fixed, encoding="utf-8")
        return {
            "applied": True,
            "backup": backup,
            "changes": [{"file": issue.get("file"), "line": issue.get("line"),
                         "original": "<file rewritten>", "new": "<rewritten>",
                         "reason": "AI-driven fix applied.", "risk": "medium",
                         "verification": "NOT_VERIFIED"}],
        }

    def _backup(self, repo_root: Path, absolute: Path) -> Path:
        backup_dir = repo_root / ".codedoctor_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        rel = absolute.relative_to(repo_root).as_posix().replace("/", "__")
        backup = backup_dir / f"{rel}.bak"
        try:
            backup.write_bytes(absolute.read_bytes())
        except OSError:
            pass
        return backup

    # ------------------------------------------------------------------
    # Snippet-level fixing (legacy / paste flow)
    # ------------------------------------------------------------------
    def fix_code(self, code: str, language: str, issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a fixed snippet. Deterministic secret-fix first, AI fallback."""
        result = {"success": False, "fixed_code": "", "explanation": "", "changes": []}

        if not issues:
            result.update(success=True, fixed_code=code,
                          explanation="No issues found. Code looks good!")
            return result

        # Try deterministic replacement of secret literals.
        new_code = _replace_all_secret_assignments(code)
        if new_code != code:
            result["success"] = True
            result["fixed_code"] = new_code
            result["explanation"] = "Replaced hardcoded credentials with environment variable reads."
            result["changes"] = ["Replaced hardcoded secret(s) with os.environ lookups."]
            return result

        if self.ai_provider is None:
            result["error"] = "AI provider not configured for non-deterministic fixes."
            return result

        try:
            fixed = self.ai_provider.fix_code(code, language, issues)
            result["success"] = True
            result["fixed_code"] = fixed
            result["explanation"] = f"Fixed {len(issues)} issue(s)."
            result["changes"] = _diff_lines(code, fixed)
        except Exception as e:
            msg, _ = classify_provider_error(e)
            result["error"] = msg
        return result

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _validate_syntax(self, text: str, filename: Optional[str]) -> bool:
        name = (filename or "").lower()
        if name.endswith(".py"):
            return _validate_python(text)
        if name.endswith((".js", ".ts", ".jsx", ".tsx", ".json")):
            return _validate_json(text) if name.endswith(".json") else True
        return True


def _validate_python(text: str) -> bool:
    try:
        compile(text, "<fixer>", "exec")
        return True
    except SyntaxError:
        return False


def _validate_json(text: str) -> bool:
    import json
    try:
        json.loads(text)
        return True
    except Exception:
        return False


def _replace_secret_assignment(line: str) -> str:
    """Replace a `KEY = "secret"` line with an os.environ lookup. Python-targeted."""
    import re
    m = re.match(r'^(\s*[A-Za-z_][\w]*)\s*=\s*["\'](.{2,})["\']\s*$', line)
    if not m:
        return line
    var = m.group(1)
    if "env" in line.lower() or "getenv" in line.lower():
        return line
    indent = line[: len(line) - len(line.lstrip())]
    env_var = var.upper()
    return (
        f"{indent}{var} = os.environ.get(\"{env_var}\", \"\")\n"
        f"{indent}# TODO: set {env_var} in your environment / CI"
    )


def _replace_all_secret_assignments(code: str) -> str:
    lines = code.split("\n")
    changed = False
    for i, line in enumerate(lines):
        new = _replace_secret_assignment(line)
        if new != line:
            lines[i] = new
            changed = True
    if changed and "import os" not in code:
        lines.insert(0, "import os")
    return "\n".join(lines)


def _diff_lines(original: str, fixed: str) -> List[str]:
    changes = []
    orig = original.split("\n")
    fix = fixed.split("\n")
    for i, (o, f) in enumerate(zip(orig, fix), 1):
        if o != f:
            changes.append(f"Line {i} modified.")
    if len(orig) != len(fix):
        changes.append(f"Line count changed from {len(orig)} to {len(fix)}.")
    return changes[:20]


def _is_within(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
