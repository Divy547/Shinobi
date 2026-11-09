"""Unit tests for GitHubClient reliability, non-retryable errors, secret redaction, and SSRF prevention."""

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from repovet_mcp.services.github_client import (
    GitHubAPIError,
    GitHubClient,
    RepositoryNotFoundError,
    parse_repository_target,
)


def test_parse_repository_target_blocks_ssrf() -> None:
    """Verify parse_repository_target rejects non-GitHub domains and local loopbacks."""
    with pytest.raises(ValueError, match="Only authorized GitHub domains"):
        parse_repository_target("https://localhost/owner/repo")

    with pytest.raises(ValueError, match="Only authorized GitHub domains"):
        parse_repository_target("https://10.0.0.1/owner/repo")

    with pytest.raises(ValueError, match="Only authorized GitHub domains"):
        parse_repository_target("https://gitlab.com/owner/repo")


@pytest.mark.asyncio
async def test_github_client_non_retryable_404() -> None:
    """Verify HTTP 404 raises RepositoryNotFoundError immediately without retries."""
    client = GitHubClient(token="ghp_test_secret_123")
    mock_response = httpx.Response(
        status_code=404,
        request=httpx.Request("GET", "https://api.github.com/repos/unknown/missing"),
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    with pytest.raises(RepositoryNotFoundError, match="not found"):
        await client.get_repository(mock_client, "unknown", "missing")

    # Must not retry: call count exactly 1
    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
async def test_github_client_non_retryable_401_redacts_secret() -> None:
    """Verify HTTP 401 raises GitHubAPIError immediately and redacts authorization tokens."""
    secret_token = "ghp_my_super_secret_token_12345678"
    client = GitHubClient(token=secret_token)
    mock_response = httpx.Response(
        status_code=401,
        request=httpx.Request(
            "GET",
            "https://api.github.com/repos/private/repo",
            headers={"Authorization": f"Bearer {secret_token}"},
        ),
        json={"message": f"Bad credentials with token {secret_token}"},
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    with pytest.raises(GitHubAPIError) as exc_info:
        await client.get_repository(mock_client, "private", "repo")

    # Must not retry: call count exactly 1
    assert mock_client.get.call_count == 1
    # Token must be redacted from error message
    assert secret_token not in str(exc_info.value)
    assert "[REDACTED_SECRET]" in str(exc_info.value)


@pytest.mark.asyncio
async def test_github_client_cancelled_error_propagates() -> None:
    """Verify asyncio.CancelledError propagates cleanly without being converted to GitHubAPIError."""
    client = GitHubClient()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await client.get_repository(mock_client, "test", "test")
