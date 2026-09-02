"""
Code analyzer orchestrator for Code Doctor AI.

Runs the full repository pipeline: discovery -> parse -> static metrics ->
security scan -> dependency scan -> (optional) AI analysis -> issue aggregation.
Produces a structured result consumed by the UI and reporter.
"""
from typing import Dict, Any, List, Optional, Callable

from config import Config
from .code_parser import CodeParser
from .security_scanner import SecurityScanner
from .dependency_scanner import DependencyScanner
from .ai_provider import AIProvider, classify_provider_error

ProgressFn = Callable[[str], None]


class CodeAnalyzer:
    """Orchestrates analysis over a repository (or a single snippet)."""

    def __init__(self, ai_provider: Optional[AIProvider] = None):
        self.ai_provider = ai_provider
        self.code_parser = CodeParser()
        self.security_scanner = SecurityScanner()
        self.dependency_scanner = DependencyScanner()

    # ------------------------------------------------------------------
    # Repository analysis
    # ------------------------------------------------------------------
    def analyze_repository(self, repo_root, owner_repo: str,
                           enable_security: bool = True,
                           enable_ai: bool = True,
                           files: Optional[List[Dict[str, Any]]] = None,
                           progress: Optional[ProgressFn] = None) -> Dict[str, Any]:
        """Analyze an entire repository root."""
        _report = progress or (lambda m: None)

        _report("Discovering files...")
        if files is None:
            files = self.code_parser.discover_files(repo_root)

        _report(f"{len(files)} files discovered. Reading source...")
        files = self.code_parser.read_many(files)
        files = self.code_parser.analyze_many(files)

        _report("Running static & security analysis...")
        issues: List[Dict[str, Any]] = []
        security_issues: List[Dict[str, Any]] = []
        if enable_security:
            security_issues = self.security_scanner.scan_repository(files)
            issues.extend(security_issues)

        _report("Analyzing dependencies...")
        dependency_result = self.dependency_scanner.scan_repository(repo_root)
        dep_issues = dependency_result["issues"]
        issues.extend(dep_issues)

        ai_status = "disabled"
        ai_issues: List[Dict[str, Any]] = []
        if enable_ai and self.ai_provider is not None:
            _report("Running AI analysis...")
            ai_file, ai_issues, ai_status = self._run_ai_analysis(files)
            issues.extend(ai_issues)
        else:
            ai_file = None

        # Static-detected issues from parsing
        static_issues = self._static_issues(files)
        issues.extend(static_issues)

        issues = self._normalize_and_sort(issues)

        summary = self._build_summary(files, issues, security_issues, dep_issues, ai_issues)

        return {
            "success": True,
            "repo": owner_repo,
            "language_summary": self._language_breakdown(files),
            "files": files,
            "files_scanned": len([f for f in files if f.get("success")]),
            "file_total": len(files),
            "issues": issues,
            "ai_issues": ai_issues,
            "security_issues": security_issues,
            "dependency_issues": dep_issues,
            "dependency_details": dependency_result["details"],
            "ai_status": ai_status,
            "ai_sample_file": ai_file,
            "overall_summary": summary,
        }

    def _run_ai_analysis(self, files: List[Dict[str, Any]]) -> tuple:
        """Run AI analysis over a bounded sample of the most relevant files."""
        candidate_files = [f for f in files if f.get("success") and f.get("content")]
        if not candidate_files:
            return None, [], "no_files"

        # Prioritize files with detected issues or larger/diverse sources.
        _by_ext = sorted(candidate_files, key=lambda f: f.get("lines", 0), reverse=True)
        sample = _by_ext[:8]
        if not sample:
            return None, [], "no_files"

        ticks = [i / len(_by_ext) for i in range(len(_by_ext))]
        ai_issues: List[Dict[str, Any]] = []
        ai_file = None
        try:
            for idx, record in enumerate(sample):
                lang = record.get("language", "text")
                if lang in ("json", "yaml", "toml", "markdown", "make", "dockerfile"):
                    continue
                result = self.ai_provider.analyze_code(
                    record["content"], lang, "full",
                    file_context=[{"path": record["path"], "content": record["content"][:4000]}],
                )
                for iss in result.get("issues", []):
                    iss["file"] = record["path"]
                    iss["line"] = iss.get("line") or 1
                    iss["source"] = "ai"
                    ai_issues.append(iss)
                ai_file = ai_file or record
                if idx >= 4:
                    break
            return ai_file, ai_issues, "ok"
        except Exception as e:
            msg, kind = classify_provider_error(e)
            return ai_file, ai_issues, f"error:{kind}:{msg}"

    def _static_issues(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Derive deterministic issues from parsing (syntax errors, TODOs)."""
        issues: List[Dict[str, Any]] = []
        for f in files:
            if not f.get("success"):
                issues.append(self._issue(
                    "File could not be decoded",
                    "CONFIGURATION", "LOW", f.get("path"), 1,
                    f"File '{f.get('path')}' could not be read/decoded: {f.get('error')}",
                    "Undecodable files are skipped and may hide real problems.",
                    "Fix encoding or add a proper text file.",
                    confidence=0.9, source="parser",
                ))
                continue
            structure = f.get("structure", {})
            for err in structure.get("syntax_errors", []):
                issues.append(self._issue(
                    "Syntax error",
                    "BUG", "HIGH", f.get("path"), err.get("line"),
                    err.get("message"),
                    "Syntax errors can prevent the program from running.",
                    "Correct the syntax on the indicated line.",
                    confidence=0.95, source="parser",
                ))
        return issues

    # ------------------------------------------------------------------
    # Single-file analysis (legacy / paste flow)
    # ------------------------------------------------------------------
    def analyze_full(self, code: str, language: str, enable_security: bool = True) -> Dict[str, Any]:
        """Analyze a single snippet of code (paste/upload flow)."""
        from .code_parser import CodeParser as _P
        from .security_scanner import SecurityScanner as _S

        parser = _P()
        lines = parser.count_lines(code)
        complexity = parser.calculate_complexity(code, language)
        structure = parser.parse_code(code, language)
        todos = parser.extract_todo_fixme(code)

        issues: List[Dict[str, Any]] = []
        if enable_security:
            issues.extend(_S().scan_code(code, language, path="<input>"))
        for err in structure.get("syntax_errors", []):
            issues.append(self._issue(
                "Syntax error", "BUG", "HIGH", "<input>", err.get("line"),
                err.get("message"), "Syntax errors can prevent the program from running.",
                "Correct the syntax.", confidence=0.95, source="parser",
            ))

        ai_analysis = {}
        ai_status = "disabled"
        if self.ai_provider is not None:
            try:
                ai_analysis = self.ai_provider.analyze_code(code, language, "full")
                for iss in ai_analysis.get("issues", []):
                    iss["file"] = "<input>"
                    iss.setdefault("source", "ai")
                    issues.append(iss)
                ai_status = "ok"
            except Exception as e:
                ai_status = classify_provider_error(e)[0]

        issues = self._normalize_and_sort(issues)
        summary = {
            "total_issues": len(issues),
            "critical": sum(1 for i in issues if i.get("severity") == "CRITICAL"),
            "high": sum(1 for i in issues if i.get("severity") == "HIGH"),
            "medium": sum(1 for i in issues if i.get("severity") == "MEDIUM"),
            "low": sum(1 for i in issues if i.get("severity") == "LOW"),
            "info": sum(1 for i in issues if i.get("severity") == "INFO"),
            "lines_of_code": lines.get("code", 0),
            "complexity": complexity,
            "security_issues": len([i for i in issues if i.get("category") == "SECURITY"]),
        }

        return {
            "success": True,
            "language": language,
            "static_analysis": {"line_counts": lines, "complexity": complexity,
                                "structure": structure, "todos": todos},
            "ai_analysis": ai_analysis,
            "ai_status": ai_status,
            "security_scan": {
                "vulnerabilities": [i for i in issues if i.get("source") == "security"],
                "summary": _S().get_summary(issues),
            },
            "issues": issues,
            "overall_summary": summary,
            "original_code": code,
        }

    # ------------------------------------------------------------------
    def _issue(self, title, category, severity, file, line, description, why, fix,
               confidence=0.8, source="static", evidence="", fixable=True,
               verification="Re-run the relevant check."):
        import uuid
        return {
            "issue_id": f"{source.upper()}-{uuid.uuid4().hex[:8]}",
            "title": title,
            "category": category,
            "severity": severity,
            "confidence": confidence,
            "file": file,
            "line": line or 1,
            "line_end": line or 1,
            "description": description,
            "why_it_matters": why,
            "evidence": evidence,
            "recommended_fix": fix,
            "fixable": fixable,
            "verification_method": verification,
            "source": source,
        }

    @staticmethod
    def _normalize_and_sort(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        order = Config.SEVERITY_ORDER
        return sorted(issues, key=lambda i: order.get(i.get("severity", "INFO"), 99))

    def _build_summary(self, files, issues, security, dep, ai) -> Dict[str, Any]:
        def count(sev):
            return sum(1 for i in issues if i.get("severity") == sev)
        total_lines = sum(f.get("lines", 0) for f in files if f.get("success"))
        return {
            "total_issues": len(issues),
            "critical": count("CRITICAL"),
            "high": count("HIGH"),
            "medium": count("MEDIUM"),
            "low": count("LOW"),
            "info": count("INFO"),
            "security_issues": len(security),
            "dependency_issues": len(dep),
            "ai_issues": len(ai),
            "lines_of_code": total_lines,
            "files_scanned": len([f for f in files if f.get("success")]),
            "file_total": len(files),
            "complexity": sum(f.get("metrics", {}).get("complexity", 0) for f in files),
        }

    @staticmethod
    def _language_breakdown(files) -> Dict[str, int]:
        breakdown = {}
        for f in files:
            lang = f.get("language", "text")
            breakdown[lang] = breakdown.get(lang, 0) + 1
        return dict(sorted(breakdown.items(), key=lambda kv: kv[1], reverse=True))

    # Backward-compatible alias used by existing UI/tests
    def get_all_issues(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        return results.get("issues", [])

    def explain_code(self, code: str, language: str) -> str:
        if self.ai_provider is None:
            return "AI provider not configured."
        try:
            return self.ai_provider.explain_code(code, language)
        except Exception:
            return "Could not generate explanation."
