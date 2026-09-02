"""
Report generator for Code Doctor AI.

Produce a professional, human-readable analysis report with an executive
summary, per-issue details, and final verification, plus a JSON export.
"""
import json
from datetime import datetime
from typing import Dict, Any, List


class Reporter:
    """Build reports from analysis results."""

    SEVERITY_MARK = {
        "CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡",
        "LOW": "🔵", "INFO": "⚪",
    }

    @staticmethod
    def health_score(summary: Dict[str, Any]) -> float:
        """Compute a 0-100 repository health score."""
        total = summary.get("total_issues", 0)
        if total == 0:
            return 95.0
        weight = (
            summary.get("critical", 0) * 12 +
            summary.get("high", 0) * 6 +
            summary.get("medium", 0) * 3 +
            summary.get("low", 0) * 1 +
            summary.get("info", 0) * 0.5
        )
        score = max(0.0, min(100.0, 100 - weight / max(total / 8, 1)))
        return round(score, 1)

    @classmethod
    def generate_markdown_report(cls, analysis: Dict[str, Any],
                                 repo: str = "", branch: str = "") -> str:
        summary = analysis.get("overall_summary", {})
        issues: List[Dict[str, Any]] = analysis.get("issues", [])
        health = cls.health_score(summary)

        lines = []
        lines.append("# 🩺 Code Doctor AI — Repository Health Report\n")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if repo:
            lines.append(f"**Repository:** `{repo}{('/' + branch) if branch else ''}`")
        files_scanned = summary.get("files_scanned", analysis.get("files_scanned", 0))
        file_total = summary.get("file_total", analysis.get("file_total", 0))
        lines.append(f"**Files scanned:** {files_scanned} / {file_total}")
        lines.append(f"**Repo health score:** {health}/100")
        lines.append("\n---\n")

        # Executive summary
        lines.append("## 📊 Executive Summary\n")
        lines.append("| Metric | Count |")
        lines.append("| --- | --- |")
        lines.append(f"| Files scanned | {files_scanned} |")
        lines.append(f"| Issues found | {summary.get('total_issues', 0)} |")
        lines.append(f"| Critical | {summary.get('critical', 0)} |")
        lines.append(f"| High | {summary.get('high', 0)} |")
        lines.append(f"| Medium | {summary.get('medium', 0)} |")
        lines.append(f"| Low | {summary.get('low', 0)} |")
        lines.append(f"| Security issues | {summary.get('security_issues', 0)} |")
        lines.append(f"| Dependency issues | {summary.get('dependency_issues', 0)} |")
        lines.append(f"| Lines of code | {summary.get('lines_of_code', 0)} |\n")

        ai_status = analysis.get("ai_status", "disabled")
        if isinstance(ai_status, str) and ai_status.startswith("error"):
            lines.append(f"> ⚠️ AI analysis note: {ai_status}\n")

        # Issue details
        lines.append("\n---\n## 🔍 Issue Details\n")
        if not issues:
            lines.append("✅ No issues found.\n")
        else:
            for i, iss in enumerate(issues, 1):
                sev = iss.get("severity", "INFO")
                mark = cls.SEVERITY_MARK.get(sev, "⚪")
                lines.append(f"### {mark} Issue #{i}: {iss.get('title', 'Untitled')}")
                lines.append(f"- **Category:** {iss.get('category', 'OTHER')}")
                lines.append(f"- **Severity:** {sev}")
                lines.append(f"- **Confidence:** {iss.get('confidence', 'n/a')}")
                if iss.get("file"):
                    lines.append(f"- **File:** `{iss['file']}`")
                if iss.get("line"):
                    lines.append(f"- **Line:** {iss['line']}")
                if iss.get("description"):
                    lines.append(f"\n**Problem:** {iss['description']}")
                if iss.get("evidence"):
                    lines.append(f"\n**Evidence:**\n```\n{iss['evidence']}\n```")
                if iss.get("why_it_matters"):
                    lines.append(f"\n**Why it matters:** {iss['why_it_matters']}")
                if iss.get("recommended_fix"):
                    lines.append(f"\n**Recommended fix:** {iss['recommended_fix']}")
                if iss.get("fixable"):
                    lines.append(f"\n**Fixable:** {iss['fixable']}")
                ver = iss.get("verification_status", "NOT_VERIFIED")
                lines.append(f"\n**Verification:** {ver}\n")

        # Final verification
        lines.append("\n---\n## ✅ Final Verification\n")
        test_result = analysis.get("test_result")
        if test_result:
            lines.append(f"- **Framework:** {test_result.get('framework')}")
            lines.append(f"- **Status:** {test_result.get('status')}")
            lines.append(f"- **Tests:** {test_result.get('tests')} "
                         f"(passed: {test_result.get('passed')}, failed: {test_result.get('failed')})")
        else:
            lines.append("- Tests not executed for this session.")
        lines.append(f"- Security checks: {summary.get('security_issues', 0)} issue(s) found")
        lines.append(f"- Remaining issues: {summary.get('total_issues', 0)}")

        return "\n".join(lines)

    @staticmethod
    def generate_json_report(analysis: Dict[str, Any]) -> str:
        """Serialize analysis (minus large file contents) to JSON."""
        import copy
        data = copy.deepcopy(analysis)
        files = data.get("files")
        if isinstance(files, list):
            for f in files:
                f.pop("content", None)
                f.pop("abs_path", None)
        return json.dumps(data, indent=2, default=str)
