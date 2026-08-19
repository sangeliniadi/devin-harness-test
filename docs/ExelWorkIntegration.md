# Exel.Work Integration Requirements

A recommended configuration model for connecting this harness to Exel.Work, based on concrete gaps hit during real testing.

## Proposed project-level fields

**Fields with direct evidence behind them:**

- **`repository_url`, `jira_project_key`** - the harness has to know which GitHub repo a Jira project maps to; Jira has no native concept of this. `jira_client.py` currently hardcodes one project (`EX`). This field replaces that hardcoding.
- **`technical_lead`, `pr_reviewer`** - reviewer identity can't reliably come from Jira per-ticket. Jira Cloud hides assignee/reporter emails by default, and every real ticket fetched this week fell back to a placeholder as a result.
- **`github_token_reference`** - the harness independently verifies CI status against GitHub's real check-run data rather than trusting Devin's claim. That check needs a token configured. This was never actually exercised successfully during real testing — `GITHUB_TOKEN` wasn't set in either real implement run this week, so this capability exists in code but is still unconfirmed against a real PR in practice.
- **`jira_service_account_permissions_confirmed`** - whatever account the harness runs under should be deliberately checked, so permission gaps aren't accidentally missed. On the personal account used throughout this project, two separate permission gaps were found this way: a missing write permission (Transition Issues, EX-65) and missing read/diagnostic access (production logs and DB access, EX-42). Testing was also bounded throughout by this one personal account's access and by the repo mapping covering one project only - any need outside that narrow scope hasn't been tested in either direction.
- **`devin_credential_reference`** - every session this project ever ran, ran on a personal API key, not a scoped service account.
- **`deployment_risk_flag`** - if merging to `main` auto-deploys, a human's PR approval and a live production change become the same click, without them necessarily knowing it. Every other conservative commitment in this project's plan (no merge, no Jira writes, no confidence-score reliance) is enforced by the harness itself - this is the one that isn't; it depends on infrastructure the harness never touches. Unconfirmed whether this repo's target branch actually does this.
- **`devin_quota_alert_contact`, `max_daily_delegated_tickets`** - manual testing has a natural pace; a webhook-triggered production system has none. Even a generous quota can be consumed unattended if nothing is watching.

**Fields that are reasonable proposals:**

- **`repository_provider`** - the harness only assumes GitHub today, untested against anything else.
- **`allowed_target_branches`** - untested; the harness has only ever targeted one branch at a time by convention, not by an enforced allowlist.
- **`safe_delegation_enabled`** - a per-project kill switch, general good practice rather than something a specific gap forced.
- **`qa_owner`, `escalation_owner`** - follow from the escalation model proposed below, not from an external requirement yet.
- **`allowed_tiers`, `protected_paths`** - currently global settings; per-project is a reasonable anticipation of multi-project use, not yet needed by the single-project reality tested.

## Why four separate reviewer-type fields, not one generic "reviewer"

- **`technical_lead`** - Is this the right approach?
- **`pr_reviewer`** - Is this code correct and mergeable?
- **`qa_owner`** - Does this actually work?
- **`escalation_owner`** - Did something try to happen that never should?

A single generic "reviewer" field would force every kind of concern through one person regardless of whether that's who should actually handle it.

## Proposed reviewer and escalation ownership

- **A gate failure needing judgment** (`open_questions`, `self_critique_raised_blockers`, `documentation_drift_found`) → `technical_lead`.
- **A ready-for-review PR** → nobody, via Exel.Work - GitHub already notifies natively; duplicating that adds a channel for the same event.
- **A hard boundary violation** (attempted master merge, protected-path write) → `escalation_owner`, high-severity.
- **A missing permission** → `escalation_owner`.
- **A CI/test failure at PR-readiness** → `qa_owner`.

## Suggested audit trail

Per Exel.Work's own goal of "a very clear picture" of what happened, the following should be logged as structured, queryable data for every ticket, regardless of outcome:

- Timestamp and ticket ID on every event
- The provisional tier assigned, and which Type/Priority combination produced it
- Every gate result, not just the final outcome
- The harness-computed score and which evidence checks passed or failed
- Every status transition the harness performs, with what triggered it
- Every human review event: who was notified, why, and what they decided
- The final outcome: merged, rejected, escalated, or still pending

## Suggested notification rules

**GitHub-native** (no Exel.Work involvement): PR review requests, review comments, CI status. Already handled correctly by GitHub; duplicating adds nothing.

**Exel.Work-originated** (no GitHub equivalent): anything from the escalation table above - no natural home elsewhere, since only Exel.Work has the ticket/tier/gate context to raise these meaningfully.

## What stays where

**Exel.Work owns:** client-facing ticket status (mirroring Jira), project configuration, tier assignment and policy, gate results and the audit trail, escalation routing.

**Jira owns:** ticket lifecycle, Type, Priority, and description, once a ticket reaches the harness. The client authors these in Exel.Work first, at intake — but `jira_client.py` only ever reads from Jira, so once the harness is involved, Jira is the live, correctable copy. This avoids a failure already found this week: the `Epic.quarter_target` bug happened because multiple parts of the codebase each kept their own version of the same field, and they drifted out of sync.

**GitHub owns:** code, PRs, branch protection, CI — and continues notifying natively for PR events.

## Business readiness assessment — is this actually ready to integrate?

**Short answer: not yet. Here's exactly what's built, what's confirmed working, and what's still blocking a real integration.**

### What's genuinely built and working

The core validation logic is solid and repeatedly tested against real tickets: deterministic scoring, the six analysis gates, automatic tier promotion, retry-on-weak-analysis, and hard boundary enforcement. All of these have real evidence behind them, not just design — see the earlier weekly notes for specifics. Two real, complete assess → implement → PR cycles were run end to end, both producing genuine, reviewable PRs with no unintended side effects.

### What's confirmed working but only in a sandboxed, manual way

Both real implement tests required a **manual bypass of the human checkpoint**, because there's no resume mechanism — a ticket that stops for review has no built way to be told "approved, continue." This was done deliberately, on a test branch, with a fake ticket, specifically to prove the mechanism works — not something to rely on for real usage as-is.

### What's still genuinely missing, not just "future work"

- **No webhook listener.** Every ticket this project ever processed was fetched manually, by running a script. Nothing fires automatically off a real Jira event.
- **No Jira write-back.** The harness cannot update a real ticket's status, even though it can read one.
- **No resume mechanism.** Directly blocks any real Tier 2/3 workflow, since those tiers always require human review, and there's currently no way to continue past that point except by editing code directly, as was done for testing.
- **Credential question unresolved.** Every single session this project ran, without exception, ran on a personal API key, not a properly scoped service account.
- **CI verification built but never proven in practice.** The code exists to independently check GitHub's real CI status, but it was never actually exercised successfully — the one required environment variable was never set during either real implement test.
- **Tested against exactly one project and one repository.** The repo-mapping mechanism, and whether Devin's repo-targeting actually works reliably on a second repo, are both unconfirmed.

### Known weaknesses and open concerns, not just gaps

- **The system has no way to distinguish "verify a claimed fix" from "investigate an open bug."** Running a real, already-closed ticket through assessment showed Devin has no way to know a ticket was already marked Done — it investigates it as a live, unresolved problem regardless. A status field now exists and prints a warning, but nothing in the actual gating logic accounts for this distinction.
- **Devin's own self-reported confidence score was shown to be genuinely unstable** — swinging by 17–45 points between separate runs of the identical ticket, which is exactly why gating moved away from it. This instability is a property of the underlying model's self-assessment, not something this harness can fully control for even with the current mitigations.
- **Retry and tier-promotion logic are both deliberately conservative, which has a real cost.** Across every real ticket tested this project, the vast majority failed for reasons the harness correctly judged unfixable by retrying or promoting — meaning most real, messy tickets will still require a human to intervene rather than being cleanly resolved automatically. This is a safety-first design choice, but it means the near-term realistic throughput of fully automated tickets is low.
- **Testing was bounded by one person's access the entire time** — one Jira account, one set of permissions, one repository. Real-world usage at another project or with a different service account's permission set is genuinely untested, not just theoretically likely to work.

### The direct recommendation

The validation and safety logic is sound and well-evidenced enough to build on with confidence. The infrastructure connecting it to a real, automated, multi-ticket workflow — webhook, write-back, resume, and a proper service account — does not exist yet, and is real, non-trivial engineering work, not a polish item. Whoever continues this should treat those four as the actual next milestones, not a checklist to move through quickly.
