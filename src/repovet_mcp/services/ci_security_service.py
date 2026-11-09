"""CI workflows, test architecture, and licensing safety analytics service."""

from typing import Any

OSI_APPROVED_SPDX = {
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "GPL-2.0",
    "GPL-3.0",
    "LGPL-2.1",
    "LGPL-3.0",
    "MPL-2.0",
    "ISC",
    "EPL-2.0",
    "AGPL-3.0",
    "0BSD",
    "Unlicense",
    "CC0-1.0",
}


class CISecurityService:
    """Analyzes CI/CD pipeline health, test structure, and license compliance."""

    def analyze_ci_and_security(
        self,
        repository_data: dict[str, Any],
        workflows: list[dict[str, Any]],
        workflow_runs: list[dict[str, Any]],
        root_contents: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Evaluate automated CI status, test directories, and OSI license status."""
        root_files = root_contents or []
        files_map = {f.get("name", "").lower(): f for f in root_files if isinstance(f, dict)}

        # 1. License Analysis
        license_meta = repository_data.get("license") or {}
        spdx_id = license_meta.get("spdx_id")
        is_osi_approved = spdx_id in OSI_APPROVED_SPDX if spdx_id else False

        # 2. Test Architecture Detection
        test_dir_names = {"tests", "test", "spec", "testing", "__tests__"}
        has_tests_dir = any(
            f.get("type") == "dir" and f.get("name", "").lower() in test_dir_names
            for f in root_files
        )

        # 3. CI Workflows & Runs Analysis
        has_workflows = len(workflows) > 0
        total_runs = len(workflow_runs)
        recent_runs = workflow_runs[:10]

        successful_runs = sum(1 for run in recent_runs if run.get("conclusion") == "success")
        failed_runs = sum(
            1 for run in recent_runs if run.get("conclusion") in ("failure", "timed_out")
        )

        default_branch = repository_data.get("default_branch", "main")
        default_branch_runs = [
            run for run in recent_runs if run.get("head_branch") == default_branch
        ]

        latest_default_run = default_branch_runs[0] if default_branch_runs else None
        latest_ci_conclusion = latest_default_run.get("conclusion") if latest_default_run else None

        ci_passing_on_default = latest_ci_conclusion == "success" if latest_default_run else None

        # 4. Safe Read-Only Root Directory Binary Check
        root_binary_detected = False
        detected_root_binaries: list[str] = []

        # Inspect root directory file names for precompiled binary extensions
        binary_extensions = {".exe", ".dll", ".so", ".bin", ".out"}
        for name in files_map:
            if any(name.endswith(ext) for ext in binary_extensions):
                root_binary_detected = True
                detected_root_binaries.append(
                    f"Precompiled binary detected in repository root: {name}"
                )

        return {
            "license_spdx": spdx_id,
            "license_name": license_meta.get("name"),
            "is_osi_approved": is_osi_approved,
            "has_tests_directory": has_tests_dir,
            "has_ci_workflows": has_workflows,
            "total_workflows_count": len(workflows),
            "recent_runs_evaluated": total_runs,
            "successful_runs_count": successful_runs,
            "failed_runs_count": failed_runs,
            "ci_passing_on_default_branch": ci_passing_on_default,
            "latest_default_branch_ci_conclusion": latest_ci_conclusion,
            "root_binary_detected": root_binary_detected,
            "detected_root_binaries": detected_root_binaries,
            "suspicious_install_scripts": root_binary_detected,  # Backward compatibility
            "suspicious_reasons": detected_root_binaries,
        }
