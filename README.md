# Shinobi (RepoVet MCP)

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Managed by: uv](https://img.shields.io/badge/managed%20by-uv-purple.svg)](https://github.com/astral-sh/uv)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![MCP Protocol 2.x](https://img.shields.io/badge/MCP-Protocol%202.x-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An autonomous, deterministic Model Context Protocol (MCP) server for open-source repository vetting and contributor due diligence.

---

## 1. Introduction

### What is Shinobi?

**Shinobi** (formerly RepoVet MCP) is a lightweight, standalone Model Context Protocol (MCP) server that empowers AI assistants to thoroughly vet open-source GitHub repositories. It evaluates project vitality, maintainer responsiveness, contributor onboarding health, and repository safety through deterministic analysis.

### Why Does It Exist?

Finding the right open-source repository to contribute to is daunting. First-time contributors and applicants to programs like **Google Summer of Code (GSoC 2027)** often spend days or weeks setting up projects, only to discover:
- Maintainers take months to review or merge pull requests.
- The default branch build is broken or tests are completely undocumented.
- The project is secretly abandoned or dominated by a single committer.
- Issue trackers are filled with bot noise and stale beginner issues.

Shinobi eliminates this guesswork by delivering an objective, reproducible audit in minutes.

### Who Should Use It?

- **GSoC & Internship Applicants**: Evaluate mentoring organizations and codebases before investing weeks drafting proposals.
- **First-Time OSS Contributors**: Discover active, welcoming repositories with high newcomer PR acceptance rates.
- **Engineering Teams**: Perform safety and maintenance due diligence before adopting or depending on open-source packages.

---

## 2. What Shinobi Does

Shinobi provides deterministic vetting across seven core capabilities:

1. **Repository Health & Vitality**: Analyzes commit cadence over the last 90 days, release frequency, and recency of maintenance.
2. **Maintainer Responsiveness**: Calculates median time for maintainers to provide the first human response to PRs and triage issues, strictly distinguishing human feedback from automated bot comments.
3. **Contributor Distribution**: Measures decentralization and bus-factor risk by evaluating contributor commit shares and top-committer dominance.
4. **Beginner Accessibility**: Evaluates newcomer PR merge rates, beginner issue availability (`good first issue` / `help wanted`), and onboarding documentation (README, CONTRIBUTING guide, Code of Conduct).
5. **GSoC & Mentorship Signals**: Inspects root and outreach directories (`docs/`, `docs/outreach/`, `.github/`) for official mentorship records and project ideas.
6. **CI & Repository Safety**: Confirms default branch CI builds are passing and verifies that no precompiled executable binaries (`.exe`, `.dll`, `.so`, `.bin`, `.out`) reside in the repository root.
7. **Deterministic Scoring & Executive PDF Reports**: Computes an objective 0–20 score (0–100%), evaluates four mandatory eligibility hard gates, validates citations against verified evidence, and compiles a publication-ready PDF audit report.

---

## 3. Getting Started

### Prerequisites

- **Python**: Version 3.12 or newer.
- **Git**: Installed and available in your `PATH`.
- **Package Manager**: [`uv`](https://github.com/astral-sh/uv) (recommended for fastest setup) or standard `pip`.

### Clone & Install

#### Option A: With `uv` (Recommended)

```bash
# Clone the repository
git clone https://github.com/Divy547/Shinobi.git
cd Shinobi

# Install dependencies and sync virtual environment
uv sync

# Verify Shinobi CLI entry point
uv run repovet-mcp --help
```

#### Option B: With Standard Python `venv` + `pip`

```bash
# Clone the repository
git clone https://github.com/Divy547/Shinobi.git
cd Shinobi

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package in editable mode
pip install -e .

# Verify CLI entry point
repovet-mcp --help
```

### Environment Configuration

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` to configure your settings:

```dotenv
# GitHub Personal Access Token (Raises rate limits from 60 to 5,000 req/hr)
REPOVET_GITHUB_TOKEN=ghp_your_personal_access_token_here

# Optional: Logging level (DEBUG, INFO, WARNING, ERROR)
REPOVET_LOG_LEVEL=INFO
```

### GitHub Token Setup

Shinobi inspects public repositories using the GitHub REST API.

- **Rate Limits**: Unauthenticated access is capped at 60 requests/hour. An authenticated token provides **5,000 requests/hour**.
- **Required Permissions**: Generate a standard Personal Access Token (classic or fine-grained) with **read-only access to public repositories**. Shinobi never requires write, admin, pull-request modification, or workflow permissions.
- **Security**: Never commit your token. Shinobi automatically masks secrets and tokens from all logs and error messages.

### Build the Official GitHub MCP Server

Shinobi operates alongside the official read-only [GitHub MCP Server](https://github.com/github/github-mcp-server) for contextual exploration.

Install the GitHub MCP server using Go:

```bash
go install github.com/github/github-mcp-server@latest
```

Or build directly from source:

```bash
git clone https://github.com/github/github-mcp-server.git
cd github-mcp-server
go build -o github-mcp-server .
```

---

## 4. Connect Shinobi to Your AI Client

Shinobi communicates via the standard MCP `stdio` transport. All diagnostic logs are sent to `stderr`, keeping `stdout` clean for JSON-RPC messages.

### A. Claude Code Configuration

Add Shinobi and GitHub MCP servers to your Claude Code project configuration (`.mcp.json`) or user configuration (`~/.claude.json`):

```json
{
  "mcpServers": {
    "shinobi": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/Shinobi",
        "run",
        "repovet-mcp"
      ],
      "env": {
        "REPOVET_GITHUB_TOKEN": "ghp_your_github_token_here",
        "REPOVET_LOG_LEVEL": "INFO"
      }
    },
    "github": {
      "command": "github-mcp-server",
      "args": [
        "--read-only",
        "--toolsets=repos,issues,pull_requests",
        "stdio"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_your_github_token_here"
      }
    }
  }
}
```

Or add Shinobi via the Claude Code CLI:

```bash
claude mcp add shinobi -- uv --directory /absolute/path/to/Shinobi run repovet-mcp
```

### B. Antigravity CLI / IDE Configuration

In Google Antigravity, add Shinobi and the GitHub MCP server to your global configuration (`~/.gemini/config/mcp_config.json`) or workspace configuration (`.gemini/mcp_config.json`):

```json
{
  "mcpServers": {
    "shinobi": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/Shinobi",
        "run",
        "repovet-mcp"
      ],
      "env": {
        "REPOVET_GITHUB_TOKEN": "ghp_your_github_token_here",
        "REPOVET_LOG_LEVEL": "INFO"
      }
    },
    "github": {
      "command": "github-mcp-server",
      "args": [
        "--read-only",
        "--toolsets=repos,issues,pull_requests",
        "stdio"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_your_github_token_here"
      }
    }
  }
}
```

---

## 5. How to Use Shinobi

### Example Prompt

Once connected to your AI client, prompt the assistant with a repository to audit:

> **Example Prompt:**
> "Analyze `kubeflow/pipelines` using Shinobi. Evaluate its suitability for a first-time contributor interested in GSoC 2027. Run the complete audit workflow, explain the score and hard gates, identify strengths and weaknesses, and generate a PDF report."

### How Your AI Client Uses Shinobi Tools

Shinobi exposes seven authoritative tools that the AI client executes during an audit:

| Tool | Purpose | What It Does |
| :--- | :--- | :--- |
| **`analyze_repository`** | Evidence Ingestion | Ingests raw repository metadata, commits, PRs, issues, and workflow runs into `data/<audit_id>/raw_data.json`. |
| **`check_hard_gates`** | Eligibility Screening | Tests the 4 mandatory gates: license validity, 365-day vitality, default-branch CI, and root binary check. |
| **`calculate_responsiveness`** | Maintainer Velocity | Computes median PR and issue human response times, automatically filtering out bots. |
| **`analyze_contribution_accessibility`** | Onboarding Health | Evaluates beginner issues, newcomer PR merge rates, and setup documentation. |
| **`calculate_scorecard`** | Core Scoring | Calculates the deterministic 10-criterion score (0–20), evaluates disqualifiers, and creates the SHA-256 integrity manifest. |
| **`validate_evidence`** | Fact Grounding | Verifies that every finding and scorecard assertion is backed by confirmed evidence items. |
| **`generate_pdf_report`** | Report Deliverable | Compiles an executive-grade, multi-page ReportLab PDF in `reports/generated/`. |

---

## 6. Understanding Your Results

### The 0–20 Scorecard Scale

Shinobi grades repositories across 10 deterministic criteria (each scored 0, 1, or 2 points):

| Score Range | Percentage | Verdict | Meaning |
| :---: | :---: | :---: | :--- |
| **16 – 20** | 80% – 100% | **`APPROVE`** | Excellent contributor candidate: fast reviews, active maintainers, passing CI, and clear documentation. |
| **10 – 15** | 50% – 75% | **`CONDITIONAL`** | Viable with caveats: maintainers are active, but newcomer PR turnaround, test setup, or GSoC documentation requires attention. |
| **0 – 9** | < 50% | **`FLAG` / `REJECT`** | High risk: unresponsive maintainers, low newcomer merge rates, or stale maintenance. |

### Hard-Gate Outcomes

Hard gates represent non-negotiable eligibility conditions:

- **`PASS`**: The criterion is satisfied (e.g., valid OSI license detected, commits exist in the last 365 days).
- **`FAIL`**: Immediate disqualifier or critical blocker (e.g., missing open-source license, broken default-branch CI).
- **`UNKNOWN`**: Data is unavailable or requires human inspection (e.g., unverified license type or missing CI logs).

### Evidence Taxonomy

Every claim in a Shinobi audit is tagged with an explicit confidence level:

- **`CONFIRMED`**: Directly verified via GitHub REST API data, exact file paths, or commit SHAs.
- **`INFERRED`**: Algorithmically derived from observable patterns (e.g., bot detection via login patterns).
- **`UNKNOWN`**: Data was unavailable or unobserved within the sample window. Never assumed or guessed.

### Audit Verdicts & Decisions

- **`CONDITIONAL`**: The repository passed all mandatory hard gates, but scored moderate points or has areas requiring contributor caution.
- **`NEEDS_MANUAL_REVIEW`**: One or more hard gates returned `UNKNOWN`, requiring contributor verification before committing effort.

### Where Output Files Are Stored

- **Primary Audit Data & Manifest**: Stored under `data/<audit_id>/`
  - `raw_data.json`: Raw GitHub API payloads.
  - `audit.json`: Complete audit data, scorecard, and hard-gate results.
  - `evidence.json`: All grounded evidence items and confidence levels.
  - `manifest.json`: SHA-256 integrity manifest for tamper detection.
- **Executive PDF Report**: Stored under `reports/generated/`
  - Filename format: `reports/generated/<audit_id>_<owner>_<repo>.pdf`

> [!NOTE]
> **Decision-Support Notice**: Shinobi provides objective decision support to help you allocate your contribution effort wisely. A high score indicates a healthy repository environment, but does not guarantee acceptance into mentorship programs or PR merges.

---

## 7. Real-World Validation

Shinobi has been tested and validated end-to-end against three production open-source codebases:

| Target Repository | Final Score | Verdict | Key Validations |
| :--- | :---: | :---: | :--- |
| **`kubeflow/pipelines`** | 10 / 20 (50.0%) | `CONDITIONAL` | Verified human comment responsiveness filtering, root binary check wording, tamper manifest verification, and accurate newcomer PR sample reporting (12 closed out of 15 evaluated in 100-PR window). |
| **`zulip/zulip`** | 14 / 20 (70.0%) | `CONDITIONAL` | Verified nested GSoC documentation discovery (`docs/outreach/`), bot classification (`zulipbot` filtered from human responsiveness), and decentralized contributor spread. |
| **`jupyterlab/jupyterlab`** | 12 / 20 (60.0%) | `CONDITIONAL` | Successfully validated dynamic default-branch (`main`) CI discovery across 25 workflow runs, explicit GitHub Actions conclusion mapping (`success` $\rightarrow$ PASS, `skipped` $\rightarrow$ UNKNOWN), and 5-page PDF structural generation. |

---

## 8. Limitations

Shinobi is designed for rapid, deterministic repository due diligence within sensible operational boundaries:

1. **Bounded API Sampling**: To respect GitHub REST API rate limits, collections sample recent windows (up to 100 commits, 100 PRs, 100 issues, and 25 workflow runs).
2. **Umbrella Foundation GSoC Discovery**: Shinobi inspects documentation within the repository (`docs/`, `docs/outreach/`, `.github/`). If a project participates in GSoC under an umbrella foundation (e.g. NumFOCUS, CNCF, Apache) without in-repo files, its status is reported as `UNKNOWN` pending manual archive checks.
3. **External CI Systems**: Only GitHub Actions workflows and runs are evaluated. Repositories using external CI services (CircleCI, Travis, AppVeyor, GitLab CI mirrors) without GitHub Actions check runs report CI status as `UNKNOWN`.
4. **Root-Only Binary Scanning**: Safe read-only safety checks inspect the repository root directory for precompiled binary extensions (`.exe`, `.dll`, `.so`, `.bin`, `.out`). Subdirectories and package build scripts are not scanned to preserve safe static analysis guarantees.

---

## 9. Project Status

**Shinobi (RepoVet MCP) is complete for its intended MVP scope.**

The project has achieved all architectural milestones, full unit and integration test coverage (108 automated tests), and real-world validation. It is ready for day-to-day use by contributors and teams evaluating open-source repositories. Shinobi is not under active feature development.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
