# Devin Platform Features - Possible Future Integrations

Not implemented, or approved. Two of these are genuinely worth pursuing; the rest are either already largely covered by existing checks or not worth the effort on their own.

## Worth actually building

### 1. Automations - closes a real, already-confirmed blocker

A way to have an external event (Eg. a Jira status change) automatically message a running Devin session. Every real implement test so far needed a manual, hand-written script to bypass the missing resume mechanism - this closes that exact gap.

**Important limitation:** the "Start session" action fires a raw Devin session directly off a trigger, with no way to route it through the harness's own validation checks first. Never use this to replace the planned Jira webhook listener - that would let a ticket bypass the harness's gating entirely, which defeats the whole point of this project.

**How to implement:** an Automation triggered by a Jira status change, using the "Message session" action, targeting the paused session's ID, sending an explicit "approved, proceed" message. This only matters *after* the harness has already validated a ticket and a human is reviewing it, so nothing about the gating logic gets bypassed at this stage.

### 2. Session Insights - already running, free, just start using it

Automatic per-session analysis Devin already generates - how long a session ran, what it cost, what problems it hit, and whether the session's size suggests something was harder than expected. Already active today, nothing to build. `devin_client.py`'s own error-handling code already anticipated wanting exactly this signal ("repeated timeouts on a tier suggest the eligibility bar is wrong"). The only real action item is making a habit of checking it after real runs - not something to build, but to remember to look at.

## Smaller wins, largely already covered by existing checks

**Knowledge** - Devin's persistent, auto-recalled project memory, the rough equivalent of a standing reference doc Devin checks automatically rather than something typed fresh each session. Real value, but the harness's documentation-reconciliation check - the step in the assess process that compares what the docs say against what the code actually does, and flags when they disagree - already proved, through real testing, that it can independently rediscover things like the `Epic.quarter_target` inconsistency through genuine investigation. Knowledge would save Devin from redoing work it already does correctly, not close a trust gap that's currently open.

**Skills** - a written, step-by-step procedure checked directly into the repo, which Devin automatically follows for a recurring task like running tests before opening a PR. Similarly modest in value here: the harness's PR-readiness check - the step that independently asks GitHub for a PR's real, actual test results rather than trusting Devin's own claim - already closes the real trust gap around whether tests genuinely passed. A Skill standardizing Devin's own testing process wouldn't add trust, just catch a broken test run slightly earlier, before a PR opens rather than after.

## Not recommended

**Playbooks** - a reusable, attachable prompt template with built-in usage metrics. Its two stated benefits both largely duplicate things already covered elsewhere: the merge-rate tracking overlaps with Session Insights above, and its "forbidden actions" guardrail is explicitly not a replacement for the harness's own hard-boundary enforcement (the code-level check that blocks a direct merge to the main branch or a write to a protected file), which already exists and is already the real, audited enforcement. This one requires an actual code change for a benefit that's mostly already covered.

**MCP integration** - confirmed that Devin supports custom per-session external tool connections, but this only matters if a separate, already-deprioritized idea (an independent check on whether a change touches auth-related code, cross-referencing a real call-graph tool) gets picked up later. Not independently actionable on its own.

**Secrets** - Devin's system for giving itself credentials it needs *during* a session (Eg. logging into a staging environment). Checked and correctly not applicable - the harness's own credentials are a different category of problem, used by the harness to talk to Devin/Jira/GitHub, not something Devin itself needs mid-session.

## Suggested order, if picked up later

Automations' resume mechanism first (closes a real, confirmed gap) → start checking Session Insights (already free, nothing to build) → Knowledge and Skills only if there's clear appetite for smaller efficiency work → Playbooks and MCP not recommended as-is.
