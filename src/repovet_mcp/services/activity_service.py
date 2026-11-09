"""Repository activity and maintenance pulse analytics service."""

from datetime import UTC, datetime
from typing import Any


class ActivityService:
    """Calculates commit cadence, recency, and release frequency."""

    @staticmethod
    def _parse_dt(dt_str: str | None) -> datetime | None:
        """Parse ISO datetime string into UTC datetime."""
        if not dt_str:
            return None
        try:
            # Handle standard ISO strings (e.g., "2026-10-14T11:22:00Z")
            clean_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(clean_str).astimezone(UTC)
        except Exception:
            return None

    def analyze_activity(
        self,
        repository_data: dict[str, Any],
        commits: list[dict[str, Any]],
        releases: list[dict[str, Any]],
        now: datetime | None = None,
        commits_collection_failed: bool = False,
    ) -> dict[str, Any]:
        """Compute commit recency, frequency across 30/90/365 days, and release cadence."""
        reference_time = now or datetime.now(UTC)
        is_archived = bool(repository_data.get("archived", False))

        # 1. Latest Commit Analysis
        commit_history_available = not commits_collection_failed
        latest_commit_date: datetime | None = None
        latest_commit_sha: str | None = None
        commit_dates: list[datetime] = []

        if commit_history_available:
            for commit in commits:
                commit_meta = commit.get("commit", {})
                committer_meta = commit_meta.get("committer", {}) or commit_meta.get("author", {})
                dt = self._parse_dt(committer_meta.get("date"))
                if dt:
                    commit_dates.append(dt)
                    if latest_commit_date is None or dt > latest_commit_date:
                        latest_commit_date = dt
                        latest_commit_sha = commit.get("sha")

            days_since_latest_commit: int | None = (
                (reference_time - latest_commit_date).days if latest_commit_date else 9999
            )
            is_dormant = days_since_latest_commit > 365 or is_archived
            is_abandoned = days_since_latest_commit > 548  # >18 months
        else:
            days_since_latest_commit = None
            is_dormant = is_archived
            is_abandoned = False

        # 2. Commit frequency buckets
        commits_last_30d = sum(1 for dt in commit_dates if (reference_time - dt).days <= 30)
        commits_last_90d = sum(1 for dt in commit_dates if (reference_time - dt).days <= 90)
        commits_last_365d = sum(1 for dt in commit_dates if (reference_time - dt).days <= 365)

        # 3. Releases Analysis
        total_releases = len(releases)
        latest_release_date: datetime | None = None
        latest_release_tag: str | None = None

        for rel in releases:
            published_at = self._parse_dt(rel.get("published_at") or rel.get("created_at"))
            if published_at and (latest_release_date is None or published_at > latest_release_date):
                latest_release_date = published_at
                latest_release_tag = rel.get("tag_name")

        days_since_latest_release = (
            (reference_time - latest_release_date).days if latest_release_date else None
        )

        return {
            "commit_history_available": commit_history_available,
            "is_archived": is_archived,
            "is_dormant": is_dormant,
            "is_abandoned": is_abandoned,
            "latest_commit_date": latest_commit_date.isoformat() if latest_commit_date else None,
            "latest_commit_sha": latest_commit_sha,
            "days_since_latest_commit": days_since_latest_commit,
            "commits_sample_size": len(commits),
            "commits_last_30d": commits_last_30d,
            "commits_last_90d": commits_last_90d,
            "commits_last_365d": commits_last_365d,
            "total_releases": total_releases,
            "latest_release_date": (
                latest_release_date.isoformat() if latest_release_date else None
            ),
            "latest_release_tag": latest_release_tag,
            "days_since_latest_release": days_since_latest_release,
        }
