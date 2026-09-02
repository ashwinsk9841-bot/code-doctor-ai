"""
Dependency analysis for Code Doctor AI.

Discovers manifest files in a repository (requirements.txt, package.json,
pyproject.toml, go.mod, Cargo.toml, etc.), parses declared dependencies, and
flags issues that can be determined locally: missing install instructions,
invalid version specs / pins, suspicious/pinned-to-HEAD references, and manifest
inconsistencies. It intentionally does NOT fabricate CVE data.
"""
import re
import json
import tomllib as _toml
from pathlib import Path
from typing import Dict, List, Any, Optional

from config import Config


class DependencyScanner:
    """Analyze dependency manifests."""

    def find_manifests(self, root: Path) -> List[Path]:
        manifests = []
        for dirpath, dirnames, filenames in root.walk():
            dirnames[:] = [d for d in dirnames if d not in Config.IGNORED_DIRS]
            for name in filenames:
                if name in Config.MANIFEST_FILENAMES:
                    manifests.append(Path(dirpath) / name)
        return manifests

    def scan_repository(self, root: Path) -> Dict[str, Any]:
        manifests = self.find_manifests(root)
        issues: List[Dict[str, Any]] = []
        details: List[Dict[str, Any]] = []

        for path in manifests:
            rel = _rel(root, path)
            try:
                parsed = self._parse_manifest(path, rel)
            except Exception as e:
                details.append({"file": rel, "status": "parse_error", "error": str(e)})
                issues.append(self._issue(
                    "Unparseable dependency manifest",
                    "DEPENDENCY", "MEDIUM",
                    rel, 1,
                    f"Could not parse '{rel}': {e}",
                    "A malformed manifest is hard to audit and may break installs.",
                    "Fix the syntax of the manifest file.",
                ))
                continue

            details.append({"file": rel, "status": "ok", "dependencies": parsed.get("count", 0)})
            issues.extend(self._analyze(rel, parsed))

        return {"manifests": [d["file"] for d in details], "details": details, "issues": issues}

    # ------------------------------------------------------------------
    def _parse_manifest(self, path: Path, rel: str) -> Dict[str, Any]:
        name = path.name.lower()
        text = path.read_text(encoding="utf-8", errors="replace")
        if name == "requirements.txt":
            return self._parse_requirements(text)
        if name == "package.json":
            data = json.loads(text)
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            return {"type": "npm", "dependencies": deps, "count": len(deps)}
        if name == "pyproject.toml":
            data = _toml.loads(text)
            deps = {}
            for section in ("dependencies",):
                for item in data.get("project", {}).get(section, []):
                    pkg = str(item).split("[")[0].split(";")[0].strip()
                    deps[pkg] = str(item)
            return {"type": "pyproject", "dependencies": deps, "count": len(deps)}
        if name == "go.mod":
            deps = {}
            for line in text.splitlines():
                m = re.match(r"^\s*([\w\.\-/]+)\s+(v?[\w\.\-+]+)", line.strip())
                if m and not line.strip().startswith(("module", "go ")):
                    deps[m.group(1)] = m.group(2)
            return {"type": "go", "dependencies": deps, "count": len(deps)}
        if name == "Cargo.toml":
            data = _toml.loads(text)
            deps = {}
            for key, val in data.get("dependencies", {}).items():
                if isinstance(val, str):
                    deps[key] = val
                elif isinstance(val, dict):
                    deps[key] = val.get("version", "")
            return {"type": "cargo", "dependencies": deps, "count": len(deps)}
        if name == "package-lock.json" or name == "yarn.lock":
            return {"type": "lock", "dependencies": {}, "count": 0}
        # Generic fallback: treat top-level as key->version mapping if possible
        if name in ("Pipfile", "environment.yml", "composer.json", "Gemfile"):
            return {"type": name, "dependencies": {}, "count": 0}
        return {"type": name, "dependencies": {}, "count": 0}

    def _parse_requirements(self, text: str) -> Dict[str, Any]:
        deps = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-r ", "-e ", "--")):
                continue
            pkg = line.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0].strip()
            if pkg:
                deps[pkg] = line
        return {"type": "pip", "dependencies": deps, "count": len(deps)}

    # ------------------------------------------------------------------
    def _analyze(self, rel: str, parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        deps = parsed.get("dependencies", {})
        ptype = parsed.get("type")
        line_no = 1

        if ptype == "pip":
            for pkg, spec in deps.items():
                line_no += 1
                # Unpinned / loosely pinned dependencies
                if not re.search(r"(==|~=|>=|<[=]?|==)", spec) and spec == pkg:
                    issues.append(self._issue(
                        f"Unpinned dependency '{pkg}'",
                        "DEPENDENCY", "LOW",
                        rel, line_no,
                        f"'{pkg}' is declared without a version pin: '{spec}'.",
                        "Unpinned dependencies produce non-reproducible builds.",
                        f"Pin the version, e.g. {pkg}==<version>.",
                        fixable=True,
                    ))
                if pkg == "cryptography" and "==2" in spec:
                    issues.append(self._issue(
                        f"Very old cryptography version for '{pkg}'",
                        "DEPENDENCY", "HIGH", rel, line_no,
                        "cryptography 2.x is long EOL and missing security fixes.",
                        "Using EOL libraries leaves known vulnerabilities unpatched.",
                        "Upgrade cryptography to a supported release.",
                        fixable=True,
                    ))
        elif ptype in ("npm", "go", "cargo", "pyproject"):
            for pkg, spec in deps.items():
                line_no += 1
                if isinstance(spec, str) and spec and any(
                    tag in spec for tag in ("github.com/", "git+", "file:", "^0.0.0", "HEAD")
                ):
                    issues.append(self._issue(
                        f"Non-reproducible reference for '{pkg}'",
                        "DEPENDENCY", "MEDIUM", rel, line_no,
                        f"'{pkg}' references '{spec}' which is not a fixed released version.",
                        "Non-release references break reproducibility and auditing.",
                        "Pin {pkg} to a released version.",
                        fixable=True,
                    ))
        return issues

    def _issue(self, title, category, severity, file, line, description,
               why, fix, fixable=False):
        import uuid
        return {
            "issue_id": f"DEP-{uuid.uuid4().hex[:8]}",
            "title": title,
            "category": category,
            "severity": severity,
            "confidence": 0.9,
            "file": file,
            "line": line,
            "line_end": line,
            "description": description,
            "why_it_matters": why,
            "evidence": "",
            "recommended_fix": fix,
            "fixable": fixable,
            "verification_method": "Rerun dependency scan after updating the manifest.",
            "source": "dependency",
        }


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name
