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
- **Atomic Writes & Audit Reproducibility**: Audit data, raw payloads, and scorecards are written atomically via temporary files and `os.replace`. Raw API snapshots in `data/<audit_id>/` guarantee 100% offline audit reproducibility with SHA-256 verification.
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
│       │   └── vetting_tools.py # 7 registered MCP tool handlers
│       │
│       ├── orchestration/      # AI orchestration & multi-MCP client integration
│       │   ├── __init__.py
│       │   ├── gemini_orchestrator.py # Gemini function calling loop & boundary enforcement
│       │   ├── github_mcp_client.py   # Official GitHub MCP server client (strictly read-only)
│       │   ├── mcp_client.py          # Base async stdio MCP client abstraction
│       │   ├── models.py              # ToolCallRecord, OrchestrationRequest/Result
│       │   └── shinobi_mcp_client.py  # Local Shinobi deterministic MCP client
│       │
│       └── reporting/          # PDF generation & validation
│           ├── __init__.py
│           ├── pdf_generator.py # ReportLab PDF audit report compiler
│           └── pdf_validator.py # Low-level PDF structural validator
│
├── tests/                      # Automated test suite (81 unit & integration tests)
│   ├── conftest.py             # Pytest fixtures & mock environments
│   ├── fixtures/               # Mock payloads & sample repository data
│   ├── integration/            # Stdio protocol & workflow integration tests
│   │   ├── test_mcp_protocol.py
│   │   ├── test_server_init.py
│   │   └── test_vetting_tools.py
│   └── unit/                   # Isolated component & service tests
│       ├── test_analytics_services.py
│       ├── test_config.py
│       ├── test_evidence_validator.py
│       ├── test_github_client.py
│       ├── test_github_client_hardening.py
│       ├── test_imports.py
│       ├── test_orchestration.py
│       ├── test_pdf_generator.py
│       ├── test_pdf_hardening.py
│       ├── test_scoring_engine.py
│       ├── test_security.py
│       └── test_storage_service.py
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
| `REPOVET_GITHUB_TOKEN` | *(None)* | GitHub Personal Access Token. Strongly recommended: raises rate limits from 60 to 5,000 req/hr. |
| `REPOVET_GITHUB_API_URL` | `https://api.github.com` | Base URL for GitHub REST API calls. |
| `REPOVET_LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Diagnostics are routed exclusively to `stderr`. |
| `REPOVET_SCORING_CONFIG_PATH` | `config/scoring.yaml` | Path to declarative scoring definitions and criteria rubrics. |
| `REPOVET_THRESHOLDS_CONFIG_PATH` | `config/thresholds.yaml` | Path to verdict thresholds and hard-gate disqualifiers. |
| `REPOVET_DATA_DIR` | `data` | Directory for raw API snapshots and audit JSON files. |
| `REPOVET_REPORTS_DIR` | `reports` | Directory where PDF reports are compiled (`reports/generated/`). |
| `REPOVET_LOGS_DIR` | `logs` | Directory for server log outputs. |
| `REPOVET_GEMINI_API_KEY` | *(None)* | Google Gemini API key (required for Phase 4 AI orchestration). |
| `REPOVET_AI_MODEL` | `gemini-2.0-flash` | Gemini model for request interpretation and tool routing. |
| `REPOVET_ORCHESTRATION_TIMEOUT_SECONDS` | `120.0` | Total session timeout for Gemini orchestration loops. |
| `REPOVET_MCP_TIMEOUT_SECONDS` | `30.0` | Per-tool call timeout for stdio MCP clients. |
| `REPOVET_MAX_ORCHESTRATION_STEPS` | `10` | Maximum sequential tool-call iterations per session. |
| `REPOVET_GITHUB_MCP_COMMAND` | `npx` | Command to launch official GitHub MCP server (`npx` or `docker`). |
| `REPOVET_GITHUB_MCP_ARGS` | `["-y", "@modelcontextprotocol/server-github"]` | Arguments for GitHub MCP server command. |
| `REPOVET_SHINOBI_MCP_COMMAND` | `repovet-mcp` | Command to launch local Shinobi MCP server. |

> **Note on Standalone vs Orchestration Execution:** Shinobi's vetting engine remains 100% deterministic and standalone. The server functions completely without Gemini API keys when run as a standalone MCP server. The Gemini API key is only required when invoking the Phase 4 `GeminiOrchestrator` service.

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
  4. *Installation Safety*: Confirms no precompiled binaries or install hooks compromise safety.
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
  - GSoC ideas document presence (`has_gsoc_doc`).
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

## Storage & Audit Integrity Manifest

Audit data and reproducibility baselines are stored under `data/<audit_id>/` with strict filesystem isolation:

```text
data/
└── audit_pallets_flask_1700000000/
    ├── raw_data.json   # Full raw GitHub API response payloads
    ├── audit.json      # Structured AuditReport contract
    ├── evidence.json   # Grounded EvidenceItem collection
    └── manifest.json   # Persisted integrity manifest with SHA-256 and byte sizes
```

- **Integrity Manifest (`manifest.json`)**:
  Generated atomically upon audit completion (`calculate_scorecard`). Records baseline SHA-256 digests and file sizes for `raw_data.json`, `audit.json`, and `evidence.json`.
- **Tamper & Corruption Detection**:
  `StorageService.verify_audit_reproducibility(audit_id)` evaluates stored files against the baseline manifest, returning explicit integrity metadata:
  - `VERIFIED`: All tracked files exist, byte counts match, and SHA-256 checksums match perfectly (`is_tampered: False`, `is_reproducible: True`).
  - `TAMPERED`: Any file was modified, truncated, deleted, or size/hash mismatch detected (`is_tampered: True`, `is_reproducible: False`).
  - `CORRUPTED_MANIFEST`: The `manifest.json` file is malformed, truncated, empty, or missing tracked entries (`is_tampered: True`, `is_reproducible: False`).
  - `UNVERIFIED`: The audit directory contains files that predate manifest generation, reporting them safely as unverified rather than falsely claiming integrity (`is_tampered: None`, `is_reproducible: False`).
  - `NOT_FOUND`: No audit files or manifest exist for the requested audit ID.
- **Path Traversal Protection**: Audit IDs are strictly validated (`^[a-zA-Z0-9_\-]{1,128}$`). Directory traversal attempts (`../`) and separator characters are rejected immediately.
- **Atomic Operations**: All file writes stream to temporary files (`*.tmp.*`) in the target audit directory and are committed atomically via `os.replace`.
- **Corruption Resilience**: Zero-byte, empty, or unparseable JSON files trigger `StorageCorruptionError` without server crashes.

> [!WARNING]
> **Local Integrity Manifest Disclaimer**: Local manifests stored alongside audit files are not cryptographically signed. They detect accidental corruption, truncation, deletions, or subsequent modifications in the local environment, but do not protect against an attacker who possesses host write access to both the manifest and the data files.

---

## AI Orchestration & Multi-MCP Integration (Phase 4.1)

Shinobi integrates Google Gemini (`google-genai` Python SDK) with Model Context Protocol (MCP) clients to deliver autonomous repository vetting while strictly safeguarding deterministic scoring integrity.

### 1. Integration Architecture

```
User Vetting Request ("Vet pallets/flask for GSoC 2027 eligibility")
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│              Gemini Orchestrator (`google-genai` SDK)            │
│  - Interprets user request & coordinates analysis                │
│  - Controlled Function Calling with discovered MCP schemas       │
│  - Sequential loop control (configurable step & time limits)     │
│  - Synthesizes natural language audit explanations               │
└───────────────────────────────┬──────────────────────────────────┘
                                │ Controlled Tool Routing
                ┌───────────────┴───────────────┐
                ▼                               ▼
┌───────────────────────────────┐ ┌───────────────────────────────┐
│       Shinobi MCP Client      │ │       GitHub MCP Client       │
│     (Local stdio transport)   │ │   (Official stdio transport)  │
│ - Authoritative vetting logic │ │ - Contextual exploration      │
│ - 7 deterministic tools       │ │ - Strictly read-only filter   │
│ - Immutable scorecard/verdict │ │ - Write operations blocked    │
└───────────────────────────────┘ └───────────────────────────────┘
```

### 2. Mandatory Evidence & Scoring Boundaries

- **Deterministic Immutability**: Shinobi is the sole authority for scoring. Gemini **cannot** calculate, alter, or override Shinobi's 10-criterion scorecard (0–20 points) or final verdicts (`APPROVE`, `CONDITIONAL`, `REJECT`, `NEEDS MANUAL REVIEW`). Even if the model text contains an opinion or hallucinated score, programmatic contracts (`result.scorecard` and `result.decision`) strictly enforce the deterministic output from Shinobi.
- **Evidence Separation**:
  - `github_mcp_observations`: Read-only discovery context from the official GitHub MCP server. These are recorded separately and unverified as audit evidence.
  - `shinobi_verified_evidence`: Grounded, primary-source evidence generated exclusively by the Shinobi vetting engine.
- **Anti-Hallucination**: The orchestrator prevents Gemini from inventing metrics, passing empty checks, or counting observations twice.

### 3. Setup & Configuration

#### A. Gemini API Setup
Obtain an API key from [Google AI Studio](https://aistudio.google.com/) and set:
```bash
export REPOVET_GEMINI_API_KEY="AIzaSy..."
export REPOVET_AI_MODEL="gemini-2.0-flash"
```

#### B. Local GitHub MCP Server Setup
The official GitHub MCP server communicates via stdio. You can run it via `npx` (Node.js 18+) or Docker:

```bash
# Option 1: NPX (Default)
export REPOVET_GITHUB_MCP_COMMAND="npx"
export REPOVET_GITHUB_MCP_ARGS='["-y", "@modelcontextprotocol/server-github"]'
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_..."

# Option 2: Docker
export REPOVET_GITHUB_MCP_COMMAND="docker"
export REPOVET_GITHUB_MCP_ARGS='["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", "ghcr.io/modelcontextprotocol/servers/github:latest"]'
```

#### C. Local Shinobi MCP Client Setup
The Shinobi MCP client launches the local Shinobi server over stdio:
```bash
export REPOVET_SHINOBI_MCP_COMMAND="repovet-mcp"
export REPOVET_SHINOBI_MCP_ARGS='[]'
```

### 4. Security & Permissions

- **Default-Deny Positive Read-Only Allowlist**: The GitHub MCP client operates under strict default-deny security. Only verified read-only discovery tools (`get_file_contents`, `list_commits`, `get_commit`, `list_issues`, `get_issue`, `list_pull_requests`, `search_repositories`, etc.) are permitted. All write/mutating tools (`create_*`, `update_*`, `delete_*`, `push_*`, `merge_*`, `fork_*`, `add_*`) and non-prefix actions (`close_issue`, `lock_issue`, `approve_pull_request`, `dispatch_workflow`, `archive_repository`) as well as unknown tools are blocked both at discovery and immediately before execution.
- **Session Audit ID Locking & Anti-Hijacking**: The orchestrator establishes a trusted audit session bound to the active target repository. Gemini cannot pass foreign `audit_id` arguments or switch repositories midway to obtain unearned scorecards or decisions from previous audits.
- **Subprocess Environment Isolation**: Subprocesses are spawned in minimal, isolated environments preserving safe system essentials (`PATH`, `HOME`, temporary directories) while strictly stripping ambient host secrets (`GEMINI_API_KEY`, AWS credentials, cloud tokens). Only explicitly configured tokens (`GITHUB_PERSONAL_ACCESS_TOKEN`) reach the intended child process.
- **Dynamic Secret Redaction**: Configured tokens, API keys, and known authorization header patterns are scrubbed dynamically from error messages and logs.
- **Untrusted Code Policy**: Zero repository code execution. The orchestrator never executes build scripts, setup scripts, or test runners from audited repositories.

### 5. Implemented vs. Deferred Capabilities

| Capability | Status | Description |
|:---|:---|:---|
| **Gemini Function Calling Loop** | **Implemented** | Discovers MCP tool schemas, normalizes for OpenAPI 3.0, and executes controlled multi-turn loops. |
| **Shinobi MCP Client** | **Implemented** | Connects to local Shinobi server over stdio and invokes all 7 deterministic tools. |
| **GitHub MCP Client** | **Implemented** | Connects to official GitHub MCP server with strict default-deny read-only allowlist. |
| **Boundary & Anti-Hijacking Protection** | **Implemented** | Enforces that Gemini cannot alter scorecards, hijack foreign audits, or switch target repositories. |
| **Subprocess Environment Isolation** | **Implemented** | Spawns child MCP servers in isolated environments without leaking ambient host API keys. |
| **Execution Safety Limits** | **Implemented** | Configurable iteration limits (`max_steps`) and timeout guards (`asyncio.timeout`). |
| **Live Multi-Agent Peer Debate** | *Deferred (Phase 4.2)* | Extended multi-agent verification and peer review dialogues. |
| **Real Repository Acceptance** | *Deferred (Phase 5)* | Live end-to-end vetting on actual candidate open-source repositories. |

---

## Troubleshooting & Diagnostics

- **Protocol Output Isolation**: Standard output (`stdout`) is reserved strictly for JSON-RPC MCP messages. All server diagnostics, startup messages, and errors are written to `stderr`.
- **GitHub Rate Limits**:
  - *Unauthenticated*: 60 requests/hour per IP.
  - *Authenticated*: 5,000 requests/hour per token.
  - When limits are reached, Shinobi raises `RateLimitExceededError` and surfaces the reset time in UTC without crashing.
- **Tool Error Handling**: If a tool fails (e.g., non-existent audit ID, unparseable repository target, or invalid arguments), the server returns `CallToolResult(is_error=True)` with a clear, sanitized error message. Secrets and tokens are automatically redacted.
- **Configuration Validation**: At startup, `Settings.validate_startup_config()` verifies YAML configurations exist, storage directories are writable, and API URLs are valid HTTP/HTTPS endpoints before listening for requests. `Settings.validate_orchestration_config()` validates requirements for AI orchestration.

---

## Development & Testing

```bash
# Run the complete test suite
uv run pytest -v

# Run Phase 4 AI orchestration unit and integration tests specifically
uv run pytest tests/unit/test_orchestration.py tests/integration/test_mcp_client.py -v

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
