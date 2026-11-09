# Vetting Methodology: How to Vet an Open-Source Repo Before Contributing

## Overview

Contributing to open-source software—especially when preparing for high-stakes programs like **Google Summer of Code (GSoC 2027)**—requires careful due diligence. Contributing to an inactive, poorly maintained, unmentored, or culturally toxic repository can result in hundreds of wasted hours, ignored pull requests, or unworkable local environments.

The **RepoVet Methodology** establishes a structured, evidence-backed evaluation pipeline across **Nine Vetting Phases**, culminating in a **10-Criterion Scorecard (0–20 Scale)** and a decisive verdict:
- **APPROVE** (Score 16–20, 0 hard blockers)
- **CONDITIONAL** (Score 11–15, 0 hard blockers)
- **NEEDS MANUAL REVIEW** (Score 8–10, or unverified signals)
- **REJECT** (Score 0–7, or presence of hard blockers)

---

## The Nine Vetting Phases

```
+-------------------------------------------------------------------------+
|                      NINE REPOSITORY VETTING PHASES                     |
+-------------------------------------------------------------------------+
|  Phase 1: Repository Identity, Provenance & Licensing                   |
|  Phase 2: Project Vitality & Maintenance Pulse                          |
|  Phase 3: Governance, Maintainer Dynamics & Culture                     |
|  Phase 4: Contributor Responsiveness & PR Velocity                      |
|  Phase 5: Documentation Completeness & Onboarding Experience            |
|  Phase 6: Issue Hygiene & Newcomer Accessibility                        |
|  Phase 7: Build Integrity, CI/CD & Testing Rigor                        |
|  Phase 8: Dependency Health, Supply Chain & Security Posture            |
|  Phase 9: Mentorship Capability, GSoC Alignment & Community Engagement  |
+-------------------------------------------------------------------------+
```

### Phase 1: Repository Identity, Provenance & Licensing
- **Goal**: Confirm the repository's identity, ownership, intellectual property validity, and open-source licensing.
- **Key Inquiries**:
  - Does the project possess an OSI-approved open-source license (MIT, Apache 2.0, BSD, GPL, etc.)?
  - Who owns the repository (individual vs. foundation vs. corporate entity)?
  - Are there patent grants, contributor agreements (CLA/DCO), or restrictive dual-licensing clauses?
- **Red Flags**: Absence of a `LICENSE` file (defaulting to "All Rights Reserved"), non-standard proprietary terms.

### Phase 2: Project Vitality & Maintenance Pulse
- **Goal**: Measure whether the repository is actively evolving or slowly deteriorating into abandonware.
- **Key Inquiries**:
  - When was the most recent commit on the default branch (`main` / `master`)?
  - What is the commit frequency over the past 30, 90, and 365 days?
  - Is there an active release cadence with semantic versioning tags?
- **Red Flags**: Default branch dormant for >6 months; no releases in over a year; stagnant commit history.

### Phase 3: Governance, Maintainer Dynamics & Culture
- **Goal**: Assess the leadership structure, bus factor, and interpersonal tone in community discussions.
- **Key Inquiries**:
  - Is the project a single-maintainer project (bus factor = 1) or supported by a distributed core team?
  - Is there an explicit `CODE_OF_CONDUCT.md` with clear reporting contacts?
  - Are maintainer comments in issue trackers and PR reviews welcoming, constructive, and civil?
- **Red Flags**: Toxic, dismissive, or passive-aggressive communication; single maintainer refusing outside contributions.

### Phase 4: Contributor Responsiveness & PR Velocity
- **Goal**: Determine whether external contributions are actively reviewed and integrated or left on read.
- **Key Inquiries**:
  - What is the median time to first maintainer response on pull requests?
  - What percentage of external PRs are merged vs. closed without feedback vs. left open indefinitely?
  - How large is the stale PR backlog (>60 days with no interaction)?
- **Red Flags**: Large pileup of unreviewed external PRs; PRs open for 6+ months without maintainer comments.

### Phase 5: Documentation Completeness & Onboarding Experience
- **Goal**: Evaluate the developer onboarding path and contribution instructions.
- **Key Inquiries**:
  - Is there a clear, comprehensive `README.md` explaining project purpose and quickstart?
  - Does a dedicated `CONTRIBUTING.md` exist with explicit branching, testing, and PR guidelines?
  - Are local setup steps (prerequisites, build commands, test runs) reproducible and accurate?
- **Red Flags**: Missing `CONTRIBUTING.md`; broken setup commands; undocumented architecture.

### Phase 6: Issue Hygiene & Newcomer Accessibility
- **Goal**: Determine if there are realistic, well-scoped entry points for new contributors.
- **Key Inquiries**:
  - Are issues actively labeled with beginner tags (`good first issue`, `help wanted`, `beginner-friendly`)?
  - Are issue descriptions sufficiently detailed with reproduction steps or acceptance criteria?
  - Are issue templates configured for bug reports and feature requests?
- **Red Flags**: Thousands of untriaged issues; beginner-tagged issues that are actually massive architectural refactors; stale issue graveyard.

### Phase 7: Build Integrity, CI/CD & Testing Rigor
- **Goal**: Verify that automated validation works and safeguards the codebase.
- **Key Inquiries**:
  - Is continuous integration (CI) configured via GitHub Actions or similar automated platforms?
  - Does the CI test suite pass on the default branch?
  - Is there an automated test suite (unit, integration, end-to-end) that contributors can run locally?
- **Red Flags**: Red CI builds on `main`; absence of automated tests; flaky test suites that fail intermittently.

### Phase 8: Dependency Health, Supply Chain & Security Posture
- **Goal**: Ensure the project is not burdened with vulnerable dependencies or supply chain risks.
- **Key Inquiries**:
  - Are package lockfiles (`uv.lock`, `package-lock.json`, `poetry.lock`, `Cargo.lock`) committed?
  - Are automated dependency updates active (Dependabot, Renovate)?
  - Is there a `SECURITY.md` detailing vulnerability disclosure policies?
  - Are there known critical CVEs in dependencies?
- **Red Flags**: Severely outdated runtimes; unresolved critical CVE alerts; missing lockfiles.

### Phase 9: Mentorship Capability, GSoC Alignment & Community Engagement
- **Goal**: Evaluate suitability for formal mentorship programs (e.g., GSoC 2027) and student success.
- **Key Inquiries**:
  - Has the organization participated in past GSoC cycles, and what was their track record?
  - Are there dedicated communication channels (Discord, Slack, Matrix, GitHub Discussions)?
  - Is there a published project ideas list with designated mentor contacts?
- **Red Flags**: Explicit hostility toward student applicants; closed development behind corporate walls; no public communication channels.

---

## The 10-Criterion Scorecard (0–20 Scale)

Every repository is scored across 10 standardized criteria. Each criterion receives a score of **0**, **1**, or **2**:
- **0 Points**: Deficient, failing, or high-risk.
- **1 Point**: Acceptable, partial, or moderate.
- **2 Points**: Robust, exemplary, or fully verified.

| # | Criterion | Evaluated Phase | 0 Points (Deficient) | 1 Point (Partial) | 2 Points (Exemplary) |
|---|-----------|-----------------|----------------------|-------------------|----------------------|
| **1** | **Project Activity & Maintenance** | Phase 2 | Abandoned (>12 mo no commits/releases) | Sporadic (commits within 3-6 mo, irregular releases) | Vibrant (<30 days active commits, regular releases) |
| **2** | **Maintainer Responsiveness** | Phase 4 | PRs/issues unreviewed >60 days | Responses within weeks; backlog building | Median response <72h; constructive reviews |
| **3** | **Documentation & Setup** | Phase 5 | Missing/broken README; no setup guide | Basic overview, but incomplete setup steps | Comprehensive architecture, setup, prerequisites |
| **4** | **Contribution Guidelines** | Phase 5 | Missing `CONTRIBUTING.md` | Basic guide; missing branch/test standards | Detailed PR process, style rules, pre-checks |
| **5** | **Community & Conduct** | Phase 3 | Toxic tone; absent Code of Conduct | Standard CoC present; limited interactions | Clear CoC with reporting contacts; welcoming chat |
| **6** | **Issue Hygiene & Onboarding** | Phase 6 | Uncurated backlog; no newcomer tags | Some templates/labels; stale backlog | Active triage; clear `good first issue` / GSoC labels |
| **7** | **CI/CD & Testing Rigor** | Phase 7 | No CI; no tests; broken default branch | CI exists, but sparse tests or flaky builds | Green CI on default branch; robust test suite |
| **8** | **Dependency & Supply Chain** | Phase 8 | Outdated dependencies; critical CVEs | Reasonable dependencies; lockfile present | Modern pinned dependencies; Dependabot; clean scan |
| **9** | **Security & Licensing** | Phase 1 & 8 | No license; non-OSI license | Valid OSI license, but no `SECURITY.md` | OSI license, published `SECURITY.md`, CLA/DCO |
| **10** | **Mentorship & GSoC Feasibility** | Phase 9 | Unsuitable; no mentorship; closed org | Potential; open but uncurated ideas/guidance | GSoC track record; project ideas list; mentors |

**Total Score**: Sum of all 10 criteria = **0 to 20 Points**.

---

## Decision Thresholds

### 1. APPROVE (16 – 20 Points)
- **Status**: High-quality repository with active maintainers, healthy CI/CD, welcoming onboarding, and solid mentorship potential.
- **Action**: Proceed with confidence. Ideal candidate for GSoC proposal drafting and long-term open-source contributions.
- **Condition**: Must have **0** critical disqualifiers.

### 2. CONDITIONAL (11 – 15 Points)
- **Status**: Viable repository with minor deficiencies (e.g., slow response time, missing beginner issues, or sparse architecture documentation).
- **Action**: Proceed with targeted caution. Engage maintainers on small issues before investing time in large feature proposals.
- **Condition**: Must have **0** critical disqualifiers.

### 3. NEEDS MANUAL REVIEW (8 – 10 Points)
- **Status**: Ambiguous signals, conflicting evidence, or moderate risks (e.g., failing default branch CI or recent maintainer changeover).
- **Action**: Require human inspection. An engineer must verify repository viability before any contribution commitment.

### 4. REJECT (0 – 7 Points)
- **Status**: Severe structural, maintenance, or cultural failure.
- **Action**: Do not recommend for contribution. High risk of wasted time or abandoned efforts.

---

## Critical Disqualifiers (Hard Blockers)

Regardless of the numeric score, any of the following triggers immediate **REJECT** or **NEEDS MANUAL REVIEW**:
1. **Missing or Non-OSI License** -> **REJECT** (Legal and intellectual property liability).
2. **Abandoned / Dormant (>18 months no activity)** -> **REJECT** (Dead repository).
3. **Confirmed Toxic / Abusive Maintainers** -> **REJECT** (Community safety violation).
4. **Persistent Failing Default Branch Build** -> **NEEDS MANUAL REVIEW** (Broken infrastructure).
5. **Suspicious / Malicious Code Patterns** -> **NEEDS MANUAL REVIEW** (Security concern).
