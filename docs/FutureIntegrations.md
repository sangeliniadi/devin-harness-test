# Devin Platform Features - Possible Future Integrations

Not implemented. This is a note for whoever picks up this project after my internship - none of this has been built or approved, and I'd recommend not building any of it until the current harness (deterministic scoring, gates, tier promotion, retry logic) has been tested end-to-end and signed off. These are genuine capabilities Devin already provides that the harness doesn't currently use, worth considering once the core system is proven.

## 1. Knowledge - lowest effort, no code required

Devin's persistent, auto-recalled project memory (`app.devin.ai/settings/knowledge`), the rough equivalent of a `CLAUDE.md` file. Nothing the harness builds today feeds into this - every session starts from a blank slate and has to rediscover things this project already found the hard way.

**What it would fix:** real, already-known landmines in `ganttxbyexelia` - the three inconsistent `Epic.quarter_target` formats (dashboard creation, ETL sync, Jira webhook), the stale customfield IDs in `docs/JiraConfiguration.md`, and doc files describing already-shipped work as still pending. None of this is captured anywhere Devin automatically recalls it.

**How to implement:** create Knowledge entries pinned specifically to `ganttxbyexelia` (not org-wide), one per known issue, each with a tight, specific trigger description so it only surfaces when actually relevant. Pure web-app configuration, no harness code touched.

**Why the harness's own prompts should stay out of Knowledge:** Knowledge is explicitly non-deterministic by design - Devin decides when it's relevant and recalls it selectively. The seven evidence questions and the six-gate sequence need to run identically every time, which is the opposite of what Knowledge is built for. Keep those hardcoded in the prompt as they are now.

## 2. Skills - low effort, one repo commit

Repo-committed, auto-discovered procedure files (`.agents/skills/<name>/SKILL.md`), version-controlled alongside the code.

**What it would fix:** `tests_passing` is currently only as reliable as however Devin happens to test before claiming success - Gate 6 verifies the result against real GitHub check-run data, but nothing standardizes the testing process itself beforehand.

**How to implement:** commit `.agents/skills/test-before-pr/SKILL.md` to `ganttxbyexelia`, with the actual concrete steps this repo needs - `pytest api/tests`, `pnpm test`/`lint`/`type-check`, based on commands already referenced in this week's real Devin assessments. No harness code changes needed; Devin auto-discovers it.

**Secondary use:** a natural home for the still-unbuilt secret-scan mandatory item - a Skill instructing Devin to run a scanner (e.g. `gitleaks`) before opening any PR.

## 3. Playbooks - small code change, plus web-app setup

Reusable, attachable prompt templates with built-in metrics (session count, merge rate).

**What it would fix:** the README's own flagged gap - "No Session Insights monitoring... as a signal the eligibility bar is wrong." Playbooks track merge rate per attached playbook automatically, which is a direct, free answer to that gap.

**How to implement:** create two Playbooks in the web app (one for assess, one for implement), each with a Forbidden Actions section mirroring `policy.yaml`'s `hard_boundaries` (no direct master merge, no writes to protected paths) as a second, defense-in-depth layer - not a replacement for `enforce_hard_boundaries()`, which must remain the real, audited enforcement. Then wire them in: `devin_client.py`'s `create_scoped_session()` already accepts a `playbook_id` parameter that nothing currently passes - update the call sites in `run_assess_step()` and `run_implement_step()` to pass the new Playbook IDs.

## 4. Automations - implementable for one specific, narrow use only

Trigger-based automatic session execution (Slack, GitHub, Linear, schedule, or webhook events → a Devin action).

**Important limitation, not a minor caveat:** Automations' "Start session" action fires a raw Devin session directly off a trigger, with no way to route through the harness's own `evaluate_gates()` or `validate_assess_step()` first. **Do not use this to replace the planned Jira webhook listener** - wiring Jira directly into an Automation would let a ticket bypass the harness's gating entirely, which defeats the actual purpose of this whole project. The harness's own Python code must remain the thing Jira's webhook reaches first.

**What it can safely fix instead:** the resume-mechanism gap flagged as a real blocker in [`ExelWorkIntegration.md`](ExelWorkIntegration.md) - this only matters *after* the harness has already validated a ticket and a human is reviewing it, so nothing about the gating logic is bypassed at this stage.

**How to implement:** an Automation triggered by a Slack reaction or a Jira status change, using the "Message session" action type, targeting the specific paused session ID, sending an explicit "approved, proceed" message. Directly closes a real, already-identified gap.

## 5. Session Insights - nothing to build, just start using it

Automatic per-session analysis (issues encountered, ACU usage, session size classification), already running for free on every session today - no setup required.

**Why it's directly relevant:** `devin_client.py`'s own `DevinSessionError` message already anticipated wanting this signal - "repeated timeouts on a tier suggest the eligibility bar is wrong" is close to exactly what Session Insights' Session Size classification (flagging L/XL sessions as unhealthy) already tracks automatically. The only action item is making a habit of checking it after real runs.

## 6. MCP integration - not independently actionable, only relevant to the existing auth-path proposal

Confirms Devin supports custom per-session MCP tools - this was previously flagged as unconfirmed in the GitNexus investigation, specifically for the proposed independent auth-path check (cross-checking Devin's `touches_auth_or_security` self-report against a real call-graph fact). This documentation resolves that specific unknown, but doesn't change anything on its own - it's still a separate, smaller, not-yet-built feature.

## 7. Secrets - checked, correctly not applicable

Devin's Secrets system is for credentials Devin needs during a session (e.g. logging into a staging site). The harness's own credentials (`DEVIN_API_KEY`, `JIRA_API_TOKEN`, `GITHUB_TOKEN`) are what the harness uses to talk to Devin/Jira/GitHub - a different category of problem, correctly out of scope for this feature.

## Suggested order, if picked up later

Knowledge first (zero risk, no code, immediate value) → Skills (one commit) → Playbooks (small code change) → Automations' resume mechanism (closes a real standing gap, but only after the core gating logic is fully trusted) → MCP/auth-path check (already a separate, lower-priority item on its own).
