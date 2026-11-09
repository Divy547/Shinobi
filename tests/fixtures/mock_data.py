"""Realistic mock GitHub API payloads for deterministic testing."""

from datetime import UTC, datetime, timedelta
from typing import Any


def create_mock_repository_data(
    owner: str = "test-org",
    repo: str = "sample-lib",
    is_archived: bool = False,
    license_spdx: str = "Apache-2.0",
    days_since_latest_commit: int = 2,
    has_ci_failing: bool = False,
    has_gsoc_ideas: bool = True,
) -> dict[str, Any]:
    """Generate a fully populated synthetic raw_data dictionary for testing."""
    now = datetime.now(UTC)
    latest_commit_dt = now - timedelta(days=days_since_latest_commit)
    older_commit_dt = now - timedelta(days=20)
    oldest_commit_dt = now - timedelta(days=120)

    repo_meta = {
        "name": repo,
        "owner": {"login": owner},
        "html_url": f"https://github.com/{owner}/{repo}",
        "default_branch": "main",
        "description": "An exemplary open source library actively participating in GSoC 2027.",
        "stargazers_count": 1420,
        "forks_count": 310,
        "open_issues_count": 8,
        "archived": is_archived,
        "topics": ["gsoc", "python", "developer-tools", "testing"],
        "has_discussions": True,
        "license": {"spdx_id": license_spdx, "name": f"{license_spdx} License"},
    }

    commits = [
        {
            "sha": "a1b2c3d4e5f67890123456789abcdef012345678",
            "commit": {
                "author": {"name": "Alice Dev", "date": latest_commit_dt.isoformat()},
                "committer": {"name": "Alice Dev", "date": latest_commit_dt.isoformat()},
                "message": "feat: add robust caching support",
            },
        },
        {
            "sha": "b2c3d4e5f67890123456789abcdef0123456789",
            "commit": {
                "author": {"name": "Bob Contributor", "date": older_commit_dt.isoformat()},
                "committer": {"name": "Bob Contributor", "date": older_commit_dt.isoformat()},
                "message": "fix: resolve connection timeout issue",
            },
        },
        {
            "sha": "c3d4e5f67890123456789abcdef01234567890",
            "commit": {
                "author": {"name": "Carol Mentee", "date": oldest_commit_dt.isoformat()},
                "committer": {"name": "Carol Mentee", "date": oldest_commit_dt.isoformat()},
                "message": "docs: update onboarding guide",
            },
        },
    ]

    contributors = [
        {"login": "alice", "contributions": 45},
        {"login": "bob", "contributions": 30},
        {"login": "carol", "contributions": 25},
        {"login": "david", "contributions": 15},
        {"login": "eve", "contributions": 10},
    ]

    pr_created = now - timedelta(days=10)
    pr_review_submitted = pr_created + timedelta(hours=18)
    pr_merged = pr_created + timedelta(days=2)

    pull_requests = [
        {
            "number": 101,
            "title": "fix: correct argument parser in CLI",
            "state": "closed",
            "created_at": pr_created.isoformat(),
            "updated_at": pr_merged.isoformat(),
            "closed_at": pr_merged.isoformat(),
            "merged_at": pr_merged.isoformat(),
            "user": {"login": "newcomer_dev", "type": "User"},
            "author_association": "FIRST_TIME_CONTRIBUTOR",
            "comments": 2,
        },
        {
            "number": 102,
            "title": "feat: enhance test suite",
            "state": "open",
            "created_at": (now - timedelta(days=4)).isoformat(),
            "updated_at": (now - timedelta(days=1)).isoformat(),
            "closed_at": None,
            "merged_at": None,
            "user": {"login": "eve", "type": "User"},
            "author_association": "CONTRIBUTOR",
            "comments": 1,
        },
    ]

    sampled_pr_reviews = {
        101: [
            {
                "user": {"login": "alice", "type": "User"},
                "submitted_at": pr_review_submitted.isoformat(),
                "state": "APPROVED",
            }
        ]
    }

    sampled_pr_comments = {
        101: [
            {
                "user": {"login": "dependabot[bot]", "type": "Bot"},
                "created_at": (pr_created + timedelta(minutes=5)).isoformat(),
                "body": "Automated dependency analysis completed.",
            },
            {
                "user": {"login": "bob", "type": "User"},
                "created_at": (pr_created + timedelta(hours=12)).isoformat(),
                "body": "Nice patch! Please address the small formatting point.",
            },
        ]
    }

    issue_created = now - timedelta(days=8)
    issues = [
        {
            "number": 201,
            "title": "Add support for Python 3.13",
            "state": "open",
            "created_at": issue_created.isoformat(),
            "updated_at": (now - timedelta(days=1)).isoformat(),
            "html_url": f"https://github.com/{owner}/{repo}/issues/201",
            "user": {"login": "student_user", "type": "User"},
            "comments": 1,
            "labels": [{"name": "good first issue"}, {"name": "help wanted"}],
        },
        {
            "number": 202,
            "title": "Documentation typo in setup section",
            "state": "open",
            "created_at": (now - timedelta(days=5)).isoformat(),
            "updated_at": (now - timedelta(days=2)).isoformat(),
            "html_url": f"https://github.com/{owner}/{repo}/issues/202",
            "user": {"login": "another_user", "type": "User"},
            "comments": 1,
            "labels": [{"name": "beginner-friendly"}, {"name": "documentation"}],
        },
        {
            "number": 203,
            "title": "Implement async database connector",
            "state": "open",
            "created_at": (now - timedelta(days=12)).isoformat(),
            "updated_at": (now - timedelta(days=3)).isoformat(),
            "html_url": f"https://github.com/{owner}/{repo}/issues/203",
            "user": {"login": "mentor_alice", "type": "User"},
            "comments": 2,
            "labels": [{"name": "gsoc"}, {"name": "help wanted"}],
        },
    ]

    sampled_issue_comments = {
        201: [
            {
                "user": {"login": "alice", "type": "User"},
                "created_at": (issue_created + timedelta(hours=24)).isoformat(),
                "body": "We would love a PR for this! Check out CONTRIBUTING.md.",
            }
        ]
    }

    releases = [
        {
            "tag_name": "v1.2.0",
            "published_at": (now - timedelta(days=25)).isoformat(),
            "name": "Release 1.2.0",
        },
        {
            "tag_name": "v1.1.0",
            "published_at": (now - timedelta(days=110)).isoformat(),
            "name": "Release 1.1.0",
        },
    ]

    root_contents = [
        {"name": "README.md", "type": "file", "size": 3400},
        {"name": "CONTRIBUTING.md", "type": "file", "size": 2200},
        {"name": "CODE_OF_CONDUCT.md", "type": "file", "size": 1500},
        {"name": "SECURITY.md", "type": "file", "size": 1100},
        {"name": "LICENSE", "type": "file", "size": 11350},
        {"name": "pyproject.toml", "type": "file", "size": 800},
        {"name": "tests", "type": "dir", "size": 0},
    ]
    if has_gsoc_ideas:
        root_contents.append({"name": "GSOC.md", "type": "file", "size": 1800})

    community_profile = {
        "health_percentage": 100,
        "files": {
            "contributing": {"url": "https://github.com/.../CONTRIBUTING.md"},
            "code_of_conduct": {"url": "https://github.com/.../CODE_OF_CONDUCT.md"},
            "security": {"url": "https://github.com/.../SECURITY.md"},
            "pull_request_template": {"url": "https://github.com/.../PULL_REQUEST_TEMPLATE"},
            "issue_template": {"url": "https://github.com/.../ISSUE_TEMPLATE"},
        },
    }

    workflows = [
        {"id": 1, "name": "CI Tests", "path": ".github/workflows/ci.yml", "state": "active"}
    ]

    run_conclusion = "failure" if has_ci_failing else "success"
    workflow_runs = [
        {
            "id": 501,
            "name": "CI Tests",
            "head_branch": "main",
            "conclusion": run_conclusion,
            "status": "completed",
            "created_at": (now - timedelta(hours=6)).isoformat(),
        }
    ]

    return {
        "repository": repo_meta,
        "commits": commits,
        "contributors": contributors,
        "issues": issues,
        "pull_requests": pull_requests,
        "releases": releases,
        "root_contents": root_contents,
        "community_profile": community_profile,
        "workflows": workflows,
        "workflow_runs": workflow_runs,
        "sampled_issue_comments": sampled_issue_comments,
        "sampled_pr_reviews": sampled_pr_reviews,
        "sampled_pr_comments": sampled_pr_comments,
        "targeted_contents": {},
    }
