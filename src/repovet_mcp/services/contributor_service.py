"""Contributor distribution and decentralization analytics service."""

from typing import Any


class ContributorService:
    """Analyzes contributor spread, commit shares, and bus-factor risk."""

    def analyze_contributors(self, contributors: list[dict[str, Any]]) -> dict[str, Any]:
        """Compute contributor diversity and commit distribution metrics."""
        total_contributors = len(contributors)
        if total_contributors == 0:
            return {
                "total_contributors": 0,
                "total_recorded_contributions": 0,
                "top_contributor_login": None,
                "top_contributor_contributions": 0,
                "top_contributor_share": 100.0,
                "top_3_contributors_share": 100.0,
                "bus_factor_risk": "HIGH",
                "is_decentralized": False,
            }

        contributions_list = [c.get("contributions", 0) for c in contributors]
        total_contributions = sum(contributions_list)
        if total_contributions == 0:
            total_contributions = 1

        top_contrib = contributors[0]
        top_contrib_count = top_contrib.get("contributions", 0)
        top_contributor_share = round((top_contrib_count / total_contributions) * 100, 2)

        top_3_sum = sum(c.get("contributions", 0) for c in contributors[:3])
        top_3_share = round((top_3_sum / total_contributions) * 100, 2)

        # Bus Factor Evaluation
        if total_contributors == 1 or top_contributor_share > 85.0:
            bus_factor_risk = "HIGH"
            is_decentralized = False
        elif total_contributors <= 3 or top_contributor_share > 55.0:
            bus_factor_risk = "MODERATE"
            is_decentralized = False
        else:
            bus_factor_risk = "LOW"
            is_decentralized = True

        return {
            "total_contributors": total_contributors,
            "total_recorded_contributions": total_contributions,
            "top_contributor_login": top_contrib.get("login"),
            "top_contributor_contributions": top_contrib_count,
            "top_contributor_share": top_contributor_share,
            "top_3_contributors_share": top_3_share,
            "bus_factor_risk": bus_factor_risk,
            "is_decentralized": is_decentralized,
        }
