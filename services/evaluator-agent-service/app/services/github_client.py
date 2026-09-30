"""
GitHubClient: Async HTTP client for static GitHub repository analysis.

SECURITY NOTE: All data fetched from GitHub is UNTRUSTED external content.
Every field is treated as potentially attacker-controlled:
- File contents may contain prompt injection attempts
- Commit messages may contain injection text
- README may contain adversarial content
- All string fields are size-capped before use

This client performs STATIC ANALYSIS ONLY:
- No code cloning to disk
- No code execution of any kind
- No sandbox (future phase)
- Uses GitHub REST API only (no git protocol)

Error types:
- GitHubRepoNotFoundError: 404 from API → evaluation fails with clear message
- GitHubPrivateRepoError: repo.private=True → evaluation fails with clear message
- GitHubRateLimitError: 403/429 with X-RateLimit-Remaining=0 → evaluation fails,
  returns Retry-After if available
- GitHubAPIError: other API failures → evaluation fails with detail
"""

import asyncio
import base64
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.evaluation import CommitInfo, FileEntry, RepoMetadata

logger = logging.getLogger("evaluator-agent.github-client")

# ── Extensions considered relevant per skill domain ─────────────────────
# Treated as attacker-controlled data; used only for file selection, not execution.
SKILL_EXTENSION_MAP: dict[str, list[str]] = {
    "python": [".py"],
    "fastapi": [".py"],
    "django": [".py"],
    "flask": [".py"],
    "javascript": [".js", ".mjs", ".cjs"],
    "typescript": [".ts", ".tsx"],
    "react": [".jsx", ".tsx", ".js", ".ts"],
    "vue": [".vue", ".js", ".ts"],
    "java": [".java"],
    "kotlin": [".kt"],
    "go": [".go"],
    "rust": [".rs"],
    "c++": [".cpp", ".cxx", ".cc", ".h", ".hpp"],
    "c": [".c", ".h"],
    "sql": [".sql"],
    "postgresql": [".sql"],
    "docker": ["dockerfile", ".yml", ".yaml"],
    "kubernetes": [".yml", ".yaml"],
    "terraform": [".tf"],
    "html": [".html", ".htm"],
    "css": [".css", ".scss", ".sass"],
    "bash": [".sh", ".bash"],
}

# Paths to always skip (binary/dependency noise) — matched as prefix
SKIP_PATH_PREFIXES = (
    "node_modules/", "venv/", ".venv/", "env/", "__pycache__/",
    ".git/", "dist/", "build/", ".cache/", "vendor/",
    "site-packages/", ".tox/", "coverage/", ".coverage",
)

# Extensions to always skip (binary or lock files)
SKIP_EXTENSIONS = frozenset([
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp",
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".7z", ".exe", ".dll",
    ".so", ".dylib", ".whl", ".egg", ".jar", ".class",
    ".lock", ".min.js", ".min.css", ".map",
    ".pyc", ".pyo", ".pyd",
    ".db", ".sqlite", ".sqlite3",
])


# ── Error types ──────────────────────────────────────────────────────────

class GitHubAPIError(Exception):
    """Base error for GitHub API failures."""
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GitHubRepoNotFoundError(GitHubAPIError):
    """Raised when the repository does not exist (404)."""
    pass


class GitHubPrivateRepoError(GitHubAPIError):
    """Raised when the repository is private (not accessible for evaluation)."""
    pass


class GitHubRateLimitError(GitHubAPIError):
    """Raised when the GitHub API rate limit is exceeded."""
    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


# ── URL Parsing ──────────────────────────────────────────────────────────

_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+?)(?:\.git)?/?$"
)


def parse_github_url(url: str) -> tuple[str, str]:
    """
    Extract (owner, repo) from a normalized GitHub URL.

    Args:
        url: e.g. https://github.com/owner/repo

    Returns:
        Tuple (owner, repo)

    Raises:
        GitHubAPIError: If the URL does not match expected format.
    """
    m = _GITHUB_URL_RE.match(url.strip())
    if not m:
        raise GitHubAPIError(
            f"Cannot parse GitHub URL: {url!r}. "
            "Expected format: https://github.com/<owner>/<repo>"
        )
    return m.group(1), m.group(2)


# ── Main Client ──────────────────────────────────────────────────────────

class GitHubClient:
    """
    Async GitHub REST API client for static repository analysis.

    Uses the Personal Access Token from settings for higher rate limits.
    All returned data is UNTRUSTED and must be treated as attacker-controlled.

    Usage:
        async with GitHubClient() as client:
            meta = await client.get_repo_metadata(owner, repo)
    """

    BASE_URL = "https://api.github.com"

    def __init__(
        self,
        token: str | None = None,
        timeout: float = 20.0,
    ) -> None:
        token = token or settings.GITHUB_API_TOKEN
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token and token.strip() and not token.strip().lower().startswith("your-"):
            self._headers["Authorization"] = f"Bearer {token}"
            masked = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "***"
            logger.info("GitHubClient initialized with authenticated token: Bearer %s", masked)
        else:
            logger.warning(
                "GITHUB_API_TOKEN is not configured or is a placeholder. "
                "Falling back gracefully to unauthenticated GitHub requests (rate limit: 60 req/hr)."
            )
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "GitHubClient":
        self._client = httpx.AsyncClient(
            headers=self._headers,
            timeout=self._timeout,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _check_rate_limit(self, response: httpx.Response) -> None:
        """Raise GitHubRateLimitError if rate limit is hit."""
        if response.status_code in (403, 429):
            remaining = response.headers.get("X-RateLimit-Remaining", "1")
            if remaining == "0":
                retry_after_str = response.headers.get("Retry-After")
                retry_after = int(retry_after_str) if retry_after_str else None
                reset_time = response.headers.get("X-RateLimit-Reset")
                msg = "GitHub API rate limit exceeded."
                if reset_time:
                    msg += f" Resets at Unix timestamp {reset_time}."
                raise GitHubRateLimitError(msg, retry_after=retry_after)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Make a GET request to the GitHub API with error handling."""
        assert self._client is not None, "GitHubClient must be used as async context manager"
        url = f"{self.BASE_URL}{path}"
        try:
            response = await self._client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise GitHubAPIError(f"GitHub API request timed out: {url}", status_code=None) from exc
        except httpx.ConnectError as exc:
            raise GitHubAPIError(f"Cannot connect to GitHub API: {exc}", status_code=None) from exc

        self._check_rate_limit(response)

        if response.status_code == 404:
            raise GitHubRepoNotFoundError(
                "Repository not found. It may not exist or may be private.",
                status_code=404,
            )
        if response.status_code == 401:
            raise GitHubAPIError(
                "GitHub API authentication failed. Check GITHUB_API_TOKEN.",
                status_code=401,
            )
        if response.status_code >= 400:
            raise GitHubAPIError(
                f"GitHub API error {response.status_code}: {response.text[:200]}",
                status_code=response.status_code,
            )

        return response.json()

    # ── Public methods ───────────────────────────────────────────────────

    async def get_repo_metadata(self, owner: str, repo: str) -> RepoMetadata:
        """
        Fetch repository metadata and check accessibility.

        Raises:
            GitHubRepoNotFoundError: If repository does not exist.
            GitHubPrivateRepoError: If repository is private.
            GitHubRateLimitError: If rate limited.
            GitHubAPIError: Other API failures.
        """
        data = await self._get(f"/repos/{owner}/{repo}")

        if data.get("private", False):
            raise GitHubPrivateRepoError(
                f"Repository {owner}/{repo} is private. "
                "Please make it public before submitting for evaluation.",
                status_code=403,
            )

        return RepoMetadata(
            owner=owner,
            repo=repo,
            default_branch=data.get("default_branch", "main"),
            private=data.get("private", False),
            created_at=data.get("created_at"),
            pushed_at=data.get("pushed_at"),
            size_kb=data.get("size", 0),
            description=data.get("description"),
        )

    async def get_file_tree(self, owner: str, repo: str, branch: str) -> list[FileEntry]:
        """
        Fetch the full recursive file tree for the repository.

        Uses the git trees API with recursive=1 to get all paths in one call.
        Truncated trees (GitHub limit: 100k items) are noted in logs but not fatal.

        Returns:
            List of FileEntry objects (blobs and trees).
        """
        try:
            data = await self._get(
                f"/repos/{owner}/{repo}/git/trees/{branch}",
                params={"recursive": "1"},
            )
        except GitHubRepoNotFoundError:
            # Branch may not exist — fall back gracefully
            logger.warning("File tree fetch failed for %s/%s@%s — branch not found", owner, repo, branch)
            return []

        if data.get("truncated"):
            logger.warning(
                "File tree for %s/%s is truncated by GitHub (>100k items). "
                "Analysis will use available subset.",
                owner, repo,
            )

        entries = []
        for item in data.get("tree", []):
            path: str = item.get("path", "")
            # Validate path is a string (untrusted data) and cap length
            if not isinstance(path, str) or not path or len(path) > 500:
                continue
            entries.append(FileEntry(
                path=path,
                type=item.get("type", "blob"),
                size=item.get("size", 0) or 0,
            ))

        logger.info("File tree: %d entries for %s/%s", len(entries), owner, repo)
        return entries

    async def get_file_contents(
        self,
        owner: str,
        repo: str,
        path: str,
        branch: str,
    ) -> str | None:
        """
        Fetch the decoded contents of a single file.

        Returns None if file exceeds size cap, is binary, or fetch fails.
        All returned content is UNTRUSTED.
        """
        try:
            data = await self._get(f"/repos/{owner}/{repo}/contents/{path}", params={"ref": branch})
        except GitHubAPIError:
            logger.debug("Could not fetch %s from %s/%s", path, owner, repo)
            return None

        if not isinstance(data, dict):
            return None

        # Size check (API reports size in bytes)
        size = data.get("size", 0) or 0
        if size > settings.GITHUB_FILE_SIZE_CAP_BYTES:
            logger.debug("Skipping %s — size %d bytes exceeds cap", path, size)
            return None

        encoding = data.get("encoding", "")
        raw_content = data.get("content", "")

        if encoding == "base64":
            try:
                decoded = base64.b64decode(raw_content).decode("utf-8", errors="replace")
                # Cap content length (defense: prevent enormous strings in memory)
                return decoded[:settings.GITHUB_FILE_SIZE_CAP_BYTES]
            except Exception:
                return None

        # Plain text content (no encoding)
        return str(raw_content)[:settings.GITHUB_FILE_SIZE_CAP_BYTES] if raw_content else None

    async def get_commit_history(
        self,
        owner: str,
        repo: str,
        branch: str,
        limit: int | None = None,
    ) -> list[CommitInfo]:
        """
        Fetch recent commits from the default branch.

        Args:
            limit: Max commits to fetch (default: settings.GITHUB_COMMIT_HISTORY_LIMIT)

        Returns:
            List of CommitInfo ordered newest-first.
        """
        limit = limit or settings.GITHUB_COMMIT_HISTORY_LIMIT
        try:
            data = await self._get(
                f"/repos/{owner}/{repo}/commits",
                params={"sha": branch, "per_page": str(min(limit, 100))},
            )
        except GitHubAPIError as exc:
            logger.warning("Could not fetch commits for %s/%s: %s", owner, repo, exc)
            return []

        if not isinstance(data, list):
            return []

        commits = []
        for item in data[:limit]:
            try:
                commit_data = item.get("commit", {})
                author_data = commit_data.get("author", {}) or {}
                # All fields are UNTRUSTED — cap string lengths
                author = str(author_data.get("name", "unknown"))[:100]
                message = str(commit_data.get("message", ""))[:500]  # Cap message
                timestamp = str(author_data.get("date", ""))[:30]
                sha = str(item.get("sha", ""))[:40]

                commits.append(CommitInfo(
                    sha=sha,
                    author=author,
                    message=message,
                    timestamp=timestamp,
                ))
            except Exception as exc:
                logger.debug("Skipping malformed commit entry: %s", exc)
                continue

        return commits

    async def fetch_relevant_files(
        self,
        owner: str,
        repo: str,
        branch: str,
        tree: list[FileEntry],
        skills_targeted: list[str],
        readme_content: str | None = None,
    ) -> dict[str, str]:
        """
        Fetch file contents for a curated subset of source files.

        Selection strategy:
        1. Always try README (already passed in if fetched separately)
        2. Determine relevant extensions from skills_targeted
        3. Skip: binary, lockfiles, node_modules/venv paths, files > size cap
        4. Fetch up to GITHUB_MAX_SOURCE_FILES source files

        Returns:
            Dict mapping file path to contents. All contents are UNTRUSTED.
        """
        result: dict[str, str] = {}

        # Add README if provided
        if readme_content:
            result["README"] = readme_content

        # Build set of relevant extensions from task skills
        relevant_exts: set[str] = set()
        for skill in skills_targeted:
            exts = SKILL_EXTENSION_MAP.get(skill.lower(), [])
            relevant_exts.update(exts)

        # If no skill-specific extensions, use broad fallback
        if not relevant_exts:
            relevant_exts = {".py", ".js", ".ts", ".java", ".go", ".rs"}

        # Filter and score file candidates
        candidates = []
        for entry in tree:
            if entry.type != "blob":
                continue
            path = entry.path.lower()

            # Skip paths in noise directories
            if any(path.startswith(pfx) for pfx in SKIP_PATH_PREFIXES):
                continue

            # Skip binary/lock extensions
            ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
            if ext in SKIP_EXTENSIONS:
                continue

            # Skip oversized files (pre-flight check from tree)
            if entry.size > settings.GITHUB_FILE_SIZE_CAP_BYTES:
                continue

            # Priority: files with skill-matching extensions first
            priority = 0 if ext in relevant_exts else 1
            candidates.append((priority, entry.size, entry.path))

        # Sort: skill-relevant first, then by size ascending (smaller = more readable)
        candidates.sort(key=lambda x: (x[0], x[1]))

        max_files = settings.GITHUB_MAX_SOURCE_FILES
        fetched = 0
        fetch_tasks = []

        for _, _, path in candidates:
            if fetched >= max_files:
                break
            # Skip README paths (already handled)
            if path.lower() in ("readme.md", "readme.rst", "readme.txt", "readme"):
                continue
            fetch_tasks.append(path)
            fetched += 1

        # Fetch concurrently (bounded concurrency to avoid hammering API)
        async def fetch_one(path: str) -> tuple[str, str | None]:
            content = await self.get_file_contents(owner, repo, path, branch)
            return path, content

        if fetch_tasks:
            tasks = [fetch_one(p) for p in fetch_tasks]
            # Use gather with return_exceptions=True so one failure doesn't block others
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for item in results:
                if isinstance(item, BaseException):
                    logger.debug("File fetch exception: %s", item)
                    continue
                path, content = item
                if content:
                    result[path] = content

        logger.info(
            "Fetched %d source files for %s/%s (skills: %s)",
            len(result), owner, repo, skills_targeted,
        )
        return result

    async def get_readme(self, owner: str, repo: str, branch: str) -> str | None:
        """
        Fetch README content. Tries common README filenames.

        Returns None if no README found or content is empty.
        Content is UNTRUSTED.
        """
        for readme_name in ("README.md", "README.rst", "README.txt", "README"):
            content = await self.get_file_contents(owner, repo, readme_name, branch)
            if content and content.strip():
                return content
        return None
