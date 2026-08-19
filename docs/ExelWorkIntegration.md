# Exel.Work Integration Requirements

A recommended configuration model for connecting this harness to Exel.Work, based on concrete gaps hit during real testing - not designed from first principles alone.

## Proposed project-level fields

**Fields with direct evidence behind them:**

- **`repository_url`, `jira_project_key`** - the harness has to know which GitHub repo a Jira project maps to; Jira has no native concept of this. `jira_client.py` currently hardcodes one project (`EX`). This field replaces that hardcoding.
- **`default_branch`** - the implement step needs a real, confirmed target branch, not an assumption. Currently hardcoded to `main` in `jira_client.py`. Confirmed correct for `ganttxbyexelia` by checking branch protection directly, but that confirmation was manual - this field should hold the confirmed value going forward, per project.
- **`technical_lead`, `pr_reviewer`** - reviewer identity can't reliably come from Jira per-ticket. Jira Cloud hides assignee/reporter emails by default, and every real ticket fetched this project fell back to a placeholder as a result.
- **`github_token_reference`** - the harness independently verifies CI status against GitHub's real check-run data rather than trusting Devin's claim. Confirmed working: with a real token configured, a test caught a mismatch between Devin's self-reported status and GitHub's actual data, and correctly blocked on it. The specific mismatch found was mundane (the test branch had no CI configured at all, so GitHub reported "unknown" against Devin's "pending"), not a dramatic caught falsehood - but the mechanism itself is proven, which is the point of this field.
- **`jira_service_account_permissions_confirmed`** - whatever account the harness runs under should be deliberately checked, so permission gaps aren't accidentally missed. On the personal account used throughout this project, two separate permission gaps were found this way: a missing write permission (Transition Issues, EX-65) and missing read/diagnostic access (production logs and DB access, EX-42). Testing was also bounded throughout by this one personal account's access and by the repo mapping covering one project only - any need outside that narrow scope hasn't been tested in either direction.
- **`devin_credential_reference`** - every session this project ever ran was on a personal API key, not a scoped service account. This is a real, unresolved decision, not a minor detail.
- **`deployment_risk_flag`** - if merging to `main` auto-deploys, a human's PR approval and a live production change become the same click, without them necessarily knowing it. Every other conservative commitment in this project's plan (no merge, no Jira writes, no confidence-score reliance) is enforced by the harness itself - this is the one that isn't; it depends on infrastructure the harness never touches. Unconfirmed whether this repo's target branch actually does this.
- **`devin_quota_alert_contact`, `max_daily_delegated_tickets`** - manual testing has a natural pace; a webhook-triggered production system has none. Even a generous quota can be consumed unattended if nothing is watching.

**Fields that are reasonable proposals, not yet backed by a specific finding:**

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

**Jira owns:** ticket lifecycle, Type, Priority, and description, once a ticket reaches the harness. The client authors these in Exel.Work first, at intake - but `jira_client.py` only ever reads from Jira, so once the harness is involved, Jira is the live, correctable copy. This avoids a failure already found this project: the `Epic.quarter_target` bug happened because multiple parts of the codebase each kept their own version of the same field, and they drifted out of sync.

**GitHub owns:** code, PRs, branch protection, CI - and continues notifying natively for PR events.

## Business readiness assessment - is this actually ready to integrate?

**Short answer: not yet. Here's exactly what's built, what's confirmed working, and what's still blocking a real integration.**

### What's genuinely built and working

The core validation logic is solid and repeatedly tested against real tickets: deterministic scoring, the six analysis gates, automatic tier promotion, retry-on-weak-analysis, and hard boundary enforcement. All of these have real evidence behind them.Three real, complete assess → implement → PR cycles were run end to end, all producing genuine, reviewable PRs with no unintended side effects.

### What's confirmed working but only in a sandboxed, manual way

All real implement tests required a **manual bypass of the human checkpoint**, because there's no resume mechanism - a ticket that stops for review has no built way to be told "approved, continue." This was done deliberately, on a test branch, with fake tickets, specifically to prove the mechanism works - not something to rely on for real usage as-is.

**CI verification is now confirmed working**, with one real caveat worth understanding before trusting it in production: it correctly detects a mismatch between Devin's claim and GitHub's real data, but "no CI configured on this branch at all" and "CI ran and genuinely failed" both currently surface the same way - as a mismatch. Before relying on this for a real integration, confirm the actual target branch has CI properly wired up, or this check will correctly-but-unhelpfully block every PR regardless of code quality.

### What's still missing, not just "future work"

- **No webhook listener.** Every ticket this project ever processed was fetched manually, by running a script. Nothing fires automatically off a real Jira event.
- **No Jira write-back.** The harness cannot update a real ticket's status, even though it can read one.
- **No resume mechanism.** Directly blocks any real Tier 2/3 workflow, since those tiers always require human review, and there's currently no way to continue past that point except by editing code directly, as was done for testing.
- **Credential question unresolved.** Every single session this project ran, without exception, ran on a personal API key, not a properly scoped service account.
- **Tested against exactly one project and one repository.** The repo-mapping mechanism, and whether Devin's repo-targeting actually works reliably on a second repo, are both unconfirmed.
- **No secret-scan validation.** Nothing checks whether Devin's diff accidentally includes a credential or key before a PR opens.
- **No Exel.Work ↔ Jira consistency check.** Not buildable yet regardless, since no real connection between Exel.Work and the harness exists - but worth naming as its own gap, not folded into the webhook item above.
- **Reviewer-readiness genuinely unconfirmed.** Not a code gap - nobody has actually confirmed Technical Leads have the time and context to meaningfully review AI-generated PRs at the pace this would eventually run at.

### Open decisions still genuinely unresolved

- **Whether the current stop-and-flag behavior on an ambiguous ticket satisfies "request clarification,"** or something more active (actually notifying a person, not just an internal flag) is wanted.
- **Whether Jira column moves should happen automatically** once a ticket's status changes - currently always manual.
- **Whether the harness should stay a separate service or be embedded into Exel.Work's own backend** - not something this project proposes an answer to. One relevant data point for whoever decides: the harness currently depends on several credentials (Devin, Jira, GitHub) managed independently as environment variables, not through Exel.Work.
- **Who formally owns tier policy going forward** - the mapping mechanism works, but nobody has signed off on it as official policy.

### Known weaknesses and open concerns, not just gaps

- **The system has no way to distinguish "verify a claimed fix" from "investigate an open bug."** Running a real, already-closed ticket through assessment showed Devin has no way to know a ticket was already marked Done - it investigates it as a live, unresolved problem regardless. A status field now exists and prints a warning, but nothing in the actual gating logic accounts for this distinction.
- **Devin's own self-reported confidence score was shown to be genuinely unstable** - swinging by 17–45 points between separate runs of the identical ticket, which is exactly why gating moved away from it. This instability is a property of the underlying model's self-assessment, not something this harness can fully control for even with the current mitigations.
- **Retry and tier-promotion logic are both deliberately conservative, which has a real cost.** Across every real ticket tested this project, the vast majority failed for reasons the harness correctly judged unfixable by retrying or promoting - meaning most real, messy tickets will still require a human to intervene rather than being cleanly resolved automatically. This is a safety-first design choice, but it means the near-term realistic throughput of fully automated tickets is low.
- **Testing was bounded by one person's access the entire time** - one Jira account, one set of permissions, one repository. Real-world usage at another project or with a different service account's permission set is genuinely untested, not just theoretically likely to work.
- **The CI check can't yet distinguish "nothing configured" from "genuinely failed."** See above - worth a real fix before production use, not a blocker for evaluating the harness itself.

### Strategic potential, beyond this specific harness

Worth separating from the readiness question above: even accounting for everything still missing, there's a case for why this is worth continued investment specifically, not just "AI delegation in general."

**The core pattern generalizes beyond Devin.** The actual design principle here - the harness independently deciding whether to trust an AI's output, rather than trusting the AI's own self-reported confidence - isn't tied to Devin specifically. If it holds up under further development, it's a pattern that could reasonably extend to other AI tools the company adopts later, not a one-off integration.

**The audit trail has value independent of how much gets automated.** Being able to see exactly why a given change passed or got flagged - which evidence checks failed, what triggered human review - is a real asset for accountability on its own, separate from raw ticket throughput.

**Realistic near-term scope:** small, clearly-scoped bugs and copy/UI fixes can already go from ticket to PR with no human touching the code. Larger or judgment-heavy work isn't there yet, but the harness already does a real, useful first pass on those too - identifying affected files, flagging risk, surfacing the actual open questions - so a human reviewing it isn't starting from zero. That review step should get faster and more efficient as more infrastructure gets built and it's tested against more tickets - the goal being genuine time saved for the team, not additional review overhead.

### The direct recommendation

This project is worth continuing to invest in. The most uncertain part of this problem was not the infrastructure but whether an AI's own judgment about its own work could be trusted, which has been genuinely proven: deterministic scoring, six analysis gates, tier promotion, retry logic, and independent CI verification, all repeatedly tested against real tickets with real evidence behind each one.

What's left for implementation - a webhook, Jira write-back, a resume mechanism, and a proper service account - will strengthen the case for whether the harness is a viable solution for automating ticket-to-PR workflows. This project will, no doubt, require further strengthening, but a solid case can be made for which requests are suitable for Devin, how to classify them, what Devin should report before any code is written, where the technical lead should approve, reject, or ask for clarification, and what safeguards are needed to ensure that Devin, alongside a harness, can be trusted to make changes to the codebase.