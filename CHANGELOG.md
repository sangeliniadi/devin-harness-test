# Changelog

All notable changes to the Devin harness, in the order they were actually built. No formal versioning was used for this internship project — entries are grouped by when the work happened.

## Final week — polish and documentation

### Changed
- README fully rewritten to reflect the system's actual current state, replacing the original Stage 1 proof-of-concept description.
- Detailed feature breakdown moved out of the README into `docs/SystemOverview.md`, keeping the README to a short orientation per standard practice.

### Added
- `docs/ExelWorkIntegration.md` — proposed Exel.Work configuration model plus a direct business-readiness assessment.
- `docs/KnownFollowUps.md` — smaller known code gaps, documented rather than built, per direction to focus on documentation this week.
- `jira_status` field on ticket context, with a warning when a ticket already marked Done/Closed is fetched — found after running a real, closed ticket (EX-42) through assessment and discovering Devin had no way to know it was already resolved.

### Fixed
- Session error handling: a Devin timeout, or a session marked "expired" without reporting completion, is now caught and returned as a clean, labeled failure instead of crashing the script or risking incomplete data being trusted as real.

### Tested
- First two real, complete assess → implement → PR runs, both on a sandboxed test branch. Both required a manual checkpoint bypass, since no resume mechanism exists yet.
- Real GitHub PR review process confirmed working end to end for the first time.

## Retry / iteration logic

### Added
- Retry-on-weak-first-pass: if assessment fails purely on thoroughness (not fully reading a file, not grounding the analysis), the harness can ask Devin to redo specifically those parts once. Only fires when every failing field is genuinely fixable by retrying; any other kind of failure (untestable criteria, a missing permission, a hard block) blocks the retry entirely.
- Automated content-genuineness check on a successful retry: compares the retried output against the original to catch a retry that "passed" by superficially flipping flags rather than doing real additional work. Only forces human review when the check finds the content suspiciously unchanged — a genuinely improved retry proceeds normally rather than being penalized just for having retried.

### Changed
- Replaced an earlier, blunter version of this same safeguard (which forced human review on every successful retry, regardless of quality) with the content-check version above, since the blunt version defeated the point of automatic proceeding for Tier 1 tickets that genuinely improved on retry.

## Tier promotion

### Added
- Automatic tier promotion: a ticket that fails only because it exceeds its tier's file-count ceiling, or is blocked by a sensitive-data flag at a tier that doesn't allow it, is automatically re-checked against the next tier's stricter rules instead of failing outright. Only fires when every failure reason is one a higher tier genuinely resolves — a mixed failure (promotable and non-promotable reasons together) never promotes, since promoting wouldn't fix the other problem and would hide it behind an apparent resolution. Human review is always forced afterward regardless of outcome.

## Analysis gates and deterministic scoring

### Added
- Six named analysis gates evaluated within the assess step: initial understanding, code-grounded analysis, blast-radius, documentation reconciliation, critical self-review, testability. A gate failure is traceable to the specific step that failed.
- Deterministic scoring: Devin's self-rated confidence score replaced, for gating purposes, with seven concrete yes/no evidence questions the harness itself scores. Devin's own confidence score is retained for logging only, after being shown to swing 17–45 points between separate runs of the identical ticket while the computed score stayed stable.
- Mandatory evidence fields per tier — a field failing here blocks the ticket regardless of the aggregate score, so a strong score elsewhere can't average away a real gap.
- Fairness derivations (`documentation_checked_if_exists`, `tests_identified_if_applicable`) so a ticket with genuinely no relevant docs or no applicable tests isn't penalized for correctly reporting that.
- `open_questions` non-empty now forces human review regardless of tier, closing a gap where a Tier 1 ticket with genuine unresolved questions could otherwise auto-continue.

### Fixed
- Removed a duplicate testability check that was reporting the same underlying failure twice (once from an older standalone check, once from the new testability gate).

### Investigated
- GitNexus tested as a possible independent blast-radius verification tool against five real tickets — one agreement out of five, not adopted for that purpose. One narrower, confirmed-useful finding (reliably tracing a function's call path into auth-related code) noted as a possible small, separate addition later, not built.

## Exel.Work integration requirements

### Added
- Proposed Exel.Work project-level configuration fields, reviewer/escalation ownership model, audit trail specification, and notification rules, based on concrete gaps hit during real testing (Jira hiding reviewer emails by default, the repo mapping being hardcoded, a missing Jira permission found only by testing).

## Initial harness

### Added
- Core harness loop: fetch a ticket, call Devin for assessment, validate the response, conditionally proceed.
- Real Jira ticket fetching (read-only).
- Real GitHub CI status verification, independent of Devin's own self-reported status.
- Hard boundaries enforced in code, not just as a prompt instruction: no direct master merge, no writes to protected paths.
- Type + Priority → provisional tier mapping.
