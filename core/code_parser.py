"""
Code parser for Code Doctor AI.

Responsible for discovering source files inside a repository, reading them
safely (encoding-tolerant), detecting language, preserving line numbers, and
producing structured per-file records for downstream analysis. A single invalid
or undecodable file never aborts the whole scan.
"""
import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

from config import Config


class ParseErrorRecord:
    """A file that could not be read or parsed, recorded without crashing."""


class CodeParser:
    """Discover and parse source files in a repository."""

    def __init__(self, ignored_dirs: Optional[set] = None,
                 ignored_extensions: Optional[set] = None):
        self._ignored_dirs = ignored_dirs or set(Config.IGNORED_DIRS)
        self._ignored_extensions = ignored_extensions or set(Config.IGNORED_EXTENSIONS)

    # ------------------------------------------------------------------
    # File discovery
    # ------------------------------------------------------------------
    def discover_files(self, root: Path) -> List[Dict[str, Any]]:
        """Walk a repository root and return safe relative source file records."""
        root = root.resolve()
        files: List[Dict[str, Any]] = []

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d for d in dirnames
                if d not in self._ignored_dirs and not d.startswith(".")
            ]
            for name in filenames:
                full = Path(dirpath) / name
                try:
                    rel = full.relative_to(root)
                except ValueError:
                    continue
                rel_str = rel.as_posix()
                ext = _safe_suffix(full).lower()
                base = full.name.lower()

                if ext in self._ignored_extensions:
                    continue
                if base.startswith("."):
                    continue
                if name.lower() in {"dockerfile", "makefile"}:
                    files.append(self._file_record(full, rel_str))
                    continue

                language = self.detect_language(full)
                if language in ("text", None):
                    # Only keep textual config-like files that we can analyze.
                    if not _is_text_candidate(full):
                        continue
                    files.append(self._file_record(full, rel_str))
                    continue

                files.append(self._file_record(full, rel_str))

            if len(files) >= Config.MAX_FILES:
                break

        return files

    def _file_record(self, full: Path, rel_str: str) -> Dict[str, Any]:
        return {
            "path": rel_str,
            "abs_path": str(full),
            "extension": full.suffix.lower(),
            "language": self.detect_language(full),
            "size": _file_size(full),
            "content": None,
            "lines": 0,
            "success": False,
            "error": None,
            "encoding": None,
        }

    def detect_language(self, path: Path) -> str:
        """Detect language from a path using Config mappings."""
        base = path.name.lower()
        if base == "dockerfile":
            return "dockerfile"
        if base == "makefile":
            return "make"
        ext = path.suffix.lower()
        for lang, extensions in Config.SUPPORTED_LANGUAGES.items():
            if ext in extensions:
                return lang
            # Also allow files like `Dockerfile` matched by no-extension bases
        return "text"

    # ------------------------------------------------------------------
    # Safe reading
    # ------------------------------------------------------------------
    def read_file(self, record: Dict[str, Any], max_bytes: int = None) -> Dict[str, Any]:
        """Read a file record's content safely, updating it in place."""
        max_bytes = max_bytes or Config.MAX_FILE_ANALYZE_BYTES
        path = Path(record["abs_path"])
        try:
            raw = path.read_bytes()
            if len(raw) > max_bytes:
                record["error"] = "file_too_large"
                record["success"] = False
                return record
            content, encoding = _decode(raw)
            record["content"] = content
            record["encoding"] = encoding
            record["lines"] = content.count("\n") + 1
            record["success"] = True
        except OSError as e:
            record["error"] = str(e)
        except Exception as e:
            record["error"] = str(e)
        return record

    def read_many(self, records: List[Dict[str, Any]],
                  max_bytes: int = None) -> List[Dict[str, Any]]:
        for record in records:
            self.read_file(record, max_bytes=max_bytes)
        return records

    # ------------------------------------------------------------------
    # Per-language structural parsing
    # ------------------------------------------------------------------
    @staticmethod
    def parse_python(code: str, lineno: int = 1) -> Dict[str, Any]:
        """Parse Python code, preserving line numbers and capturing syntax errors."""
        result = {
            "language": "python",
            "functions": [],
            "classes": [],
            "imports": [],
            "syntax_errors": [],
        }
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            result["syntax_errors"].append({
                "line": lineno + (e.lineno or 0) - 1,
                "message": e.msg,
                "text": (e.text or "").strip(),
            })
            return result
        except Exception as e:
            result["syntax_errors"].append({"line": lineno, "message": str(e), "text": ""})
            return result

        offset = lineno - 1
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                result["functions"].append({
                    "name": node.name, "line": offset + node.lineno,
                })
            elif isinstance(node, ast.ClassDef):
                result["classes"].append({
                    "name": node.name, "line": offset + node.lineno,
                })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    result["imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    result["imports"].append(
                        f"{module}.{alias.name}" if module else alias.name
                    )
        return result

    @staticmethod
    def parse_javascript(code: str) -> Dict[str, Any]:
        """Regex-based structural parse of JavaScript/TypeScript."""
        result = {"language": "javascript", "functions": [], "classes": [], "imports": []}
        for pattern in (r'function\s+([A-Za-z_$][\w$]*)\s*\(',):
            for m in re.finditer(pattern, code):
                result["functions"].append({"name": m.group(1),
                                            "line": _line_of(code, m.start())})
        for pattern in (r'(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:\([^)]*\)\s*=>|[^=]*=>)',):
            for m in re.finditer(pattern, code):
                result["functions"].append({"name": m.group(1),
                                            "line": _line_of(code, m.start())})
        for m in re.finditer(r'class\s+([A-Za-z_$][\w$]*)', code):
            result["classes"].append({"name": m.group(1), "line": _line_of(code, m.start())})
        for m in re.finditer(r'(?:import|export)\s+.*?\bfrom\s+[\'"]([^\'"]+)[\'"]', code):
            result["imports"].append(m.group(1))
        return result

    @classmethod
    def parse_code(cls, code: str, language: str, lineno: int = 1) -> Dict[str, Any]:
        """Dispatch structural parsing by language."""
        lang = (language or "").lower()
        if lang == "python":
            return cls.parse_python(code, lineno=lineno)
        if lang in ("javascript", "typescript"):
            return cls.parse_javascript(code)
        return {"language": lang, "functions": [], "classes": [], "imports": []}

    # ------------------------------------------------------------------
    # Static metrics on a single file
    # ------------------------------------------------------------------
    @staticmethod
    def count_lines(code: str) -> Dict[str, int]:
        """Count total/blank/comment/code lines (simple, generic)."""
        lines = code.split("\n")
        total = len(lines)
        blank = sum(1 for ln in lines if not ln.strip())
        comment = 0
        in_block = False
        for ln in lines:
            s = ln.strip()
            if s.startswith(("#", "//", "*")) or s.startswith("<!--"):
                comment += 1
                continue
            if s.startswith(("/*", '"""', "'''")) or in_block:
                comment += 1
                in_block = not s.endswith(("*/", '"""', "'''"))
                continue
        return {"total": total, "code": max(0, total - blank - comment),
                "blank": blank, "comment": comment}

    @staticmethod
    def calculate_complexity(code: str, language: str) -> int:
        """Estimate cyclomatic complexity from decision keywords."""
        keywords = [
            r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b", r"\bcatch\b",
            r"\bexcept\b", r"\b&&\b", r"\|\|", r"\band\b", r"\bor\b",
            r"\bswitch\b", r"\?.*:",
        ]
        complexity = 1
        for kw in keywords:
            complexity += len(re.findall(kw, code, re.IGNORECASE | re.MULTILINE))
        return complexity

    @staticmethod
    def extract_todo_fixme(code: str) -> List[Dict[str, Any]]:
        todos = []
        pattern = r"\b(TODO|FIXME|XXX|HACK|BUG)\b[:\s]+(.+?)(?:\n|$)"
        for m in re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE):
            todos.append({
                "type": m.group(1).upper(),
                "message": m.group(2).strip(),
                "line": _line_of(code, m.start()),
            })
        return todos

    def analyze_file(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Run full static analysis over one file record (in place)."""
        content = record.get("content")
        language = record.get("language", "text")
        if content is None or record.get("success") is False:
            record["structure"] = {"language": language}
            record["metrics"] = {"complexity": 0, "line_counts": {"total": 0}}
            record["todos"] = []
            return record

        line_counts = self.count_lines(content)
        complexity = self.calculate_complexity(content, language)
        todos = self.extract_todo_fixme(content)
        structure = self.parse_code(content, language)

        record["structure"] = structure
        record["metrics"] = {"complexity": complexity, "line_counts": line_counts}
        record["todos"] = todos
        return record

    def analyze_many(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for record in records:
            self.analyze_file(record)
        return records


def _safe_suffix(path: Path) -> str:
    try:
        return path.suffix
    except Exception:
        return ""


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _decode(raw: bytes) -> tuple:
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, AttributeError):
            continue
    # Final fallback — always decodes, may contain substitutions.
    return raw.decode("utf-8", errors="replace"), "utf-8(ignore)"


def _line_of(text: str, index: int) -> int:
    return text[:index].count("\n") + 1


def _is_text_candidate(path: Path) -> bool:
    """Heuristic: is this file likely textual (config, readme, lockfile...)?"""
    name = path.name.lower()
    if name in ("readme", "readme.md", "license", "license.txt", "changelog"):
        return True
    return path.suffix.lower() in {
        ".txt", ".cfg", ".ini", ".properties", ".conf",
    }
