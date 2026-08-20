# System Overview - How the Harness Actually Works

A ticket goes through up to two checkpoints: **assess** (Devin investigates and reports back, writes no code) and **implement** (Devin writes code and opens a PR). The harness independently validates Devin's output at each step using deterministic checks - not Devin's own self-reported confidence.

## The proposed workflow, end to end

```
Ticket → automatic tier classification (Type + Priority)
        ↓
Assess step: Devin investigates, writes no code
        ↓
Six analysis gates evaluated + deterministic score computed
        ↓
   Passed cleanly?  ──No──→  Retry once, only if every failure reason
        │                    is genuinely fixable by trying again
        │                         │
        │                    Still fails / not retryable
        │                         ↓
       Yes                   Ticket stops, scoping report returned,
        │                    escalated for human input
        ↓
   Tier requires review, or Devin flagged open questions, self-critique concerns, or documentation drift?  ──Yes──→  Stops for human checkpoint
        │
        No
        ↓
Implement step: Devin writes code, opens a PR (never merges)
        ↓
Hard boundaries checked - violation is an immediate, non-negotiable stop
        ↓
Real GitHub CI status independently verified against Devin's own claim
        ↓
Human reviews and merges the PR (always required)
```

## Deterministic scoring

Devin no longer self-rates its own confidence for gating purposes. It answers seven concrete yes/no evidence questions (did it read the impacted files fully, is the analysis grounded in real code, did it check protected areas, etc.), and the harness computes the actual score from those answers. Devin's own `confidence_score` is still reported, but only for logging - proven unstable across reruns of the same ticket (17–45 point swings), while the harness-computed score stayed consistent.

## What the harness actually sees vs. what Devin actually did

Every result the harness returns comes only from structured_output (AssessImpactOutput/ImplementOutput, models.py). What Devin actually produces is a much richer narrative report - confirmed against real runs (EX-42, EX-61, EX-65, EX-71, EX-87): grounded findings with exact file/line citations, blast radius, adversarial self-critique, a testability verdict, documentation-vs-code drift naming exact doc lines, and a closing recommendation.

The harness result is a **deliberately lossy compression**, not an index into the full report. To see the actual investigation, you need the session itself - the harness has no persisted link back to it (see `docs/KnownFollowUps.md`). Five real full reports are kept as source material in [`docs/examples.md`](./examples.md).

## What's self-reported vs. independently verified

Not every check in the harness is the same kind of guarantee, and it's worth noting rather than letting "the harness checks it" imply more than it does. Most checks validate what Devin *says* about itself - real, code-level, unbypassable by anything in Devin's phrasing, and no longer subject to Devin grading its own confidence - but still ultimately trusting Devin's own report of what it did. A much smaller number check against a fact the harness maintains completely independently of Devin.

| Check | Basis |
|---|---|
| Deterministic score, mandatory evidence fields, all six analysis gates | Devin's self-report (now structured yes/no evidence instead of a confidence number, but still Devin's own account of what it did) |
| Touches customer data / auth / production config | Devin's self-report |
| File count under tier ceiling | Devin's self-report (its own file list) |
| No direct master merge, no writes to protected paths | Devin's self-report (`attempted_master_merge`, `files_changed`), checked in code against a static list |
| Required permissions are ones the service account actually has | Devin self-reports what it thinks it needs; compared against `granted_permissions` in `policy.yaml` - an externally-maintained fact, not something Devin can be right or wrong about on its own |
| PR CI status | GitHub's real check-run data, when a token is configured and a PR exists - otherwise falls back to Devin's self-report, and that fallback is explicitly recorded via `ci_verification_source` |
| Branch protection on `main` | Independent of Devin entirely - GitHub's own ruleset, enforced by GitHub itself at merge time, not by the harness |
| Jira `Transition Issues` permission | Independent of Devin entirely - simply not granted; a transition call would fail outright regardless of anything the harness concludes |

The takeaway for anyone extending this: only CI verification, branch protection, and the Jira permission check don't depend on Devin accurately reporting on itself. Everything else - including every evidence field, every gate, and the deterministic score built from them - is a real, enforced rule that Devin cannot talk its way past with better phrasing, but it is still checking Devin's word, not an independent fact. Moving more checks from the left column to the right (Eg. a real secret scan on the diff) is the direction that actually closes the remaining trust gap, not just adding more self-report fields.

## Six analysis gates

Run within the assess step: initial understanding, code-grounded analysis, blast-radius, documentation reconciliation, critical self-review, and testability. A gate failure is traceable to the specific step that failed, not a flat list of reasons.

**In practice:** EX-64 passed every gate cleanly, and the gates caught real things, not just formal boxes - documentation reconciliation traced the bug back to a design doc that contained the buggy code as a worked example, and self-critique explicitly declined a scope expansion beyond what the ticket asked for. EX-87 passed four gates with real depth before correctly stopping at testability, showing the sequence evaluates each gate independently rather than short-circuiting.

## Tiering - intake classification

Every ticket gets an automatic starting tier (1, 2, or 3) from its Type + Priority (never set by the client directly, via `tier_mapping.py`). Tier determines how strict validation is - file-count ceilings, which evidence fields are mandatory, whether human checkpoint review is required on every step. The mapping is deliberately asymmetric: a bug's risk comes from what it touches, not urgency, so priority barely moves it, except a high-priority bug often signals an active incident, which tends to be rushed and under-specified. A task carries more inherent ambiguity than a bug, so urgency compounds risk. A story needs product judgment regardless of urgency, so Type alone floors it at Tier 2. The tier is provisional and can only be pushed stricter by Devin's own findings, never relaxed.

Concretely: Tier 1 (Low) - minimum score 0.6, a smaller set of mandatory evidence fields, capped at 3 affected files, no checkpoint-level review required. Tier 2 (Medium) - minimum score 0.75, more fields mandatory, capped at 10 files, human reviews every checkpoint. Tier 3 (High) - minimum score 0.9, all seven evidence fields mandatory, uncapped files, always human-reviewed, and may stay fully human-managed rather than entering the harness at all.

### Why the mandatory fields differ by tier

The asymmetry in `policy.yaml`'s `mandatory_evidence_fields` is deliberate, not visible from the YAML alone:

- `checked_protected_areas`, `documentation_checked_if_exists`, `identified_affected_files`, `analysis_is_code_grounded`, `tests_identified_if_applicable` - mandatory at **every** tier. Even a trivial fix needs to name its file and be grounded in real code.
- `has_testable_success_criteria` - mandatory from Tier 2 up. Tier 1 still counts it toward the aggregate score, just doesn't hard-block on it alone.
- `read_impacted_files_fully` - mandatory **only** at Tier 3. Unlike the two "fairness fields" below, there's no legitimate "not applicable" case here, so keeping it tier-scaled is proportional scrutiny, not a gap.

`documentation_checked_if_exists` and `tests_identified_if_applicable` are derived fields (`(not X_exists) or read/identified_X`, see `compute_deterministic_score()`), not raw Devin answers - they exist so a ticket isn't penalized for correctly reporting that documentation or tests don't apply. `tests_identified_if_applicable` was added specifically to mirror that pattern, rather than making `identified_required_tests` mandatory everywhere and risking the same false-penalty problem.

## Automatic tier promotion

If a ticket fails only because it's larger than its tier allows - nothing else wrong - the harness automatically re-checks it against the next tier's (stricter) rules instead of just failing it. Only fires when every failure reason is one a higher tier genuinely resolves; any other kind of failure blocks promotion entirely, so a real problem can't be masked behind an apparent fix. Human review is always forced afterward regardless.

## Retry on a weak first pass

If assessment fails purely on thoroughness - Devin didn't fully read a file, didn't ground its analysis - the harness can ask it to redo specifically those parts once, rather than failing outright. Only fires when every failing field is genuinely fixable by trying again; anything else (untestable criteria, a missing permission, a hard block) blocks the retry entirely, since a second attempt can't fix those. A successful retry is checked for genuinely different content before being trusted - a "pass" with suspiciously identical output to the first attempt forces human review instead.

**Real example:** EX-87 was typed Bug/Medium, mapping to Tier 1. Devin's investigation found the change spanned more files than Tier 1's 3-file ceiling allows. Before this feature existed, that just dead-ended the ticket - a human had to notice the failure, realize the initial tier guess was wrong, and manually re-triage it. Now the harness re-checks automatically against Tier 2 and passes under the stricter rules, with human review still forced.

**Tested independently of Devin:** ran validate_assess_step() against two constructed cases. A clean ticket with only a file-count breach correctly promoted from Tier 1 to Tier 2 and passed under the stricter rules, with human review forced. The same breach alongside an unrelated problem (untestable criteria) correctly stayed at Tier 1 and failed, exactly as before - confirming a mixed failure never promotes.

## Real CI verification

Devin's own claim that tests passed is no longer trusted directly - the harness independently asks GitHub for the PR's actual check-run results. A mismatch is a hard failure regardless of which claim sounds better; if verification can't run at all (no token configured), that fallback is explicitly recorded, not silently assumed.

## Session failure handling

A Devin timeout, or a session marked "expired" without reporting completion, is caught and returned as a clean, labeled failure - not a crash, and not silently trusted as real data.

## Hard boundaries

Never tier-dependent: no direct master merge, no writes to protected paths (CI/CD config, secrets, migrations). Enforced in code, not just as a prompt instruction.

## Manual checkpoint override - how real implement testing was actually done

Since no resume mechanism exists yet, a ticket that stops for human checkpoint review has no built way to be told "approved, continue." To actually test the implement step, two standalone scripts (run_implement_manual_override.py, run_implement_manual_override_sandbox2.py) were used - not a feature of the harness itself, a testing workaround.

Each script reconstructs the exact ticket and the exact AssessImpactOutput already returned from a real, already-reviewed assess run, then calls run_implement_step() directly - skipping past the requires_human_review check in run_harness() that would otherwise stop it. No new assess call happens and no extra Devin quota is spent re-assessing; only the implement step itself runs for real.

This was deliberately used only on assessments that had already passed cleanly on their own merits (no hard blocks, no unresolved concerns beyond open questions worth a second look), on a sandboxed test branch, with fake tickets - a one-off, manual substitute for the missing resume mechanism, not a pattern meant to be reused casually. See docs/KnownFollowUps.md for the note on generalizing this into a proper reusable tool if this pattern is used going forward.
