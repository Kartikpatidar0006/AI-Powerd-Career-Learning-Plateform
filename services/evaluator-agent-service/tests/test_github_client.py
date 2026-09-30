"""
GitHubClient unit tests for evaluator-agent-service (Agent 3).

Verifies:
1. URL parsing (https://github.com/owner/repo, .git suffix, trailing slashes, invalid URLs)
2. 404 Not Found -> GitHubRepoNotFoundError (clean message, no stack trace leaked)
3. Private repo -> GitHubPrivateRepoError (clean message, no stack trace leaked)
4. 403/429 Rate limited -> GitHubRateLimitError with retry-after
5. Network / server error -> GitHubAPIError
"""

import unittest
from unittest.mock import AsyncMock, patch

from app.services.github_client import (
    GitHubAPIError,
    GitHubClient,
    GitHubPrivateRepoError,
    GitHubRateLimitError,
    GitHubRepoNotFoundError,
    parse_github_url,
)


class TestGitHubClient(unittest.IsolatedAsyncioTestCase):
    """Test GitHub API client error handling and static analysis logic."""

    def test_parse_github_url(self) -> None:
        """Verify URL parsing handles various formats and rejects invalid ones."""
        # Standard
        owner, repo = parse_github_url("https://github.com/octocat/Hello-World")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "Hello-World")

        # With trailing slash
        owner, repo = parse_github_url("https://github.com/octocat/Hello-World/")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "Hello-World")

        # With .git suffix
        owner, repo = parse_github_url("https://github.com/octocat/Hello-World.git")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "Hello-World")

        # Invalid URLs raise GitHubAPIError
        with self.assertRaises(GitHubAPIError):
            parse_github_url("https://gitlab.com/octocat/Hello-World")

        with self.assertRaises(GitHubAPIError):
            parse_github_url("https://github.com/octocat")

        with self.assertRaises(GitHubAPIError):
            parse_github_url("not a url")

    async def test_repo_not_found_raises_clean_error(self) -> None:
        """404 from GitHub must raise GitHubRepoNotFoundError without leaking raw response."""
        client = GitHubClient(token="mock-token")
        with patch.object(client, "_get", AsyncMock(side_effect=GitHubRepoNotFoundError("Repository not found", 404))):
            with self.assertRaises(GitHubRepoNotFoundError) as ctx:
                await client.get_repo_metadata("user", "nonexistent")

            self.assertIn("not found", str(ctx.exception).lower())
            self.assertNotIn("Traceback", str(ctx.exception))

    async def test_private_repo_raises_clean_error(self) -> None:
        """Private repo returns private=True in metadata, triggering GitHubPrivateRepoError."""
        client = GitHubClient(token="mock-token")
        # Return repo metadata with private=True
        mock_meta = {
            "name": "secret-repo",
            "private": True,
            "default_branch": "main",
            "created_at": "2026-01-01T00:00:00Z",
            "pushed_at": "2026-01-01T00:00:00Z",
            "size": 100,
        }
        with patch.object(client, "_get", AsyncMock(return_value=mock_meta)):
            with self.assertRaises(GitHubPrivateRepoError) as ctx:
                await client.get_repo_metadata("user", "secret-repo")

            self.assertIn("private", str(ctx.exception).lower())
            self.assertNotIn("Traceback", str(ctx.exception))

    async def test_rate_limited_raises_clean_error(self) -> None:
        """Rate limited response must raise GitHubRateLimitError with clear message."""
        client = GitHubClient(token="mock-token")
        with patch.object(client, "_get", AsyncMock(side_effect=GitHubRateLimitError("GitHub API rate limit exceeded", retry_after=60))):
            with self.assertRaises(GitHubRateLimitError) as ctx:
                await client.get_repo_metadata("user", "repo")

            self.assertIn("rate limit", str(ctx.exception).lower())
            self.assertEqual(ctx.exception.retry_after, 60)
            self.assertNotIn("Traceback", str(ctx.exception))

    async def test_api_server_error_raises_clean_error(self) -> None:
        """Server errors from GitHub map to GitHubAPIError."""
        client = GitHubClient(token="mock-token")
        with patch.object(client, "_get", AsyncMock(side_effect=GitHubAPIError("GitHub API error 500: Internal Server Error", 500))):
            with self.assertRaises(GitHubAPIError) as ctx:
                await client.get_repo_metadata("user", "repo")

            self.assertIn("500", str(ctx.exception))
            self.assertNotIn("Traceback", str(ctx.exception))

    def test_github_api_token_header_when_configured(self) -> None:
        """When GITHUB_API_TOKEN is provided, Authorization: Bearer <token> is configured."""
        token = "ghp_realSecretTokenForTesting123456789"
        client = GitHubClient(token=token)
        self.assertIn("Authorization", client._headers)
        self.assertEqual(client._headers["Authorization"], f"Bearer {token}")

    def test_github_api_token_graceful_fallback_when_missing(self) -> None:
        """When token is missing or placeholder, Authorization header is omitted and no crash occurs."""
        # None
        client_none = GitHubClient(token="")
        self.assertNotIn("Authorization", client_none._headers)

        # Placeholder
        client_placeholder = GitHubClient(token="your-github-personal-access-token-optional")
        self.assertNotIn("Authorization", client_placeholder._headers)


if __name__ == "__main__":
    unittest.main()
