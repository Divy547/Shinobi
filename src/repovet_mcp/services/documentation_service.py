"""Documentation and onboarding guidance analytics service."""

from typing import Any


class DocumentationService:
    """Analyzes presence and quality of core contributor documentation."""

    @staticmethod
    def _is_gsoc_doc_name(name: str) -> bool:
        low = name.lower()
        return (
            low.startswith("gsoc")
            or "summer-of-code" in low
            or "project-ideas" in low
            or low in ("ideas.md", "ideas.rst", "ideas.txt")
        )

    def analyze_documentation(
        self,
        root_contents: list[dict[str, Any]] | None,
        community_profile: dict[str, Any] | None,
        repository_data: dict[str, Any] | None = None,
        nested_contents: dict[str, list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        """Inspect README, CONTRIBUTING, Code of Conduct, templates, and targeted GSoC docs."""
        root_files = root_contents or []
        community = community_profile or {}
        files_map = {f.get("name", "").lower(): f for f in root_files if isinstance(f, dict)}
        nested = nested_contents or {}

        # Check README
        has_readme = any(name.startswith("readme") for name in files_map)
        readme_file = next((f for name, f in files_map.items() if name.startswith("readme")), None)
        readme_size = readme_file.get("size", 0) if readme_file else 0

        # Check CONTRIBUTING (root, community profile, or nested .github/docs)
        has_contributing = any("contributing" in name for name in files_map)
        if not has_contributing and "files" in community:
            has_contributing = community["files"].get("contributing") is not None
        if not has_contributing:
            for dir_key in (".github", "docs"):
                dir_items = nested.get(dir_key) or []
                if any(
                    "contributing" in item.get("name", "").lower()
                    for item in dir_items
                    if isinstance(item, dict)
                ):
                    has_contributing = True
                    break

        # Check CODE_OF_CONDUCT
        has_coc = any("code_of_conduct" in name or "conduct" in name for name in files_map)
        if not has_coc and "files" in community:
            has_coc = community["files"].get("code_of_conduct") is not None
        if not has_coc:
            dir_items = nested.get(".github") or []
            if any(
                "conduct" in item.get("name", "").lower()
                for item in dir_items
                if isinstance(item, dict)
            ):
                has_coc = True

        # Check SECURITY
        has_security = any("security" in name for name in files_map)
        if not has_security and "files" in community:
            has_security = community["files"].get("security") is not None
        if not has_security:
            dir_items = nested.get(".github") or []
            if any(
                "security" in item.get("name", "").lower()
                for item in dir_items
                if isinstance(item, dict)
            ):
                has_security = True

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
        if not has_pr_template or not has_issue_template:
            gh_items = nested.get(".github") or []
            for item in gh_items:
                if not isinstance(item, dict):
                    continue
                name_l = item.get("name", "").lower()
                if "pull_request_template" in name_l:
                    has_pr_template = True
                if "issue_template" in name_l:
                    has_issue_template = True

        # Check Community Chat / Discussions
        has_discussions = False
        if repository_data:
            has_discussions = bool(repository_data.get("has_discussions", False))

        # Check Dedicated GSoC / Project Ideas Documentation (Root first, then bounded nested paths)
        has_gsoc_doc = False
        gsoc_doc_path: str | None = None

        # 1. Root inspection
        for f in root_files:
            if not isinstance(f, dict):
                continue
            fname = f.get("name", "")
            if self._is_gsoc_doc_name(fname):
                has_gsoc_doc = True
                gsoc_doc_path = f.get("path") or fname
                break

        # 2. Bounded nested inspection: docs/outreach/, docs/, .github/
        if not has_gsoc_doc:
            for dir_path in ("docs/outreach", "docs", ".github"):
                items = nested.get(dir_path) or []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    fname = item.get("name", "")
                    if self._is_gsoc_doc_name(fname):
                        has_gsoc_doc = True
                        gsoc_doc_path = item.get("path") or f"{dir_path}/{fname}"
                        break
                if has_gsoc_doc:
                    break

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
            "gsoc_doc_path": gsoc_doc_path,
        }
