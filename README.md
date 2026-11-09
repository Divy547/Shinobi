# Shinobi (RepoVet MCP)

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/managed%20by-uv-purple.svg)](https://github.com/astral-sh/uv)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![MCP](https://img.shields.io/badge/MCP-Protocol%202.x-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Shinobi** (formerly RepoVet MCP) is a lightweight, hardened, standalone Python Model Context Protocol (MCP) server for autonomous open-source repository vetting. It is engineered specifically for prospective open-source contributors (such as **Google Summer of Code / GSoC 2027** applicants) and software engineering teams conducting due diligence before adopting or contributing to third-party open-source codebases.

Shinobi runs over the standard MCP stdio transport, exposing seven deterministic vetting tools that investigate target repositories across **Nine Vetting Phases**, evaluate mandatory **Eligibility Hard Gates**, calculate a grounded **10-Criterion Scorecard (0–20 Scale)**, and compile executive-ready, publication-grade **PDF Audit Reports**.

---

## Key Highlights

- **100% Deterministic & Work-Ready**: Scoring algorithms, triage velocities, and decision boundaries are computed entirely in Python without relying on external LLM synthesis or non-deterministic heuristics.
- **Strict Untrusted Code Policy**: Audited codebases are treated as untrusted user input. Shinobi **never** executes external build scripts, shell commands, test runners, or install hooks. Repositories are inspected solely through safe read-only GitHub REST APIs and static AST analysis.
- **SSRF & Path Traversal Immunity**: URL parsing strictly whitelists authorized GitHub domains (`github.com`, `www.github.com`). Storage paths and audit IDs are strictly validated (`^[a-zA-Z0-9_\-]{1,128}$`) and resolved safely within base directories.
- **Credential & Secret Redaction**: All error logs, exception messages, and protocol payloads automatically mask GitHub personal access tokens (`ghp_`, `github_pat_`), Bearer authorization headers, and API keys.
- **Atomic Writes & Artifact Integrity Manifests**: Audit data, raw payloads, and scorecards are written atomically via temporary files and `os.replace`. A SHA-256 manifest in `data/<audit_id>/manifest.json` provides tamper detection for stored audit contracts (`raw_data.json`, `audit.json`, `evidence.json`). Note: compiled PDF reports in `reports/generated/` are stored outside this manifest.
- **Publication-Quality PDF Reports**: Multi-page PDF reports generated with ReportLab feature dynamic page headers/footers, XML-sanitized text cells, multi-page table pagination (`repeatRows=1`), and automated structural validation.

---

## Architecture & Directory Layout

```text
repovet-mcp/
├── pyproject.toml              # Packaging metadata, entry points & tool configuration
├── uv.lock                     # Deterministic dependency lockfile
├── README.md                   # Operational and architectural guide
├── GEMINI.md                   # Permanent AI agent guidelines & safety rules
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules
│
├── config/                     # Declarative YAML configurations
│   ├── scoring.yaml            # 10 scorecard criteria definitions & 0-2 rubrics
│   └── thresholds.yaml         # Decision thresholds & disqualifier rules
│
├── src/
│   └── repovet_mcp/
│       ├── __init__.py         # Package root with version metadata
│       ├── server.py           # MCP server initialization & CLI entry point
│       │
│       ├── config/             # Typed settings & YAML loaders
│       │   ├── __init__.py
│       │   └── settings.py     # Pydantic Settings with startup validation
│       │
│       ├── models/             # Pydantic structured data contracts
│       │   ├── __init__.py
│       │   ├── audit.py        # AuditReport, Scorecard, CriterionScore, HardGateResult
│       │   ├── evidence.py     # EvidenceItem, EvidenceConfidence, EvidenceSourceType
│       │   └── findings.py     # AuditFinding, FindingSeverity, FindingCategory
│       │
│       ├── services/           # Core business logic & analytics engines
│       │   ├── __init__.py
│       │   ├── activity_service.py         # Commit pulse, releases, activity recency
│       │   ├── ci_security_service.py      # Workflow status, licenses, install safety
│       │   ├── contributor_service.py     # Committer distribution & bus factor
│       │   ├── documentation_service.py   # README, CONTRIBUTING, setup guides
│       │   ├── evidence_validator.py      # Evidence citation and grounding checks
│       │   ├── github_client.py           # Asynchronous GitHub client with rate limits
│       │   ├── hard_gates_service.py      # Mandatory eligibility gate evaluation
│       │   ├── newcomer_service.py        # Beginner issues & newcomer PR velocity
│       │   ├── responsiveness_service.py  # First human response times (bot-filtered)
│       │   ├── scoring_engine.py          # Deterministic 10-criterion scoring
│       │   ├── security.py                # Redaction, sanitization, SSRF/traversal checks
│       │   └── storage_service.py         # Atomic JSON persistence & checksums
│       │
│       ├── tools/              # MCP tool definitions exposed over stdio
│       │   ├── __init__.py
│       │   └── vetting_tools.py # 7 registered MCP tool handlers with rich schemas
│       │
│       └── reporting/          # PDF generation & validation
│           ├── __init__.py
│           ├── pdf_generator.py # ReportLab PDF audit report compiler
│           └── pdf_validator.py # Low-level PDF structural validator
│
├── tests/                      # Automated test suite (77 unit & integration tests)
│   ├── conftest.py             # Pytest fixtures & mock environments
│   ├── fixtures/               # Mock payloads & sample repository data
│   ├── integration/            # Stdio protocol & workflow integration tests
│   │   ├── test_client_workflow.py # End-to-end 7-tool client workflow
│   │   ├── test_mcp_protocol.py    # Stdio protocol lifecycle & cwd independence
│   │   ├── test_server_init.py     # Server startup & settings validation
│   │   └── test_vetting_tools.py   # Tool handler unit integration
│   └── unit/                   # Isolated component & service tests
│       ├── test_analytics_services.py
│       ├── test_config.py
│       ├── test_evidence_validator.py
│       ├── test_github_client.py
│       ├── test_github_client_hardening.py
│       ├── test_imports.py
│       ├── test_pdf_generator.py
│       ├── test_pdf_hardening.py
│       ├── test_scoring_engine.py
│       ├── test_security.py
│       ├── test_storage_service.py
│       └── test_tool_definitions.py
│
├── knowledge/                  # Methodology & policy references
│   ├── vetting-methodology.md  # 9-phase methodology & 10-criterion rubric
│   └── evidence-policy.md      # Ground truth, untrusted content & safety rules
│
├── data/                       # Cached audit payloads & raw JSON manifests
└── reports/                    # Output directory for generated PDF audits
```

---

## Standalone MCP Server Execution

### 1. Installation

Prerequisites: Python 3.12+.

#### Installing `uv` (Recommended)

`uv` is an extremely fast Python package manager from Astral. Install it via one of the following methods:

```bash
# Standalone installer (macOS / Linux):
curl -LsSf https://astral.sh/uv/install.sh | sh

# Standalone installer (Windows PowerShell):
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip (any platform with Python):
pip install uv

# Or via Homebrew (macOS / Linux):
brew install uv
```

#### Option A: Quickstart with `uv` (Recommended)

```bash
# Clone the repository
git clone https://github.com/Divy547/Shinobi.git
cd Shinobi

# Create virtualenv and synchronize all runtime and development dependencies
uv sync --extra dev

# Run tools and entry points directly via uv
uv run repovet-mcp --help
```

#### Option B: Standard Python `venv` + `pip` Fallback

If you do not have `uv` installed, you can use the standard Python virtual environment workflow:

```bash
# Clone the repository
git clone https://github.com/Divy547/Shinobi.git
cd Shinobi

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package and development dependencies in editable mode
pip install -e ".[dev]"

# Verify the installed CLI entry point
repovet-mcp --help
```

### 2. Verifying the Installed MCP Entry Point

After installation, verify that the `repovet-mcp` entry point starts correctly and responds to MCP protocol frames over `stdio`:

#### A. Basic CLI Startup Check

```bash
# Using active venv:
repovet-mcp --help

# Or using explicit venv path:
.venv/bin/repovet-mcp --help

# Or via uv:
uv run repovet-mcp --help
```

#### B. Protocol-Level JSON-RPC Handshake Verification

You can test the stdio transport protocol initialization directly from the command line:

```bash
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}' | .venv/bin/repovet-mcp
```

Expected output on `stdout`:
```json
{"jsonrpc":"2.0","id":1,"result":{"capabilities":{"prompts":{"listChanged":false},"resources":{"listChanged":false,"subscribe":false},"tools":{"listChanged":false}},"instructions":"RepoVet MCP: Autonomous open-source repository vetting server. Exposes tools to investigate repositories across nine phases, calculate 10-criterion scorecards, validate evidence, and generate audit reports.","protocolVersion":"2024-11-05","serverInfo":{"name":"repovet-mcp","version":"0.1.0"}}}
```

All operational logging is routed strictly to `stderr`, keeping `stdout` completely clean for JSON-RPC messages.

### 3. Environment Setup

Create your `.env` file from the example template:

```bash
cp .env.example .env
```

Configuration parameters:

| Variable | Default | Purpose |
|:---|:---|:---|
| `REPOVET_GITHUB_TOKEN` | *(None)* | GitHub Personal Access Token for Shinobi's internal REST client. Strongly recommended: raises rate limits from 60 to 5,000 req/hr. |
| `REPOVET_GITHUB_API_URL` | `https://api.github.com` | Base URL for GitHub REST API calls. |
| `REPOVET_LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Diagnostics are routed exclusively to `stderr`. |
| `REPOVET_SCORING_CONFIG_PATH` | `config/scoring.yaml` | Path to declarative scoring definitions and criteria rubrics. |
| `REPOVET_THRESHOLDS_CONFIG_PATH` | `config/thresholds.yaml` | Path to verdict thresholds and hard-gate disqualifiers. |
| `REPOVET_DATA_DIR` | `data` | Directory for raw API snapshots and audit JSON files. |
| `REPOVET_REPORTS_DIR` | `reports` | Directory where PDF reports are compiled (`reports/generated/`). |
| `REPOVET_LOGS_DIR` | `logs` | Directory for server log outputs. |

> [!NOTE]
> **Cost Statement & Authentication**: Shinobi requires no separately billed LLM API keys or API usage. AI orchestration uses the user's independently authenticated AI client (such as Claude Code or Antigravity CLI) and existing subscription, subject to provider usage limits and terms. Shinobi operates purely as a deterministic MCP tool server.

### 4. Running via stdio Transport

The server communicates via standard JSON-RPC over `stdio`. All operational and error diagnostics are sent to `stderr` to keep `stdout` pristine for MCP protocol frames:

```bash
# Direct execution via uv
uv run repovet-mcp

# Or via python module
uv run python -m repovet_mcp.server
```

### 5. Claude Desktop Configuration

To connect Shinobi to the Claude Desktop application, add the server to your `claude_desktop_config.json`:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

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
        "REPOVET_GITHUB_TOKEN": "ghp_your_personal_access_token_here",
        "REPOVET_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

---

## Registered MCP Tools

Shinobi exposes seven specialized MCP tools covering the entire vetting lifecycle:

### 1. `analyze_repository`
Initializes an audit record and collects raw data from GitHub (repository metadata, commits, pull requests, issues, root files, and GitHub Actions workflows).
- **Arguments**:
  - `target` *(string, required)*: Repository target in shorthand (`owner/repo`) or HTTPS URL (`https://github.com/owner/repo`).
  - `audit_id` *(string, optional)*: Custom audit identifier (format: `^[a-zA-Z0-9_\-]{1,128}$`). If omitted, an ID is generated automatically.
- **Returns**: Repository metadata, default branch, stars, forks, license SPDX, and the assigned `audit_id`.

### 2. `check_hard_gates`
Evaluates mandatory eligibility gates that instantly disqualify a repository or require human review.
- **Arguments**:
  - `audit_id` *(string, required)*: Identifier of the initialized audit.
- **Evaluated Hard Gates**:
  1. *License Validity*: Ensures an OSI-approved permissive/copyleft license exists.
  2. *Repository Dormancy*: Ensures commits exist within the last 365 days.
  3. *Default Branch CI*: Verifies default branch builds are passing if CI workflows exist.
  4. *Root Directory Binary Check*: Confirms no precompiled executable files (.exe, .dll, .so, .bin, .out) reside in the repository root. Note: subdirectories and package build scripts are not scanned.
- **Returns**: Individual gate outcomes (`PASS`, `FAIL`, `UNKNOWN`), severity, evaluation rationale, and blockers count.

### 3. `calculate_responsiveness`
Calculates maintainer responsiveness while strictly distinguishing human activity from automated bots.
- **Arguments**:
  - `audit_id` *(string, required)*: Identifier of the initialized audit.
- **Returns**:
  - Median PR first human response time (hours).
  - Overall PR merge rate (percentage).
  - Unanswered issue percentage.
  - Bot comment filtering metrics.

### 4. `analyze_contribution_accessibility`
Evaluates repository documentation clarity, beginner issues, and newcomer opportunities.
- **Arguments**:
  - `audit_id` *(string, required)*: Identifier of the initialized audit.
- **Returns**:
  - Presence of `README`, `CONTRIBUTING`, `CODE_OF_CONDUCT`, and setup guides.
  - GSoC ideas document presence (`has_gsoc_doc`, inspecting root, `docs/outreach/`, `docs/`, and `.github/`).
  - Open beginner-friendly issues (`good first issue`, `help wanted`).
  - Newcomer pull request merge rate.

### 5. `calculate_scorecard`
Scores the repository across all 10 standardized criteria (0–2 scale, 20 maximum points) and determines the final audit verdict.
- **Arguments**:
  - `audit_id` *(string, required)*: Identifier of the initialized audit.
- **Scoring Rubric (10 Criteria, 0–2 Points Each)**:
  1. *GSoC History & Mentorship Track Record*: Verified ideas list or past participation (missing documents score 0 / marked UNKNOWN).
  2. *Commit Vitality & Cadence*: Commit recency and frequency over 30/90/365 days.
  3. *Issue Hygiene & Backlog Health*: Ratio of open issues with recent maintainer triage.
  4. *PR Velocity & Review Turnaround*: Median first human response time (< 72 hrs = exemplary).
  5. *Onboarding & Documentation*: Clear setup instructions, architecture docs, contribution guidelines.
  6. *Newcomer Accessibility*: Triage of beginner-friendly tasks and newcomer PR merge rate.
  7. *CI/CD & Automated Testing Rigor*: Active CI workflows passing on default branch.
  8. *Dependency Health & Install Safety*: Clean dependencies, zero precompiled binaries.
  9. *Community Culture & Conduct*: Code of conduct enforcement, inclusive communication.
  10. *Project Governance & Bus Factor*: Distributed committers avoiding single-maintainer bottlenecks.
- **Verdict Precedence**:
  - **REJECT**: Any critical hard gate `FAIL` or total score < 11.
  - **NEEDS MANUAL REVIEW**: Any hard gate `UNKNOWN` or total score 8–10.
  - **CONDITIONAL**: Total score 11–15 with no failed hard gates.
  - **APPROVE**: Total score 16–20 with all hard gates `PASS`.
- **Returns**: Total score, percentage attainment, criteria breakdown with rationales, triggered disqualifiers, and final verdict.

### 6. `validate_evidence`
Validates that every claim, finding, and scorecard point is grounded in verified primary data.
- **Arguments**:
  - `audit_id` *(string, required)*: Identifier of the initialized audit.
- **Taxonomy Enforced**:
  - `CONFIRMED`: Direct observation from GitHub REST API payload or file content.
  - `INFERRED`: Derived statistical metric (e.g., median response time).
  - `UNKNOWN`: Missing or unverified data source (never defaults to passing).
- **Returns**: Evidence count, confidence distributions, and ungrounded finding warnings.

### 7. `generate_pdf_report`
Compiles an executive multi-section PDF audit report in `reports/generated/`.
- **Arguments**:
  - `audit_id` *(string, required)*: Identifier of the initialized audit.
- **Report Features**:
  - Prominent final decision banner (`APPROVE`, `CONDITIONAL`, `NEEDS MANUAL REVIEW`, `REJECT`).
  - Repository metadata card with commit SHA and license information.
  - Complete 10-criterion scorecard table with evidence rationales.
  - Detailed maintainer responsiveness and newcomer accessibility tables.
  - Technical risks, critical findings, and remediation advice.
  - Suggested contribution opportunities table with direct links.
  - Grounded evidence appendix with source endpoints and confidence levels.
  - Two-pass `NumberedCanvas` rendering running headers and footers ("Page X of Y").
  - Dynamic TrueType font registration (`DejaVuSans` / `DejaVuSans-Bold` at `/usr/share/fonts/truetype/dejavu/`) with graceful fallback to Helvetica.
  - Safe Unicode fallback handling: emojis safely converted to `[name]` (e.g. `[rocket]`), CJK characters converted to `[U+XXXX]` (e.g. `[U+4E16]`), and accented Latin characters (`é`, `ü`, `ñ`, `ç`, `ø`, etc.) preserved.
- **Returns**: Absolute file path, file name, and file size in bytes.

---

## Storage & Artifact Integrity Manifest

Audit data contracts and baseline digests are stored under `data/<audit_id>/` with strict filesystem isolation:

```text
data/
└── audit_pallets_flask_1700000000/
    ├── raw_data.json   # Full raw GitHub API response payloads
    ├── audit.json      # Structured AuditReport contract
    ├── evidence.json   # Grounded EvidenceItem collection
    └── manifest.json   # Persisted integrity manifest with SHA-256 and byte sizes
```

> [!NOTE]
> **Manifest Scope & PDF Reports**: The SHA-256 integrity manifest specifically tracks stored audit data contracts (`raw_data.json`, `audit.json`, and `evidence.json`) in `data/<audit_id>/`. The compiled ReportLab PDF report is generated separately under `reports/generated/` and is outside this data manifest.

- **Integrity Manifest (`manifest.json`)**:
  Generated atomically upon audit completion (`calculate_scorecard`). Records baseline SHA-256 digests and file sizes for `raw_data.json`, `audit.json`, and `evidence.json`.
- **Tamper & Corruption Detection**:
  `StorageService.verify_audit_reproducibility(audit_id)` evaluates stored files against the baseline manifest, returning explicit artifact integrity metadata:
  - `VERIFIED`: All tracked files exist, byte counts match, and SHA-256 checksums match perfectly (`is_tampered: False`, `is_reproducible: True`).
  - `TAMPERED`: Any file was modified, truncated, deleted, or size/hash mismatch detected (`is_tampered: True`, `is_reproducible: False`).
  - `CORRUPTED_MANIFEST`: The `manifest.json` file is malformed, truncated, empty, or missing tracked entries (`is_tampered: True`, `is_reproducible: False`).
  - `UNVERIFIED`: The audit directory contains files that predate manifest generation, reporting them safely as unverified rather than falsely claiming integrity (`is_tampered: None`, `is_reproducible: False`).
  - `NOT_FOUND`: No audit files or manifest exist for the requested audit ID.
- **Path Traversal Protection**: Audit IDs are strictly validated (`^[a-zA-Z0-9_\-]{1,128}$`). Directory traversal attempts (`../`) and separator characters are rejected immediately.
- **Atomic Operations**: All file writes stream to temporary files (`*.tmp.*`) in the target audit directory and are committed atomically via `os.replace`.
- **Corruption Resilience**: Zero-byte, empty, or unparseable JSON files trigger `StorageCorruptionError` without server crashes.

> [!WARNING]
> **Local Integrity Manifest Disclaimer**: Local manifests stored alongside audit files are not cryptographically signed. They detect accidental corruption, truncation, deletions, or subsequent modifications in the local environment, but do not protect against an attacker who possesses host write access to both the manifest and the data files. They establish stored artifact integrity rather than execution reproducibility across shifting network states or environments.

---

## AI-Client-Driven Architecture & MCP Integration (Phase 4.2)

Shinobi operates under an **AI-client-driven architecture**. Rather than requiring an internal LLM runtime or hard-coded API credentials, Shinobi relies on the top-level AI client (such as **Claude Code** or **Google Antigravity CLI**) to orchestrate the repository audit using the user's existing subscription credentials.

Shinobi runs as a deterministic Model Context Protocol (MCP) server over `stdio`, exposing seven specialized vetting tools. The official native Go GitHub MCP server operates independently alongside Shinobi as a co-equal tool provider for qualitative context.

### 1. Integration Architecture

```
                  ┌───────────────────────────────────────────────┐
                  │ AI Client (Claude Code / Antigravity CLI)     │
                  │ - Orchestrates 9-step repository audit        │
                  │ - Uses existing subscription authentication   │
                  │ - Discovers tools independently from servers  │
                  │ - Synthesizes qualitative executive narrative │
                  └───────────────────────┬───────────────────────┘
                                          │ stdio MCP transports
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
┌─────────────────────────────────────────┐   ┌─────────────────────────────────────────┐
│           Shinobi MCP Server            │   │          GitHub MCP Server              │
│       (Local stdio Python server)       │   │       (Official native Go binary)       │
│ - 7 deterministic vetting tools         │   │ - Contextual codebase exploration       │
│ - Internal GitHub REST client (primary) │   │ - Strictly read-only toolset            │
│ - Immutable 10-criterion scorecard      │   │ - Independent observational context     │
│ - Tamper-evident PDF audit reports      │   │ - Cannot alter Shinobi scores or gates  │
└─────────────────────────────────────────┘   └─────────────────────────────────────────┘
```

### 2. Evidence Provenance & Data Boundaries

To prevent AI hallucination and ensure absolute due diligence rigor, Shinobi enforces strict evidence provenance boundaries:

- **Shinobi-Verified Primary Evidence**: Collected directly by Shinobi's internal GitHub REST client and stored in `data/<audit_id>/raw_data.json`. Only this primary evidence feeds into the deterministic scoring engine, eligibility hard gates, and the formal PDF report.
- **GitHub MCP Observations**: Collected independently by the external AI client (e.g. browsing file contents or specific pull requests). These observations enrich the AI's qualitative conversational narrative but **never** enter Shinobi's internal evidence storage and **never** influence numeric scores or gate verdicts.
- **Conflict Resolution**: If an AI observation conflicts with Shinobi's collected metrics, Shinobi-verified primary evidence is authoritative. The AI client must note observational discrepancies in its qualitative synthesis without altering the deterministic verdict.

### 3. Client MCP Configuration Examples

Both MCP servers are configured directly in your AI client.

#### A. Google Antigravity CLI

Configure Shinobi and GitHub MCP in Antigravity CLI either globally or per-workspace:

- **Global Config**: `~/.gemini/config/mcp_config.json`
- **Workspace Config**: `.agents/mcp_config.json`

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
      "command": "/home/divy547/tools/github-mcp-server/github-mcp-server",
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

#### B. Claude Code

Configure Shinobi and GitHub MCP in Claude Code using project or user configuration files, or via CLI:

- **Project Config**: `.mcp.json`
- **User Config**: `~/.claude.json`

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
      "command": "/home/divy547/tools/github-mcp-server/github-mcp-server",
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

Or add via Claude Code CLI commands:
```bash
claude mcp add shinobi -- uv --directory /absolute/path/to/Shinobi run repovet-mcp
```

### 4. Nine-Step AI Client Vetting Workflow

When auditing an open-source repository, the AI client executes the following standardized 9-step vetting sequence:

1. **Step 1: Primary Evidence Ingestion (`analyze_repository`)**
   *Mandatory first step.* Shinobi collects raw repository metadata, commits, PRs, issues, root contents, and workflows via its internal GitHub REST client, caching the payload in `data/<audit_id>/raw_data.json` and returning an `audit_id`.
2. **Step 2: Contextual Exploration (Optional GitHub MCP tools)**
   *Independent exploration.* The AI client optionally invokes read-only GitHub MCP tools (e.g. `get_file_contents`, `list_issues`) to examine project-specific documentation or architectural patterns.
3. **Step 3: Eligibility Hard Gates (`check_hard_gates`)**
   *Diagnostic.* Evaluates OSI license validity, 365-day dormancy, default branch CI status, and safe installation.
4. **Step 4: Maintainer Velocity (`calculate_responsiveness`)**
   *Diagnostic.* Measures median PR first human response times and issue response rates while filtering out automated bots.
5. **Step 5: Documentation & Newcomer Hygiene (`analyze_contribution_accessibility`)**
   *Diagnostic.* Assesses onboarding documentation (README, CONTRIBUTING, Code of Conduct) and beginner issue availability.
6. **Step 6: Deterministic Scoring & Verdict (`calculate_scorecard`)**
   *Core scoring.* Executes the 10-criterion scoring engine (0–20 points, 0–100%), determines the final verdict (`APPROVE`, `FLAG`, `REJECT`), persists `audit.json` and `evidence.json`, and generates the SHA-256 integrity manifest.
7. **Step 7: Evidence Grounding Validation (`validate_evidence`)**
   *Verification.* Validates citation grounding and confidence ratings (`CONFIRMED`, `INFERRED`, `UNKNOWN`).
8. **Step 8: PDF Report Compilation (`generate_pdf_report`)**
   *Deliverable.* Compiles the tamper-evident ReportLab PDF report in `reports/generated/` and updates the SHA-256 integrity manifest.
9. **Step 9: Executive Narrative Synthesis (AI Client)**
   *Synthesis.* The AI client reads the verified scorecard, findings, and PDF location to write a clear executive narrative for the user, summarizing strengths, risks, and next steps without fabricating or modifying any scores.

### 5. Integrity & Storage Guarantees

- **Tamper Detection (Not Cryptographic Immutability)**: The SHA-256 integrity manifest (`manifest.json`) provides local tamper detection. It accurately detects accidental file modifications, deletions, or corruptions. However, because local manifests are not signed by an external PKI authority, an attacker with write access to the filesystem could modify both the audit file and the manifest.
- **Snapshot Overwrites**: Re-running `analyze_repository` with an existing `audit_id` refreshes and safely overwrites `raw_data.json` with new primary data.
- **PAT Scoping & Rate Limits**: GitHub personal access tokens require only standard public repository read permissions. Authenticated tokens provide 5,000 requests/hour, whereas unauthenticated access is capped at 60 requests/hour.

---

## Troubleshooting & Diagnostics

- **Protocol Output Isolation**: Standard output (`stdout`) is reserved strictly for JSON-RPC MCP messages. All server diagnostics, startup messages, and errors are written to `stderr`.
- **GitHub Rate Limits**:
  - *Unauthenticated*: 60 requests/hour per IP.
  - *Authenticated*: 5,000 requests/hour per token.
  - When limits are reached, Shinobi raises `RateLimitExceededError` and surfaces the reset time in UTC without crashing.
- **Tool Error Handling**: If a tool fails (e.g., non-existent audit ID, unparseable repository target, or invalid arguments), the server returns `CallToolResult(is_error=True)` with a clear, sanitized error message. Secrets and tokens are automatically redacted.
- **Configuration Validation**: At startup, `Settings.validate_startup_config()` verifies YAML configurations exist, storage directories are writable, and API URLs are valid HTTP/HTTPS endpoints before listening for requests.

---

## Development & Testing

```bash
# Run the complete test suite
uv run pytest -v

# Run Phase 4 client workflow and tool definition tests specifically
uv run pytest tests/unit/test_tool_definitions.py tests/integration/test_client_workflow.py -v

# Run lint checks with Ruff
uv run ruff check .

# Check code formatting with Ruff
uv run ruff format --check .

# Automatically apply Ruff fixes and formatting
uv run ruff check --fix .
uv run ruff format .
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
