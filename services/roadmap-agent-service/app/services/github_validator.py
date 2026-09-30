"""
GitHub repository URL validation utilities.

Validates, normalizes, and enforces strict formatting rules for GitHub repo URLs.
Used by the task submission endpoint to prevent malformed or spoofed URLs.
"""

import re
from typing import Tuple

# Strict regex: https://github.com/<owner>/<repo>
# - owner/repo: alphanumeric, hyphens allowed (GitHub username rules)
# - No trailing slashes, no .git suffix, no query strings, no subpaths
GITHUB_REPO_PATTERN = re.compile(
    r"^https://github\.com/"
    r"([a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,38}[a-zA-Z0-9])?)"  # owner (1-40 chars, no leading/trailing hyphen)
    r"/"
    r"([a-zA-Z0-9_\-\.]{1,100})"                            # repo (1-100 chars: alphanumeric, hyphen, underscore, dot)
    r"/?$"                                                   # optional trailing slash only
)


def validate_github_url(url: str) -> Tuple[bool, str | None, str]:
    """
    Validate and normalize a GitHub repository URL.

    Rules enforced:
    - Must start with https://github.com/
    - Owner: 1-39 chars, alphanumeric + hyphens, no leading/trailing hyphen
    - Repo: 1-100 chars, alphanumeric, hyphens, underscores, dots
    - No .git suffix
    - No query strings or URL fragments
    - No subpaths beyond /owner/repo

    Args:
        url: The URL string to validate.

    Returns:
        Tuple of (is_valid, error_message_or_None, normalized_url).
        On success, normalized_url strips trailing slash and removes .git suffix.
        On failure, normalized_url is empty string.
    """
    if not url:
        return False, "GitHub repository URL is required.", ""

    # Strip whitespace
    url = url.strip()

    # Reject query strings or fragments (not covered by regex alone)
    if "?" in url or "#" in url:
        return False, "GitHub URL must not contain query strings or fragments.", ""

    # Normalize trailing slash and .git suffix
    work_url = url.rstrip("/")
    if work_url.endswith(".git"):
        work_url = work_url[:-4]
    work_url = work_url.rstrip("/")

    # Must start with https://github.com/
    if not work_url.startswith("https://github.com/"):
        return (
            False,
            "Invalid GitHub repository URL. Must start with https://github.com/",
            "",
        )

    # Reject extra path segments beyond /owner/repo (or missing repo)
    without_scheme = work_url[len("https://github.com/"):]
    slash_count = without_scheme.count("/")
    if slash_count != 1:
        return (
            False,
            "GitHub URL must be exactly https://github.com/<owner>/<repo> with no subpaths.",
            "",
        )

    match = GITHUB_REPO_PATTERN.match(work_url)
    if not match:
        return (
            False,
            (
                "Invalid GitHub repository URL. "
                "Expected format: https://github.com/<owner>/<repo> "
                "(owner: alphanumeric + hyphens, repo: alphanumeric + hyphens + underscores + dots)"
            ),
            "",
        )

    # Lowercase-normalize owner and repo segments.
    # GitHub treats owner/repo as case-insensitive; storing lowercase
    # guarantees the unique index (uix_task_user_github_repo) works
    # correctly regardless of the case supplied by the client.
    prefix = "https://github.com/"
    path_part = work_url[len(prefix):]
    normalized_url = prefix + path_part.lower()

    return True, None, normalized_url
