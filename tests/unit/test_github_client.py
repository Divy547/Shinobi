"""Unit tests for GitHub REST client and target URL parsing."""

import httpx
import pytest

from repovet_mcp.services.github_client import (
    GitHubClient,
    RateLimitExceededError,
    RepositoryNotFoundError,
    parse_repository_target,
)


def test_parse_repository_target_valid() -> None:
    """Verify target parsing across various URL and shorthand forms."""
    assert parse_repository_target("pallets/flask") == ("pallets", "flask")
    assert parse_repository_target("https://github.com/pallets/flask") == ("pallets", "flask")
    assert parse_repository_target("https://github.com/pallets/flask.git") == ("pallets", "flask")
    assert parse_repository_target("http://github.com/pallets/flask/") == ("pallets", "flask")
    assert parse_repository_target("git@github.com:pallets/flask.git") == ("pallets", "flask")


def test_parse_repository_target_invalid() -> None:
    """Verify ValueError is raised on unparseable target strings."""
    with pytest.raises(ValueError, match="Unable to parse repository"):
        parse_repository_target("invalid-target-format")

    with pytest.raises(ValueError, match="Unable to parse repository"):
        parse_repository_target("https://notgithub.com")


@pytest.mark.asyncio
async def test_github_client_auth_headers() -> None:
    """Verify GitHubClient attaches token to headers when provided."""
    client_unauth = GitHubClient(token=None)
    assert "Authorization" not in client_unauth.headers

    client_auth = GitHubClient(token="ghp_test_secret_token")
    assert client_auth.headers["Authorization"] == "Bearer ghp_test_secret_token"


@pytest.mark.asyncio
async def test_github_client_rate_limit_exceeded() -> None:
    """Verify RateLimitExceededError is raised when GitHub returns 403 with rate limit message."""

    def mock_rate_limit_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1790000000"},
            text="API rate limit exceeded for user.",
        )

    transport = httpx.MockTransport(mock_rate_limit_handler)
    async with httpx.AsyncClient(transport=transport) as test_client:
        gh = GitHubClient()
        with pytest.raises(RateLimitExceededError, match="rate limit"):
            await gh._request(test_client, "/repos/owner/repo")


@pytest.mark.asyncio
async def test_github_client_repo_not_found() -> None:
    """Verify RepositoryNotFoundError is raised when repo returns 404."""

    def mock_not_found_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    transport = httpx.MockTransport(mock_not_found_handler)
    async with httpx.AsyncClient(transport=transport) as test_client:
        gh = GitHubClient()
        with pytest.raises(RepositoryNotFoundError, match="not found"):
            await gh.get_repository(test_client, "owner", "missing-repo")
