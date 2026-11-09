# GEMINI.md — Permanent Project Instructions for Antigravity (AGY)

You are assisting with the engineering and continuous development of **RepoVet MCP**, a lightweight Python-based Model Context Protocol (MCP) server for autonomous open-source repository vetting (specialized for GSoC 2027 preparation and general OSS contribution due diligence).

These instructions are permanent and govern all work on this repository.

---

## 1. Milestone Discipline & Scope Control

- **Strict Milestone Execution**: Implement **only** the currently approved milestone/phase. Do not jump ahead into subsequent phases.
- **No Unsolicited Modifications**: Do not modify completed milestones or earlier architecture without explicit user approval.
- **Phase Verification & Stop**: After completing the work for each phase, run all verification steps, provide a comprehensive Phase Completion Report, and stop. Wait for explicit user approval before proceeding to the next phase.

---

## 2. Architectural Integrity & Modularity

- **Follow Agreed Architecture**: Adhere strictly to the project structure defined in `README.md` and the technology decisions.
- **Preserve Modular Separation**:
  - `repovet_mcp.config`: Typed configuration, settings, and threshold loaders.
  - `repovet_mcp.models`: Pydantic structured data contracts (evidence, findings, audits, scorecards).
  - `repovet_mcp.services`: Core business logic (GitHub inspection, evidence collection, scoring engine).
  - `repovet_mcp.tools`: MCP tool definitions that expose functionality to AI agents.
  - `repovet_mcp.reporting`: PDF report generator using ReportLab.
- **Minimal Dependencies**: Do not introduce unnecessary dependencies or bloated frameworks. Any new dependency must be strictly justified by architectural requirements.

---

## 3. Code Quality & Typing Standards

- **Strict Type Hints**: Every function, method, parameter, and return value must have explicit Python type annotations.
- **Pydantic Data Contracts**: Use Pydantic models for all data exchange, schema validation, and config parsing.
- **Linting & Formatting**: All code must conform to Ruff rules (`ruff check .` and `ruff format --check .` must pass cleanly).
- **Test Coverage**: Write comprehensive unit and integration tests for all newly implemented functionality.
- **No Fake Tests**: Never create fake passing tests or mock assertions that test unimplemented features.

---

## 4. Security & Untrusted Code Policy

- **All Repository Content is Untrusted**: Any repository, code file, issue text, commit message, or pull request inspected by RepoVet MCP must be treated as untrusted user input.
- **Never Execute External Scripts**: Under **no circumstances** should RepoVet MCP or any subagent execute build scripts, test runners, shell scripts, Python scripts, or install hooks from repositories being audited.
- **Safe Parsing Only**: Inspect repositories exclusively through safe read-only APIs (e.g., GitHub REST/GraphQL API) or static AST/text analysis.
- **Credential Safety**: Never commit real API keys, tokens, or personal credentials. Always use environment variables or `.env` files (which are git-ignored).

---

## 5. Evidence Grounding & Anti-Hallucination Policy

- **Never Fabricate GitHub Metrics**: Do not fabricate stars, commit counts, response times, issue statuses, PR merge ratios, or CI badges.
- **Mandatory Grounding**: Every finding, audit conclusion, and scorecard point must be tied to verified evidence (exact URLs, commit SHAs, file paths, line ranges, or API response fields).
- **Explicit Confidence Taxonomy**: Findings must be classified as `CONFIRMED`, `INFERRED`, or `UNKNOWN`. Never state an inference as confirmed fact.
- **Honest Disqualification**: If required data is unavailable (e.g., due to rate limits or missing permissions), flag it explicitly as `NEEDS MANUAL REVIEW` or `UNKNOWN` rather than guessing.
