"""
GitHub repository ingestion for Code Doctor AI.

Safely fetches a public GitHub repository (as a zip archive, avoids executing
any repository code), extracts it into an isolated temporary directory, and
provides safe path helpers.
"""
import os
import re
import shutil
import tempfile
import urllib.request
import urllib.error
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional

GITHUB_REPO_RE = re.compile(
    r"^https?://(?:www\.)?github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)"
    r"(?:\.git)?/?$",
    re.IGNORECASE,
)


class RepositoryError(Exception):
    """Raised when repository ingestion fails."""


class Repository:
    """Fetched GitHub repository held in a safe temporary directory."""

    def __init__(self, root: Path, owner: str, repo: str, branch: str):
        self.root = root
        self.owner = owner
        self.repo = repo
        self.branch = branch
        self._temp_dir: Optional[tempfile.TemporaryDirectory] = None

    @property
    def name(self) -> str:
        return f"{self.owner}/{self.repo}"

    @property
    def safe_root(self) -> Path:
        """The canonical root, resolved to guard against traversal."""
        return self.root.resolve()

    def is_within(self, path: Path) -> bool:
        """Return True if `path` resolves inside the safe root."""
        try:
            path.resolve().relative_to(self.safe_root)
            return True
        except ValueError:
            return False

    def cleanup(self) -> None:
        """Remove the temporary directory and all resources."""
        if self._temp_dir is not None:
            try:
                self._temp_dir.cleanup()
            except Exception:
                pass
            self._temp_dir = None

    def __enter__(self) -> "Repository":
        return self

    def __exit__(self, *exc) -> None:
        self.cleanup()

    @classmethod
    def parse_url(cls, url: str) -> Dict[str, Optional[str]]:
        """Return dict with owner/repo/branch or an error message."""
        url = (url or "").strip()
        if not url:
            return {"error": "No repository URL provided."}
        match = GITHUB_REPO_RE.match(url)
        if not match:
            return {
                "error": (
                    "Invalid GitHub repository URL. Expected format: "
                    "https://github.com/<owner>/<repo>"
                )
            }
        repo = match.group("repo")
        if repo.lower().endswith(".git"):
            repo = repo[:-4]
        return {
            "owner": match.group("owner"),
            "repo": repo,
            "branch": None,
        }

    @classmethod
    def _resolve_branch(cls, owner: str, repo: str, timeout: int) -> str:
        """Determine the default branch via the GitHub API."""
        api = f"https://api.github.com/repos/{owner}/{repo}"
        req = urllib.request.Request(api, headers={"Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                import json
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("default_branch", "main")
        except Exception:
            # Fall back to common default branch names
            for candidate in ("main", "master"):
                probe = f"https://raw.githubusercontent.com/{owner}/{repo}/{candidate}/README.md"
                try:
                    with urllib.request.urlopen(probe, timeout=timeout):
                        return candidate
                except Exception:
                    continue
            raise RepositoryError(
                f"Repository '{owner}/{repo}' not found or is not accessible."
            )

    @classmethod
    def fetch(cls, url: str, timeout: int = 30) -> "Repository":
        """Fetch a repository from a GitHub URL into a clean temporary dir."""
        parsed = cls.parse_url(url)
        if "error" in parsed:
            raise RepositoryError(parsed["error"])

        owner, repo = parsed["owner"], parsed["repo"]
        branch = parsed["branch"] or cls._resolve_branch(owner, repo, timeout)

        archive_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"

        temp_dir = tempfile.TemporaryDirectory(prefix="codedoctor_")
        zip_path = Path(temp_dir.name) / "repo.zip"
        extract_root = Path(temp_dir.name) / "repo"

        try:
            req = urllib.request.Request(
                archive_url, headers={"User-Agent": "CodeDoctorAI"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                with open(zip_path, "wb") as fh:
                    shutil.copyfileobj(resp, fh)

            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(extract_root)

            # The archive extracts into <owner>-<repo>-<branch>/; find it safely.
            extracted = _find_single_top_level_dir(extract_root)
            if extracted is None:
                raise RepositoryError("Repository archive appeared empty.")

            repo_obj = cls(extracted, owner, repo, branch)
            repo_obj._temp_dir = temp_dir
            return repo_obj

        except RepositoryError:
            temp_dir.cleanup()
            raise
        except urllib.error.HTTPError as e:
            temp_dir.cleanup()
            if e.code == 404:
                raise RepositoryError(
                    f"Repository '{owner}/{repo}' was not found (404)."
                )
            raise RepositoryError(f"Failed to download repository (HTTP {e.code}).")
        except urllib.error.URLError as e:
            temp_dir.cleanup()
            raise RepositoryError(f"Network error while fetching repository: {e.reason}")
        except zipfile.BadZipFile:
            temp_dir.cleanup()
            raise RepositoryError("Downloaded archive was invalid or empty.")
        except Exception as e:
            temp_dir.cleanup()
            raise RepositoryError(f"Failed to fetch repository: {str(e)}")

    @classmethod
    def check_exists(cls, url: str, timeout: int = 30) -> Dict[str, Any]:
        """Lightweight existence check without downloading the full archive."""
        parsed = cls.parse_url(url)
        if "error" in parsed:
            return {"success": False, "message": parsed["error"], "branch": None}
        owner, repo = parsed["owner"], parsed["repo"]
        try:
            branch = cls._resolve_branch(owner, repo, timeout)
        except RepositoryError as e:
            return {"success": False, "message": str(e), "branch": None}
        return {
            "success": True,
            "message": f"Repository found ({owner}/{repo}).",
            "owner": owner,
            "repo": repo,
            "branch": branch,
        }


def _find_single_top_level_dir(root: Path) -> Optional[Path]:
    """Return the single top-level directory inside an extracted archive."""
    entries = [p for p in root.iterdir()]
    if not entries:
        return None
    # Prefer the first directory; if multiple, fall back to files present.
    for entry in sorted(entries, key=lambda p: p.name):
        if entry.is_dir():
            return entry
    return root


def detect_repository_size(repo: Repository, max_bytes: int) -> Dict[str, Any]:
    """Walk the repository and estimate the size of relevant text files."""
    total = 0
    file_count = 0
    for dirpath, dirnames, filenames in os.walk(repo.safe_root):
        dirnames[:] = [
            d for d in dirnames if d not in ConfigLike().IGNORED_DIRS
        ]
        for name in filenames:
            p = Path(dirpath) / name
            if not repo.is_within(p):
                continue
            try:
                total += p.stat().st_size
                file_count += 1
            except OSError:
                continue
    return {"size_bytes": total, "file_count": file_count}


class ConfigLike:
    IGNORED_DIRS = {
        ".git", "node_modules", "venv", ".venv", "__pycache__", "dist",
        "build", "coverage", ".pytest_cache", ".tox", ".mypy_cache",
        ".idea", ".vscode", "target", ".next", "site-packages", "Pods",
        ".gradle", ".svn", ".hg", ".cache",
    }
