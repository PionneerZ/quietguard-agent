# QuietGuard demo pitch

Target length: 2 minutes 4 seconds. Camera and cloud credentials are not required.

1. **Promise** — Disk pressure, handled quietly.
2. **Problem** — Diagnostic log storms grow in the background. Manual cleanup arrives late; broad cleanup scripts put user data at risk.
3. **Audience** — Solo professionals and small teams that run data-heavy desktop tools without a full operations staff.
4. **Architecture** — A real Strands Agent chooses four tools: scan, plan, guarded action, and evidence publication.
5. **Working demo** — The synthetic incident contains two old, explicitly allowlisted log files, an unmarked log, and a SQLite database.
6. **Result** — QuietGuard detects 2.9 MB of growth, reclaims exactly 3.0 MB, preserves the database and unmarked log, and escalates one decision.
7. **Safety** — Exact root boundary, explicit marker, extension and age checks, symlink/reparse refusal, byte budget, read-only default, and a hash-chained audit log.
8. **Impact** — Known noise is handled automatically; uncertain evidence reaches a human with context.

## Devpost description draft

QuietGuard is a safety-first autonomous disk-pressure agent for professionals and small teams. It detects runaway diagnostic logs before they consume a workstation, builds a bounded cleanup plan, automatically handles only explicitly allowlisted regenerable files, and surfaces uncertain items for a human decision.

The implementation uses a real `strands.Agent` loop with four custom tools. The included offline custom model provider makes the demo deterministic, private, and free to run; any Strands-supported model provider can replace it without changing the filesystem guardrails. Every action is revalidated at execution time and recorded in a tamper-evident audit chain. The contained demo proves the end-to-end behavior without touching user files.

Built during the Agents for Humans Hackathon. OpenAI Codex was used as a coding assistant. All QuietGuard product code, safety rules, tests, visual assets, and demo materials are new work for this event.

