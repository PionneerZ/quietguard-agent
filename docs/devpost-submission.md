# QuietGuard — Devpost submission pack

## Core fields

**Project name:** QuietGuard

**Tagline:** Disk pressure, handled quietly: a Strands agent that removes proven noise and brings uncertain evidence to a human.

**Track:** Professional Agents

**Repository:** https://github.com/PionneerZ/quietguard-agent

**Live demo:** https://pionneerz.github.io/quietguard-agent/

**Video:** https://vimeo.com/1224243653 — public 2:04 H.264 demo. The source MP4 is at `docs/assets/quietguard-demo.mp4`.

**Built with:** Python, Strands Agents SDK 1.54.0, HTML, JSON, SHA-256, pytest, GitHub Actions

## Project story

### Inspiration

Runaway diagnostic logs are a quiet but expensive operational problem. They grow while people work, then suddenly fill a workstation and interrupt trading tools, spreadsheets, design software, or other data-heavy desktop applications. Manual cleanup arrives late. Broad cleanup scripts are worse: they can treat user data as disposable simply because it is large.

QuietGuard starts from a stricter idea. An autonomous agent should handle known, regenerable noise end to end, while giving uncertain evidence to a person with enough context to make a fast decision.

### What it does

QuietGuard detects disk-pressure incidents, compares the current workspace with a saved baseline, classifies the files, builds a bounded plan, and optionally applies safe actions. It publishes a visual dashboard, a machine-readable incident report, and a tamper-evident audit chain after every cycle.

Automatic cleanup is deliberately narrow. A file must be inside the exact configured root, below a directory carrying an explicit `.quietguard-safe` marker, old enough, one of four regenerable file types, and inside the cycle byte budget. QuietGuard rechecks all of those conditions immediately before acting. Databases, documents, media, archives, unmarked logs, symlinks, Windows reparse points, and anything outside the exact root remain protected.

The contained demo creates a synthetic Excel-diagnostics log storm with four files. The agent detects 2.9 MB of growth, reclaims exactly 3.0 MB from two explicitly allowlisted logs, preserves a SQLite database and an unmarked log, and escalates one decision. It never touches the user's files.

### How we built it

The real `strands.Agent` loop coordinates four decorated Strands tools:

1. `scan_workspace` collects evidence without following symlinks or reparse points.
2. `build_guarded_plan` applies the marker, extension, age, and byte-budget policy.
3. `apply_safe_actions` revalidates every boundary at execution time.
4. `publish_dashboard` writes the visual and machine-readable evidence.

The bundled custom Strands `Model` implementation is deterministic and offline. It drives the real agent/tool protocol without an API key, paid inference, or cloud account, so judges can reproduce the full workflow for free. A production deployment can replace it with Amazon Bedrock or another Strands-supported model without changing the safety tools.

We added a standalone incident dashboard, a responsive public demo site, an English captioned 2:04 video, a reproducible video renderer, and a cross-platform test matrix on Linux and Windows.

### Challenges we ran into

The hard problem was not deleting files. It was proving that autonomy stops at the intended boundary. Filesystem paths can escape through symlinks or Windows reparse points, state can change between planning and execution, and file extensions alone do not establish operator intent.

We addressed those failure modes with exact resolved-root checks, explicit marker inheritance, link and reparse refusal, action-time revalidation, a cycle byte budget, and a hash-chained audit log. The demo is synthetic because safety claims are easier to judge when the expected outcome is deterministic and no real user data is at risk.

### Accomplishments that we're proud of

- A working, non-trivial Strands agent completes the whole incident cycle.
- Read-only mode is the default and guarded action mode must be explicit.
- The demo proves both action and refusal: two files are removed and two are preserved.
- Seven focused tests cover policy, boundaries, budgets, links, audit integrity, and tool order on Linux and Windows.
- The public product page, source, architecture, demo, and test evidence require no login or paid service.

### What we learned

Safe autonomy needs observable refusal paths. A system that only shows what it did cannot prove what it would decline to do. Treating the plan, the action-time checks, and the audit stream as separate artifacts made the agent easier to reason about and test.

Strands' custom model interface also made it possible to keep the demo deterministic while preserving a real agent loop. That separates the orchestration and tool-safety work from model-provider choice.

### What's next for QuietGuard

The next version will add native Windows free-space signals, scheduled silent monitoring, operator-approved notification channels, signed policy bundles, and a Bedrock/AgentCore deployment option. A production rollout would begin in read-only mode and learn per-application growth patterns before any directory receives a safety marker.

## Testing instructions

Requirements: Python 3.10 or newer. No credentials, cloud account, or payment method are required.

```text
git clone https://github.com/PionneerZ/quietguard-agent.git
cd quietguard-agent
python -m pip install -e .
quietguard demo
```

The command creates a new synthetic workspace under `artifacts/`, runs one real Strands agent cycle, and prints the result. Open the emitted `evidence/dashboard.html` file to inspect the dashboard. Verify that the two old files below `safe-logs/.quietguard-safe` are removed, while `user-data.sqlite` and the unmarked `outside.log` remain.

Run the complete test suite with:

```text
python -m pytest
```

Expected result: `7 passed`. The same suite runs on Linux and Windows in GitHub Actions.

## Architecture diagram

Use `docs/assets/architecture.png` for upload. The source SVG is `docs/architecture.svg`.

## Gallery assets

1. `docs/assets/dashboard.png` — working incident result and primary cover image.
2. `docs/assets/architecture.png` — Strands agent/tool architecture.
3. `docs/assets/quietguard-demo.mp4` — final 2:04 captioned demonstration and pitch.

## Disclosure

This project was created during the Agents for Humans Hackathon submission period. OpenAI Codex was used as a coding assistant. The product design, safety rules, source code, tests, and demo artifacts in this repository are new work for the hackathon. QuietGuard uses the Strands Agents SDK 1.54.0 and is released under the MIT License.

