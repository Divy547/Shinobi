"""Asynchronous GitHub REST API client for repository data collection."""

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from repovet_mcp.services.security import (
    redact_secrets,
    validate_repo_component,
    validate_repository_url_domain,
)

logger = logging.getLogger("repovet_mcp.github")


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""


class RateLimitExceededError(GitHubAPIError):
    """Raised when GitHub API rate limit is exhausted."""


class RepositoryNotFoundError(GitHubAPIError):
    """Raised when the target repository does not exist or is private."""


def parse_repository_target(target: str) -> tuple[str, str]:
    """Extract and strictly validate owner and repo name from shorthand or GitHub URL.

    Examples:
        - "pallets/flask" -> ("pallets", "flask")
        - "https://github.com/pallets/flask" -> ("pallets", "flask")
        - "https://github.com/pallets/flask.git" -> ("pallets", "flask")
        - "git@github.com:pallets/flask.git" -> ("pallets", "flask")
    """
    clean_target = target.strip()
    if clean_target.startswith(("http://", "https://")):
        # Validate authorized domain to prevent SSRF
        validate_repository_url_domain(clean_target)
        parsed = urlparse(clean_target)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2:
            owner = validate_repo_component(parts[0], "owner")
            repo = validate_repo_component(parts[1].removesuffix(".git"), "repository")
            return owner, repo
    elif clean_target.startswith("git@github.com:"):
        path = clean_target.removeprefix("git@github.com:")
        parts = [p for p in path.strip("/").split("/") if p]
        if len(parts) >= 2:
            owner = validate_repo_component(parts[0], "owner")
            repo = validate_repo_component(parts[1].removesuffix(".git"), "repository")
            return owner, repo

    # Assume owner/repo shorthand
    match = re.match(r"^([\w\-\.]+)/([\w\-\.]+)$", clean_target)
    if match:
        owner = validate_repo_component(match.group(1), "owner")
        repo = validate_repo_component(match.group(2).removesuffix(".git"), "repository")
        return owner, repo

    msg = f"Unable to parse repository owner and name from target: '{clean_target}'"
    raise ValueError(msg)


class GitHubClient:
    """Asynchronous client for collecting repository vetting evidence from GitHub REST API."""

    def __init__(
        self,
        token: str | None = None,
        base_url: str = "https://api.github.com",
        timeout: float = 25.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "RepoVet-MCP/0.1.0 (Autonomous Open-Source Vetting)",
        }
        if self.token and self.token.strip():
            self.headers["Authorization"] = f"Bearer {self.token.strip()}"

    async def _request(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        params: dict[str, Any] | None = None,
        max_retries: int = 2,
    ) -> Any:
        """Execute HTTP request with rate limit inspection and retry logic."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        attempt = 0
        backoff = 1.0

        while attempt <= max_retries:
            attempt += 1
            try:
                response = await client.get(url, params=params, headers=self.headers)
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                if attempt > max_retries:
                    logger.warning("Request to %s failed after %d attempts: %s", url, attempt, exc)
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2
                continue

            remaining = response.headers.get("x-ratelimit-remaining")
            if response.status_code == 200:
                if remaining is not None and int(remaining) <= 0:
                    reset_time = response.headers.get("x-ratelimit-reset", "unknown")
                    logger.warning(
                        "GitHub API rate limit exhausted on successful response. Resets at: %s",
                        reset_time,
                    )
                return response.json()
            if response.status_code == 404:
                return None
            if response.status_code in (403, 429):
                err_body = response.text
                if (
                    "rate limit" in err_body.lower()
                    or remaining == "0"
                    or (remaining is not None and int(remaining) <= 0)
                ):
                    reset_time = response.headers.get("x-ratelimit-reset", "unknown")
                    msg = f"GitHub API rate limit reached (HTTP {response.status_code}). Resets at: {reset_time}"
                    raise RateLimitExceededError(msg)
                if attempt > max_retries:
                    msg = (
                        f"GitHub API permission or rate issue: {response.status_code} - {err_body}"
                    )
                    raise GitHubAPIError(msg)
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            if remaining is not None and int(remaining) <= 0:
                reset_time = response.headers.get("x-ratelimit-reset", "unknown")
                msg = f"GitHub API rate limit exhausted. Resets at: {reset_time}"
                logger.error(msg)
                raise RateLimitExceededError(redact_secrets(msg))
            if response.status_code >= 500:
                if attempt > max_retries:
                    msg = f"GitHub API server error: {response.status_code}"
                    raise GitHubAPIError(redact_secrets(msg))
                await asyncio.sleep(backoff)
                backoff *= 2
                continue

            # Other 4xx client errors (e.g. 400, 401, 422 - not retried)
            clean_err = redact_secrets(response.text)
            msg = f"GitHub API request failed: {response.status_code} - {clean_err}"
            raise GitHubAPIError(msg)

        return None

    async def get_repository(
        self, client: httpx.AsyncClient, owner: str, repo: str
    ) -> dict[str, Any]:
        """Fetch repository metadata."""
        data = await self._request(client, f"/repos/{owner}/{repo}")
        if data is None:
            msg = f"Repository {owner}/{repo} not found on GitHub."
            raise RepositoryNotFoundError(msg)
        return data

    async def get_commits(
        self, client: httpx.AsyncClient, owner: str, repo: str, per_page: int = 100
    ) -> list[dict[str, Any]]:
        """Fetch recent commit history."""
        data = await self._request(
            client, f"/repos/{owner}/{repo}/commits", params={"per_page": per_page}
        )
        return data if isinstance(data, list) else []

    async def get_contributors(
        self, client: httpx.AsyncClient, owner: str, repo: str, per_page: int = 100
    ) -> list[dict[str, Any]]:
        """Fetch contributor list."""
        data = await self._request(
            client, f"/repos/{owner}/{repo}/contributors", params={"per_page": per_page}
        )
        return data if isinstance(data, list) else []

    async def get_issues(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        state: str = "all",
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch issues (note: GitHub API includes PRs in this endpoint unless filtered)."""
        data = await self._request(
            client, f"/repos/{owner}/{repo}/issues", params={"state": state, "per_page": per_page}
        )
        return data if isinstance(data, list) else []

    async def get_issue_comments(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        issue_number: int,
        per_page: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch comments for a specific issue or pull request."""
        data = await self._request(
            client,
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            params={"per_page": per_page},
        )
        return data if isinstance(data, list) else []

    async def get_pull_requests(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        state: str = "all",
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch pull requests."""
        data = await self._request(
            client, f"/repos/{owner}/{repo}/pulls", params={"state": state, "per_page": per_page}
        )
        return data if isinstance(data, list) else []

    async def get_pull_reviews(
        self, client: httpx.AsyncClient, owner: str, repo: str, pull_number: int
    ) -> list[dict[str, Any]]:
        """Fetch reviews submitted on a pull request."""
        data = await self._request(client, f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews")
        return data if isinstance(data, list) else []

    async def get_releases(
        self, client: httpx.AsyncClient, owner: str, repo: str, per_page: int = 30
    ) -> list[dict[str, Any]]:
        """Fetch repository release records."""
        data = await self._request(
            client, f"/repos/{owner}/{repo}/releases", params={"per_page": per_page}
        )
        return data if isinstance(data, list) else []

    async def get_contents(
        self, client: httpx.AsyncClient, owner: str, repo: str, path: str = ""
    ) -> Any:
        """Fetch repository content list or specific file metadata."""
        return await self._request(client, f"/repos/{owner}/{repo}/contents/{path}")

    async def get_community_profile(
        self, client: httpx.AsyncClient, owner: str, repo: str
    ) -> dict[str, Any] | None:
        """Fetch community health profile (docs, code of conduct, license)."""
        data = await self._request(client, f"/repos/{owner}/{repo}/community/profile")
        return data if isinstance(data, dict) else None

    async def get_workflows(
        self, client: httpx.AsyncClient, owner: str, repo: str
    ) -> list[dict[str, Any]]:
        """Fetch registered GitHub Actions workflows."""
        data = await self._request(client, f"/repos/{owner}/{repo}/actions/workflows")
        if isinstance(data, dict) and "workflows" in data:
            return data["workflows"]
        return []

    async def get_workflow_runs(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        per_page: int = 25,
        branch: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch recent GitHub Actions workflow runs, optionally filtered by branch."""
        params: dict[str, Any] = {"per_page": per_page}
        if branch:
            params["branch"] = branch
        data = await self._request(client, f"/repos/{owner}/{repo}/actions/runs", params=params)
        if isinstance(data, dict) and "workflow_runs" in data:
            return data["workflow_runs"]
        return []

    async def collect_repository_data(
        self,
        owner: str,
        repo: str,
        sample_comments_limit: int = 15,
    ) -> dict[str, Any]:
        """Orchestrate comprehensive data collection for repository vetting."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # 1. Fetch Repository Metadata
            repo_meta = await self.get_repository(client, owner, repo)

            # 2. Concurrently fetch core collections
            gathered = await asyncio.gather(
                self.get_commits(client, owner, repo, per_page=100),
                self.get_contributors(client, owner, repo, per_page=100),
                self.get_issues(client, owner, repo, state="all", per_page=100),
                self.get_pull_requests(client, owner, repo, state="all", per_page=100),
                self.get_releases(client, owner, repo, per_page=30),
                self.get_contents(client, owner, repo, path=""),
                self.get_community_profile(client, owner, repo),
                self.get_workflows(client, owner, repo),
                self.get_workflow_runs(client, owner, repo, per_page=25),
                return_exceptions=True,
            )

            collection_errors: dict[str, str] = {}
            keys = [
                "commits",
                "contributors",
                "issues",
                "pull_requests",
                "releases",
                "root_contents",
                "community_profile",
                "workflows",
                "workflow_runs",
            ]
            clean_results: dict[str, Any] = {}
            for key, val in zip(keys, gathered, strict=True):
                if isinstance(val, Exception):
                    collection_errors[key] = str(val)
                    logger.warning("Error fetching %s for %s/%s: %s", key, owner, repo, val)
                    clean_results[key] = None
                else:
                    clean_results[key] = val

            commits = clean_results["commits"]
            contributors = clean_results["contributors"]
            all_issues = clean_results["issues"]
            pulls = clean_results["pull_requests"]
            releases = clean_results["releases"]
            root_contents = clean_results["root_contents"]
            community_profile = clean_results["community_profile"]
            workflows = clean_results["workflows"]
            workflow_runs = clean_results["workflow_runs"]

            # If workflows exist but none of the initial workflow runs belong to the default branch,
            # execute a single bounded query specifically targeting the repository's actual default branch.
            default_branch = (repo_meta or {}).get("default_branch") or "main"
            runs_list = workflow_runs if isinstance(workflow_runs, list) else []
            has_default_run = any(
                isinstance(r, dict) and r.get("head_branch") == default_branch for r in runs_list
            )
            if workflows and not has_default_run:
                try:
                    default_branch_runs = await self.get_workflow_runs(
                        client, owner, repo, per_page=10, branch=default_branch
                    )
                    if isinstance(default_branch_runs, list) and default_branch_runs:
                        if isinstance(workflow_runs, list):
                            workflow_runs.extend(default_branch_runs)
                        else:
                            workflow_runs = default_branch_runs
                except Exception as err:
                    logger.debug(
                        "Failed to fetch default branch (%s) workflow runs for %s/%s: %s",
                        default_branch,
                        owner,
                        repo,
                        err,
                    )

            # Separate true issues from pull requests in the issues list
            raw_issues_list = all_issues if isinstance(all_issues, list) else []
            true_issues = [issue for issue in raw_issues_list if "pull_request" not in issue]
            pull_requests = pulls if isinstance(pulls, list) else []

            # 3. Sample comments & reviews for recent PRs and issues for responsiveness calculations
            sampled_issue_comments: dict[int, list[dict[str, Any]]] = {}
            for issue in true_issues[:sample_comments_limit]:
                num = issue.get("number")
                if num and issue.get("comments", 0) > 0:
                    try:
                        comments_data = await self.get_issue_comments(client, owner, repo, num)
                        sampled_issue_comments[num] = comments_data
                    except Exception as err:
                        logger.debug("Failed to fetch comments for issue #%d: %s", num, err)

            sampled_pr_reviews: dict[int, list[dict[str, Any]]] = {}
            sampled_pr_comments: dict[int, list[dict[str, Any]]] = {}
            for pr in pull_requests[:sample_comments_limit]:
                num = pr.get("number")
                if num:
                    try:
                        reviews_data = await self.get_pull_reviews(client, owner, repo, num)
                        sampled_pr_reviews[num] = reviews_data
                    except Exception as err:
                        logger.debug("Failed to fetch reviews for PR #%d: %s", num, err)
                    try:
                        comments_data = await self.get_issue_comments(client, owner, repo, num)
                        sampled_pr_comments[num] = comments_data
                    except Exception as err:
                        logger.debug("Failed to fetch comments for PR #%d: %s", num, err)

            # 4. Bounded, targeted inspection of documentation directories for GSoC / onboarding guidance
            targeted_contents: dict[str, list[dict[str, Any]]] = {}
            candidate_paths = ["docs", "docs/outreach", ".github"]
            root_dir_names = {
                item.get("name")
                for item in (root_contents if isinstance(root_contents, list) else [])
                if isinstance(item, dict) and item.get("type") == "dir"
            }

            for t_path in candidate_paths:
                # Bounded optimization: skip if parent directory definitely does not exist
                if t_path == "docs" and root_dir_names and "docs" not in root_dir_names:
                    continue
                if t_path == "docs/outreach" and (
                    (root_dir_names and "docs" not in root_dir_names)
                    or (
                        "docs" in targeted_contents
                        and not any(
                            isinstance(item, dict)
                            and item.get("name") == "outreach"
                            and item.get("type") == "dir"
                            for item in targeted_contents["docs"]
                        )
                    )
                ):
                    continue
                if t_path == ".github" and root_dir_names and ".github" not in root_dir_names:
                    continue

                try:
                    contents_data = await self.get_contents(client, owner, repo, path=t_path)
                    if isinstance(contents_data, list):
                        targeted_contents[t_path] = contents_data
                except Exception as err:
                    logger.debug("Failed to fetch targeted contents for %s: %s", t_path, err)

            return {
                "repository": repo_meta,
                "commits": commits if isinstance(commits, list) else [],
                "contributors": contributors if isinstance(contributors, list) else [],
                "issues": true_issues,
                "pull_requests": pull_requests,
                "releases": releases if isinstance(releases, list) else [],
                "root_contents": root_contents if isinstance(root_contents, list) else [],
                "targeted_contents": targeted_contents,
                "community_profile": community_profile
                if isinstance(community_profile, dict)
                else {},
                "workflows": workflows if isinstance(workflows, list) else [],
                "workflow_runs": workflow_runs if isinstance(workflow_runs, list) else [],
                "sampled_issue_comments": sampled_issue_comments,
                "sampled_pr_reviews": sampled_pr_reviews,
                "sampled_pr_comments": sampled_pr_comments,
                "errors": collection_errors,
            }
