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

    with pytest.raises(ValueError, match="Invalid repository URL host"):
        parse_repository_target("https://notgithub.com")

    with pytest.raises(ValueError, match="Unable to parse repository"):
        parse_repository_target("https://github.com")


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
async def test_github_client_rate_limit_successful_response() -> None:
    """Verify HTTP 200 with x-ratelimit-remaining=0 returns payload without error."""

    def mock_final_call_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1790000000"},
            json={"name": "test-repo", "stargazers_count": 42},
        )

    transport = httpx.MockTransport(mock_final_call_handler)
    async with httpx.AsyncClient(transport=transport) as test_client:
        gh = GitHubClient()
        data = await gh._request(test_client, "/repos/owner/test-repo")
        assert data["name"] == "test-repo"
        assert data["stargazers_count"] == 42


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


@pytest.mark.asyncio
async def test_collect_repository_data_tracks_errors() -> None:
    """Verify collect_repository_data captures partial endpoint errors in errors dictionary."""

    def mock_partial_failure_handler(request: httpx.Request) -> httpx.Response:
        url_path = request.url.path
        if url_path == "/repos/owner/repo":
            return httpx.Response(200, json={"name": "repo", "owner": {"login": "owner"}})
        if "commits" in url_path:
            return httpx.Response(500, text="Internal Server Error")
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(mock_partial_failure_handler)
    gh = GitHubClient()
    # monkeypatch httpx.AsyncClient inside collect_repository_data
    original_client = httpx.AsyncClient

    def mock_async_client(**kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original_client(**kwargs)  # type: ignore[arg-type]

    import unittest.mock

    with unittest.mock.patch("httpx.AsyncClient", side_effect=mock_async_client):
        result = await gh.collect_repository_data("owner", "repo")
        assert "errors" in result
        assert "commits" in result["errors"]
        assert result["commits"] == []


@pytest.mark.asyncio
async def test_collect_repository_data_fetches_pr_comments_without_comments_field() -> None:
    """Verify PR conversation comments are collected even when PR list item lacks a 'comments' field."""
    pr_number = 42
    comment_payload = [
        {
            "id": 1001,
            "body": "Thank you for the pull request!",
            "created_at": "2026-11-01T12:00:00Z",
            "user": {"login": "maintainer", "type": "User"},
        }
    ]

    def mock_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/repos/owner/repo":
            return httpx.Response(200, json={"name": "repo", "owner": {"login": "owner"}})
        if path == "/repos/owner/repo/pulls":
            # Real GitHub PR list items do not include a "comments" key
            return httpx.Response(
                200,
                json=[
                    {
                        "number": pr_number,
                        "title": "Add feature",
                        "state": "open",
                        "user": {"login": "contributor"},
                    }
                ],
            )
        if path == f"/repos/owner/repo/pulls/{pr_number}/reviews":
            return httpx.Response(200, json=[])
        if path == f"/repos/owner/repo/issues/{pr_number}/comments":
            return httpx.Response(200, json=comment_payload)
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(mock_handler)
    gh = GitHubClient()
    original_client = httpx.AsyncClient

    def mock_async_client(**kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original_client(**kwargs)  # type: ignore[arg-type]

    import unittest.mock

    with unittest.mock.patch("httpx.AsyncClient", side_effect=mock_async_client):
        result = await gh.collect_repository_data("owner", "repo")
        assert pr_number in result["sampled_pr_comments"]
        comments = result["sampled_pr_comments"][pr_number]
        assert len(comments) == 1
        assert comments[0]["body"] == "Thank you for the pull request!"


@pytest.mark.asyncio
async def test_collect_repository_data_pr_comments_empty_and_api_failure() -> None:
    """Verify PR comment fetching handles empty lists and API failures without crashing."""

    def mock_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/repos/owner/repo":
            return httpx.Response(200, json={"name": "repo", "owner": {"login": "owner"}})
        if path == "/repos/owner/repo/pulls":
            return httpx.Response(
                200,
                json=[
                    {"number": 10, "title": "PR with empty comments"},
                    {"number": 20, "title": "PR with failing comments endpoint"},
                ],
            )
        if path == "/repos/owner/repo/issues/10/comments":
            return httpx.Response(200, json=[])  # Empty comment list
        if path == "/repos/owner/repo/issues/20/comments":
            return httpx.Response(500, text="Internal Server Error")
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(mock_handler)
    gh = GitHubClient()
    original_client = httpx.AsyncClient

    def mock_async_client(**kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original_client(**kwargs)  # type: ignore[arg-type]

    import unittest.mock

    with unittest.mock.patch("httpx.AsyncClient", side_effect=mock_async_client):
        result = await gh.collect_repository_data("owner", "repo")
        # PR 10 comments should be an empty list
        assert 10 in result["sampled_pr_comments"]
        assert result["sampled_pr_comments"][10] == []
        # PR 20 comment call failed, should be omitted without crashing
        assert 20 not in result["sampled_pr_comments"]
        assert len(result["pull_requests"]) == 2


@pytest.mark.asyncio
async def test_collect_repository_data_bounded_targeted_docs_inspection() -> None:
    """Verify bounded inspection queries docs, docs/outreach, and .github when parent directories exist."""
    requested_paths: list[str] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        requested_paths.append(path)
        if path == "/repos/owner/repo":
            return httpx.Response(200, json={"name": "repo", "owner": {"login": "owner"}})
        if path == "/repos/owner/repo/contents/":
            return httpx.Response(
                200,
                json=[
                    {"name": "README.md", "type": "file"},
                    {"name": "docs", "type": "dir"},
                    {"name": ".github", "type": "dir"},
                ],
            )
        if path == "/repos/owner/repo/contents/docs":
            return httpx.Response(
                200,
                json=[
                    {"name": "index.md", "type": "file"},
                    {"name": "outreach", "type": "dir"},
                ],
            )
        if path == "/repos/owner/repo/contents/docs/outreach":
            return httpx.Response(
                200,
                json=[
                    {"name": "gsoc.md", "path": "docs/outreach/gsoc.md", "type": "file"},
                ],
            )
        if path == "/repos/owner/repo/contents/.github":
            return httpx.Response(
                200,
                json=[
                    {"name": "workflows", "type": "dir"},
                ],
            )
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(mock_handler)
    gh = GitHubClient()
    original_client = httpx.AsyncClient

    def mock_async_client(**kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original_client(**kwargs)  # type: ignore[arg-type]

    import unittest.mock

    with unittest.mock.patch("httpx.AsyncClient", side_effect=mock_async_client):
        result = await gh.collect_repository_data("owner", "repo")
        assert "targeted_contents" in result
        assert "docs" in result["targeted_contents"]
        assert "docs/outreach" in result["targeted_contents"]
        assert ".github" in result["targeted_contents"]
        assert result["targeted_contents"]["docs/outreach"][0]["name"] == "gsoc.md"


@pytest.mark.asyncio
async def test_collect_repository_data_skips_missing_targeted_dirs() -> None:
    """Verify bounded inspection skips docs/outreach when docs directory is absent in root."""
    requested_paths: list[str] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        requested_paths.append(path)
        if path == "/repos/owner/repo":
            return httpx.Response(200, json={"name": "repo", "owner": {"login": "owner"}})
        if path == "/repos/owner/repo/contents/":
            return httpx.Response(
                200,
                json=[
                    {"name": "README.md", "type": "file"},
                    {"name": "src", "type": "dir"},
                ],
            )
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(mock_handler)
    gh = GitHubClient()
    original_client = httpx.AsyncClient

    def mock_async_client(**kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original_client(**kwargs)  # type: ignore[arg-type]

    import unittest.mock

    with unittest.mock.patch("httpx.AsyncClient", side_effect=mock_async_client):
        result = await gh.collect_repository_data("owner", "repo")
        assert "targeted_contents" in result
        assert "docs" not in result["targeted_contents"]
        assert "docs/outreach" not in result["targeted_contents"]
        assert ".github" not in result["targeted_contents"]
        assert "/repos/owner/repo/contents/docs" not in requested_paths
        assert "/repos/owner/repo/contents/docs/outreach" not in requested_paths
