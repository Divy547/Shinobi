"""Documentation and onboarding guidance analytics service."""

from typing import Any


class DocumentationService:
    """Analyzes presence and quality of core contributor documentation."""

    def analyze_documentation(
        self,
        root_contents: list[dict[str, Any]] | None,
        community_profile: dict[str, Any] | None,
        repository_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Inspect README, CONTRIBUTING, Code of Conduct, and templates."""
        root_files = root_contents or []
        community = community_profile or {}
        files_map = {f.get("name", "").lower(): f for f in root_files if isinstance(f, dict)}

        # Check README
        has_readme = any(name.startswith("readme") for name in files_map)
        readme_file = next((f for name, f in files_map.items() if name.startswith("readme")), None)
        readme_size = readme_file.get("size", 0) if readme_file else 0

        # Check CONTRIBUTING
        has_contributing = any("contributing" in name for name in files_map)
        if not has_contributing and "files" in community:
            has_contributing = community["files"].get("contributing") is not None

        # Check CODE_OF_CONDUCT
        has_coc = any("code_of_conduct" in name or "conduct" in name for name in files_map)
        if not has_coc and "files" in community:
            has_coc = community["files"].get("code_of_conduct") is not None

        # Check SECURITY
        has_security = any("security" in name for name in files_map)
        if not has_security and "files" in community:
            has_security = community["files"].get("security") is not None

        # Check LICENSE
        has_license = any(
            name.startswith("license") or name.startswith("copying") for name in files_map
        )
        if not has_license and repository_data:
            has_license = bool(repository_data.get("license"))

        # Check Templates
        has_pr_template = False
        has_issue_template = False
        if "files" in community:
            has_pr_template = community["files"].get("pull_request_template") is not None
            has_issue_template = community["files"].get("issue_template") is not None

        # Check Community Chat / Discussions
        has_discussions = False
        if repository_data:
            has_discussions = bool(repository_data.get("has_discussions", False))

        # Check Dedicated GSoC / Project Ideas Documentation
        has_gsoc_doc = any(
            name.startswith("gsoc")
            or "summer-of-code" in name
            or "project-ideas" in name
            or name in ("ideas.md", "ideas.rst", "ideas.txt")
            for name in files_map
        )

        return {
            "has_readme": has_readme,
            "readme_size_bytes": readme_size,
            "has_contributing": has_contributing,
            "has_code_of_conduct": has_coc,
            "has_security_policy": has_security,
            "has_license_file": has_license,
            "has_pr_template": has_pr_template,
            "has_issue_template": has_issue_template,
            "has_discussions_enabled": has_discussions,
            "has_gsoc_doc": has_gsoc_doc,
        }
