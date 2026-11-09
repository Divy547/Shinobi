"""Newcomer contribution accessibility and beginner issues analytics service."""

from typing import Any

from repovet_mcp.services.responsiveness_service import ResponsivenessService

BEGINNER_LABELS = {
    "good first issue",
    "good-first-issue",
    "beginner",
    "beginner-friendly",
    "easy",
    "help wanted",
    "help-wanted",
    "up-for-grabs",
    "first-timers-only",
    "gsoc",
    "gsoc-idea",
}


class NewcomerService:
    """Evaluates newcomer PR merge velocity and beginner issue accessibility."""

    def __init__(self) -> None:
        self._responsiveness_service = ResponsivenessService()

    def is_bot_user(self, user: dict[str, Any] | None) -> bool:
        """Determine whether a user is an automated bot."""
        return self._responsiveness_service.is_bot_user(user)

    def analyze_newcomers(
        self,
        issues: list[dict[str, Any]],
        pull_requests: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compute newcomer PR acceptance rate and beginner-friendly issue metrics."""
        # 1. Newcomer Pull Requests Analysis
        newcomer_prs_count = 0
        newcomer_prs_merged = 0
        newcomer_prs_closed = 0

        for pr in pull_requests:
            if self.is_bot_user(pr.get("user")):
                continue
            assoc = pr.get("author_association", "NONE")
            is_newcomer = assoc in ("FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "NONE")
            if is_newcomer:
                newcomer_prs_count += 1
                if pr.get("state") == "closed":
                    newcomer_prs_closed += 1
                    if pr.get("merged_at") is not None:
                        newcomer_prs_merged += 1

        newcomer_merge_rate = (
            round((newcomer_prs_merged / newcomer_prs_closed) * 100, 1)
            if newcomer_prs_closed > 0
            else 0.0
        )

        # 2. Beginner & Help Wanted Issues Analysis
        open_beginner_issues: list[dict[str, Any]] = []
        closed_beginner_issues_count = 0

        for issue in issues:
            labels = issue.get("labels", [])
            label_names = [lbl.get("name", "").lower() for lbl in labels if isinstance(lbl, dict)]
            has_beginner_label = any(
                bl in label_name for bl in BEGINNER_LABELS for label_name in label_names
            )

            if has_beginner_label:
                if issue.get("state") == "open":
                    open_beginner_issues.append(
                        {
                            "number": issue.get("number"),
                            "title": issue.get("title"),
                            "url": issue.get("html_url"),
                            "labels": label_names,
                            "created_at": issue.get("created_at"),
                        }
                    )
                else:
                    closed_beginner_issues_count += 1

        return {
            "total_prs_evaluated": len(pull_requests),
            "newcomer_prs_sample_count": newcomer_prs_count,
            "newcomer_prs_closed": newcomer_prs_closed,
            "newcomer_prs_merged": newcomer_prs_merged,
            "newcomer_merge_rate": newcomer_merge_rate,
            "open_beginner_issues_count": len(open_beginner_issues),
            "closed_beginner_issues_count": closed_beginner_issues_count,
            "open_beginner_issues": open_beginner_issues[:10],  # sample up to 10 for review
        }
