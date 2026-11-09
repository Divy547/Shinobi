# RepoVet MCP

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/managed%20by-uv-purple.svg)](https://github.com/astral-sh/uv)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![MCP](https://img.shields.io/badge/MCP-Protocol-green.svg)](https://modelcontextprotocol.io/)

**RepoVet MCP** is a lightweight Python-based Model Context Protocol (MCP) server for autonomous open-source repository vetting, built especially for contributors preparing for **Google Summer of Code (GSoC 2027)** and engineers evaluating third-party open-source software before adoption or contribution.

RepoVet MCP empowers AI coding agents (such as Google Gemini via the Antigravity CLI) to systematically investigate target repositories across **Nine Vetting Phases**, calculate an evidence-grounded **10-Criterion Scorecard (0–20 Scale)**, validate primary evidence, and generate comprehensive PDF audit reports displaying a decisive verdict:
**APPROVE**, **CONDITIONAL**, **REJECT**, or **NEEDS MANUAL REVIEW**.

---

## Architecture Overview

RepoVet MCP follows a clean, modular source-layout architecture designed for extensibility, safety, and deterministic evaluation:

```
repovet-mcp/
├── pyproject.toml              # Project metadata, dependencies & tool configs
├── uv.lock                     # Deterministic dependency lockfile
├── README.md                   # Project documentation & operational guide
├── GEMINI.md                   # Permanent AI agent guidelines & safety rules
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules
│
├── config/                     # Declarative YAML configurations
│   ├── scoring.yaml            # 10 scorecard criteria definitions & 0-2 rubrics
│   └── thresholds.yaml         # Decision boundaries & critical disqualifiers
│
├── src/
│   └── repovet_mcp/
│       ├── __init__.py         # Package root with version metadata
│       ├── server.py           # FastMCP server lifecycle & entry point
│       │
│       ├── config/             # Typed settings & YAML loaders
│       │   ├── __init__.py
│       │   └── settings.py     # Pydantic Settings implementation
│       │
│       ├── models/             # Pydantic data contracts & domain schemas
│       │   ├── __init__.py
│       │   ├── evidence.py     # Grounded evidence & confidence models
│       │   ├── findings.py     # Audit findings & severity classifications
│       │   └── audit.py        # Scorecard, audit report & target models
│       │
│       ├── tools/              # MCP tool implementations (Phase 2+)
│       │   └── __init__.py
│       │
│       ├── services/           # GitHub API, evidence & scoring engines (Phase 2+)
│       │   └── __init__.py
│       │
│       └── reporting/          # ReportLab PDF report generation (Phase 5)
│           └── __init__.py
│
├── tests/                      # Automated test suite
│   ├── unit/                   # Isolated component tests
│   ├── integration/            # Multi-component integration tests
│   └── conftest.py             # Pytest fixtures & test configuration
│
├── knowledge/                  # Permanent methodology & policy references
│   ├── vetting-methodology.md  # 9-phase methodology & 10-criterion rubric
│   └── evidence-policy.md      # Ground truth, untrusted content & safety rules
│
├── data/                       # Cached audit payloads & raw API responses
│   └── .gitkeep
│
└── reports/                    # Output directory for generated PDF audits
    └── .gitkeep
```

---

## Key Capabilities

- **Nine Vetting Phases**: Systematically assesses repository identity, vitality pulse, community culture, maintainer responsiveness, documentation, issue hygiene, CI/CD testing, dependency health, and mentorship feasibility.
- **Strict 0–20 Scorecard**: Evaluates 10 standardized criteria on a 0–2 scale (0 = Deficient, 1 = Partial, 2 = Exemplary).
- **Decisive Verdicts**: Assigns **APPROVE** (16–20), **CONDITIONAL** (11–15), **NEEDS MANUAL REVIEW** (8–10), or **REJECT** (0–7).
- **Critical Disqualifiers**: Immediately flags hard blockers such as missing/non-OSI licenses, dormant repos (>18 mo), broken master builds, or toxic maintainers.
- **Untrusted Code Sandbox**: Never executes target code, build hooks, or scripts. Uses safe read-only API inspection.
- **Anti-Hallucination Evidence Grounding**: Every scorecard point and finding is linked to primary evidence (exact commit SHAs, line numbers, API response fields).

---

## Planned MCP Tools

In upcoming phases, RepoVet MCP will expose the following tools to AI agents:

1. `repovet_audit_repository`: Execute full 9-phase vetting on a GitHub repository, evaluate the 10 scorecard criteria, and return the final audit report with verdict.
2. `repovet_quick_scan`: Rapid health check scanning commit pulse, license presence, and immediate critical blockers.
3. `repovet_evaluate_criterion`: Deep-dive into a single criterion (e.g., `maintainer_responsiveness` or `ci_cd_and_testing`) with focused evidence extraction.
4. `repovet_validate_evidence`: Verify and ground findings against raw GitHub API data.
5. `repovet_generate_report`: Render an executive-ready ReportLab PDF report complete with visual scorecard tables and decision banners.

---

## Implementation Roadmap (Five Phases)

| Phase | Milestone | Scope & Deliverables | Status |
|:---:|:---|:---|:---:|
| **Phase 1** | **Project Foundation & Initial Structure** | Source layout packaging, `uv` dependency management, Ruff linting/formatting, Pytest harness, typed `pydantic-settings`, declarative YAML configs (`scoring.yaml`, `thresholds.yaml`), knowledge documentation (`vetting-methodology.md`, `evidence-policy.md`, `GEMINI.md`). | **Completed** |
| **Phase 2** | **Core Data Contracts, Models & Mock Engine** | Complete Pydantic schemas, validation rules, mock evidence fixtures, scorecard evaluation engine, and test harness. | Planned |
| **Phase 3** | **GitHub API Integration & Evidence Collectors** | Asynchronous `httpx` GitHub REST/GraphQL client, rate limit handling, response caching, evidence collectors across all 9 vetting phases. | Planned |
| **Phase 4** | **Scoring Engine, Heuristics & MCP Tools** | Scorecard evaluation algorithms, critical blocker detection, FastMCP tool implementations, and Antigravity tool binding. | Planned |
| **Phase 5** | **PDF Audit Report & Antigravity Validation** | ReportLab PDF layout generator, decision badge rendering, end-to-end MCP verification with Antigravity CLI and Gemini. | Planned |

---

## Getting Started

### Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) (fast Python package manager)

### Installation

Clone the repository and sync dependencies:

```bash
# Clone repository
cd repovet-mcp

# Install dependencies and sync virtual environment with uv
uv sync

# Install in editable mode
uv pip install -e .
```

### Environment Configuration

Copy the example environment file and configure your API tokens (optional for unauthenticated public repo scans):

```bash
cp .env.example .env
```

Configuration variables:
- `REPOVET_GITHUB_TOKEN`: GitHub Personal Access Token (recommended to raise API rate limits from 60 to 5,000 req/hr).
- `REPOVET_GEMINI_API_KEY`: Google Gemini API key for future AI-driven qualitative synthesis.
- `REPOVET_LOG_LEVEL`: Application log level (`INFO`, `DEBUG`, `WARNING`, `ERROR`).
- `REPOVET_SCORING_CONFIG_PATH`: Path to scoring criteria configuration (`config/scoring.yaml`).
- `REPOVET_THRESHOLDS_CONFIG_PATH`: Path to threshold configuration (`config/thresholds.yaml`).

---

## Development Commands

All development tasks are managed via `uv`:

```bash
# Run test suite
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run lint checks with Ruff
uv run ruff check .

# Automatically apply Ruff lint fixes
uv run ruff check --fix .

# Verify code formatting with Ruff
uv run ruff format --check .

# Format code with Ruff
uv run ruff format .

# Start the MCP server locally over stdio transport
uv run repovet-mcp
```
