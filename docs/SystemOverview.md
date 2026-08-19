# System Overview — How the Harness Actually Works

A ticket goes through up to two checkpoints: **assess** (Devin investigates and reports back, writes no code) and **implement** (Devin writes code and opens a PR). The harness independently validates Devin's output at each step using deterministic checks — not Devin's own self-reported confidence.

## Deterministic scoring

Devin no longer self-rates its own confidence for gating purposes. It answers seven concrete yes/no evidence questions (did it read the impacted files fully, is the analysis grounded in real code, did it check protected areas, etc.), and the harness computes the actual score from those answers. Devin's own `confidence_score` is still reported, but only for logging — proven unstable across reruns of the same ticket (17–45 point swings), while the harness-computed score stayed consistent.

## Six analysis gates

Run within the assess step: initial understanding, code-grounded analysis, blast-radius, documentation reconciliation, critical self-review, and testability. A gate failure is traceable to the specific step that failed, not a flat list of reasons.

## Tiering

Every ticket gets an automatic starting tier from its Type + Priority (never set by the client directly). Tier determines how strict validation is — file-count ceilings, which evidence fields are mandatory, whether human checkpoint review is required on every step. The tier is provisional and can only be pushed stricter by Devin's own findings, never relaxed.

## Automatic tier promotion

If a ticket fails only because it's larger than its tier allows — nothing else wrong — the harness automatically re-checks it against the next tier's (stricter) rules instead of just failing it. Only fires when every failure reason is one a higher tier genuinely resolves; any other kind of failure blocks promotion entirely, so a real problem can't be masked behind an apparent fix. Human review is always forced afterward regardless.

## Retry on a weak first pass

If assessment fails purely on thoroughness — Devin didn't fully read a file, didn't ground its analysis — the harness can ask it to redo specifically those parts once, rather than failing outright. Only fires when every failing field is genuinely fixable by trying again; anything else (untestable criteria, a missing permission, a hard block) blocks the retry entirely, since a second attempt can't fix those. A successful retry is checked for genuinely different content before being trusted — a "pass" with suspiciously identical output to the first attempt forces human review instead.

## Real CI verification

Devin's own claim that tests passed is no longer trusted directly — the harness independently asks GitHub for the PR's actual check-run results. A mismatch is a hard failure regardless of which claim sounds better; if verification can't run at all (no token configured), that fallback is explicitly recorded, not silently assumed.

## Session failure handling

A Devin timeout, or a session marked "expired" without reporting completion, is caught and returned as a clean, labeled failure — not a crash, and not silently trusted as real data.

## Hard boundaries

Never tier-dependent: no direct master merge, no writes to protected paths (CI/CD config, secrets, migrations). Enforced in code, not just as a prompt instruction.
