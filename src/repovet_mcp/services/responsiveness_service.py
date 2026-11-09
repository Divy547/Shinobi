"""Responsiveness and velocity analytics service distinguishing human from bot interactions."""

from datetime import UTC, datetime
from statistics import median
from typing import Any

KNOWN_BOT_LOGINS = {
    "github-actions",
    "dependabot",
    "codecov",
    "stale",
    "renovate",
    "semantic-release",
    "mergify",
    "greenkeeper",
    "sonarcloud",
    "lgtm-com",
    "vercel",
    "snyk-bot",
    "probot",
    "web-flow",
    "zulipbot",
    "k8s-ci-robot",
    "google-cla",
    "cla-assistant",
    "boring-cyborg",
}


class ResponsivenessService:
    """Calculates PR turnaround, human response times, and issue triage velocity."""

    @staticmethod
    def _parse_dt(dt_str: str | None) -> datetime | None:
        if not dt_str:
            return None
        try:
            clean_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(clean_str).astimezone(UTC)
        except Exception:
            return None

    def is_bot_user(self, user: dict[str, Any] | None) -> bool:
        """Determine whether a GitHub user profile represents an automated bot."""
        if not user or not isinstance(user, dict):
            return False

        if user.get("type") == "Bot":
            return True

        login = user.get("login", "").lower()
        if not login:
            return False

        if (
            login.endswith("[bot]")
            or login.endswith("-bot")
            or login.endswith("_bot")
            or login.endswith("-robot")
        ):
            return True

        return login in KNOWN_BOT_LOGINS

    def analyze_responsiveness(
        self,
        issues: list[dict[str, Any]],
        pull_requests: list[dict[str, Any]],
        sampled_issue_comments: dict[int, list[dict[str, Any]]],
        sampled_pr_reviews: dict[int, list[dict[str, Any]]],
        sampled_pr_comments: dict[int, list[dict[str, Any]]],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Compute human review turnaround, median response times, and unanswered rates."""
        reference_time = now or datetime.now(UTC)

        total_human_comments = 0
        total_bot_comments = 0

        # ---------------------------------------------------------
        # 1. Pull Request Responsiveness Analysis
        # ---------------------------------------------------------
        pr_response_hours_list: list[float] = []
        pr_merge_hours_list: list[float] = []
        closed_prs = 0
        merged_prs = 0
        stale_prs_count = 0

        for pr in pull_requests:
            pr_num = pr.get("number")
            pr_created = self._parse_dt(pr.get("created_at"))
            pr_updated = self._parse_dt(pr.get("updated_at"))
            pr_merged = self._parse_dt(pr.get("merged_at"))
            pr_state = pr.get("state", "open")
            pr_author = (pr.get("user") or {}).get("login", "").lower()

            if pr_state == "closed":
                closed_prs += 1
                if pr_merged:
                    merged_prs += 1
                    if pr_created:
                        merge_hours = (pr_merged - pr_created).total_seconds() / 3600.0
                        if merge_hours >= 0:
                            pr_merge_hours_list.append(merge_hours)
            elif pr_state == "open" and pr_updated and (reference_time - pr_updated).days > 60:
                stale_prs_count += 1

            # Sample comments & reviews for first human response
            if pr_num and pr_created:
                earliest_human_response: datetime | None = None

                # Inspect PR Reviews
                reviews = (
                    sampled_pr_reviews.get(pr_num) or sampled_pr_reviews.get(str(pr_num)) or []
                )
                for rev in reviews:
                    rev_user = rev.get("user")
                    if self.is_bot_user(rev_user):
                        total_bot_comments += 1
                        continue
                    rev_author = (rev_user or {}).get("login", "").lower()
                    if rev_author and rev_author != pr_author:
                        total_human_comments += 1
                        rev_time = self._parse_dt(rev.get("submitted_at") or rev.get("created_at"))
                        if rev_time and (
                            earliest_human_response is None or rev_time < earliest_human_response
                        ):
                            earliest_human_response = rev_time

                # Inspect PR Comments
                comments = (
                    sampled_pr_comments.get(pr_num) or sampled_pr_comments.get(str(pr_num)) or []
                )
                for comment in comments:
                    c_user = comment.get("user")
                    if self.is_bot_user(c_user):
                        total_bot_comments += 1
                        continue
                    c_author = (c_user or {}).get("login", "").lower()
                    if c_author and c_author != pr_author:
                        total_human_comments += 1
                        c_time = self._parse_dt(comment.get("created_at"))
                        if c_time and (
                            earliest_human_response is None or c_time < earliest_human_response
                        ):
                            earliest_human_response = c_time

                if earliest_human_response:
                    delta_hours = (earliest_human_response - pr_created).total_seconds() / 3600.0
                    pr_response_hours_list.append(max(0.0, delta_hours))

        # ---------------------------------------------------------
        # 2. Issue Responsiveness Analysis
        # ---------------------------------------------------------
        issue_response_hours_list: list[float] = []
        open_issues_count = 0
        unanswered_open_issues_count = 0
        stale_issues_count = 0

        for issue in issues:
            issue_num = issue.get("number")
            issue_created = self._parse_dt(issue.get("created_at"))
            issue_updated = self._parse_dt(issue.get("updated_at"))
            issue_state = issue.get("state", "open")
            issue_author = (issue.get("user") or {}).get("login", "").lower()

            if issue_state == "open":
                open_issues_count += 1
                if issue_updated and (reference_time - issue_updated).days > 60:
                    stale_issues_count += 1

            if issue_num and issue_created:
                earliest_human_comment: datetime | None = None
                comments = (
                    sampled_issue_comments.get(issue_num)
                    or sampled_issue_comments.get(str(issue_num))
                    or []
                )

                for comment in comments:
                    c_user = comment.get("user")
                    if self.is_bot_user(c_user):
                        total_bot_comments += 1
                        continue
                    c_author = (c_user or {}).get("login", "").lower()
                    if c_author and c_author != issue_author:
                        total_human_comments += 1
                        c_time = self._parse_dt(comment.get("created_at"))
                        if c_time and (
                            earliest_human_comment is None or c_time < earliest_human_comment
                        ):
                            earliest_human_comment = c_time

                if earliest_human_comment:
                    delta_hours = (earliest_human_comment - issue_created).total_seconds() / 3600.0
                    issue_response_hours_list.append(max(0.0, delta_hours))
                elif issue_state == "open" and (reference_time - issue_created).days > 7:
                    # Flag open issue with no human reply after 7 days as unanswered
                    unanswered_open_issues_count += 1

        # Calculate medians and rates
        median_pr_first_response = (
            round(median(pr_response_hours_list), 1) if pr_response_hours_list else None
        )
        median_pr_merge_time = (
            round(median(pr_merge_hours_list), 1) if pr_merge_hours_list else None
        )
        pr_merge_rate = round((merged_prs / closed_prs) * 100, 1) if closed_prs > 0 else 0.0

        median_issue_first_response = (
            round(median(issue_response_hours_list), 1) if issue_response_hours_list else None
        )
        unanswered_issue_pct = (
            round((unanswered_open_issues_count / max(1, open_issues_count)) * 100, 1)
            if open_issues_count > 0
            else 0.0
        )

        return {
            "median_pr_first_response_hours": median_pr_first_response,
            "median_pr_merge_hours": median_pr_merge_time,
            "pr_merge_rate": pr_merge_rate,
            "total_prs_evaluated": len(pull_requests),
            "prs_with_human_response_count": len(pr_response_hours_list),
            "stale_prs_count": stale_prs_count,
            "median_issue_first_response_hours": median_issue_first_response,
            "unanswered_issue_percentage": unanswered_issue_pct,
            "open_issues_evaluated": open_issues_count,
            "stale_issues_count": stale_issues_count,
            "human_comments_count": total_human_comments,
            "bot_comments_count": total_bot_comments,
        }
