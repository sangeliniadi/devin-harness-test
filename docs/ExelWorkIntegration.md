# Exel.Work Integration Requirements

A recommended configuration model for connecting this harness to Exel.Work, based on gaps hit during real testing - not first principles alone.

## Proposed project-level fields

**Fields with direct evidence behind them:**

- **`repository_url`, `jira_project_key`** - the harness has to know which GitHub repo a Jira project maps to; Jira has no native concept of this. `jira_client.py` currently hardcodes one project (`EX`). This field replaces that hardcoding.
- **`default_branch`** - the implement step needs a real, confirmed target branch, not a shared assumption. Currently hardcoded to main in jira_client.py, manually confirmed correct for ganttxbyexelia by checking branch protection directly - nothing confirms that's right for a different project. This field should hold the confirmed value per project going forward.
- **`technical_lead`, `pr_reviewer`** - reviewer identity can't reliably come from Jira per-ticket. Jira Cloud hides assignee/reporter emails by default, and every real ticket fetched this project fell back to a placeholder as a result.
- **`github_token_reference`** - the harness independently verifies CI status against GitHub's real data rather than trusting Devin's claim. Confirmed working - see the readiness assessment below for the one real caveat found.
- **`jira_service_account_permissions_confirmed`** - whatever account the harness runs under should be deliberately checked, so permission gaps aren't missed by accident. On the personal account used throughout, two separate gaps were found this way: a missing write permission (EX-65) and missing read/diagnostic access (EX-42). Testing was also bounded by that one account's access and by the repo mapping covering one project only - anything outside that scope is untested.
- **`devin_credential_reference`** - every session this project ever ran was on a personal API key, not a scoped service account. This is a real, unresolved decision.
- **`deployment_risk_flag`** - if merging to `main` auto-deploys, a human's PR approval and a live production change become the same click, without them necessarily knowing it. Every other conservative commitment (no merge, no Jira writes, no confidence-score reliance) is enforced by the harness itself. Not believed to be an issue for ganttxbyexelia specifically, but this should be checked and confirmed for any future repo or branch before assuming it's safe.
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

In line with the goal of having a clear picture of what happened, the following should be logged as structured, queryable data for every ticket, regardless of outcome:

- Timestamp and ticket ID on every event
- The provisional tier assigned, and which Type/Priority combination produced it
- Every gate result, not just the final outcome
- The harness-computed score and which evidence checks passed or failed
- Every status transition the harness performs, with what triggered it
- Every human review event: who was notified, why, and what they decided
- The final outcome: merged, rejected, escalated, or still pending

**Exel.Work-originated** (no GitHub equivalent): anything from the escalation table above - no natural home elsewhere, since only Exel.Work has the ticket/tier/gate context to raise these meaningfully.

## What stays where and who notifies about what

**Exel.Work owns:** client-facing ticket status (mirroring Jira), project configuration, tier assignment and policy, gate results and the audit trail, escalation routing - since only Exel.Work has the tier and gate context needed to raise escalations meaningfully.

**Jira owns:** ticket lifecycle, Type, Priority, and description, once a ticket reaches the harness. The client authors these in Exel.Work first, at intake - but jira_client.py only ever reads from Jira, so once the harness is involved, Jira is the correctable copy. This avoids a failure already found this project: the Epic.quarter_target bug happened because multiple parts of the codebase each kept their own version of the same field, and they drifted out of sync.

**GitHub owns:** code, PRs, branch protection, CI - and already notifies natively for PR reviews, comments, and CI status; duplicating that through Exel.Work adds nothing.

### What's still missing, not just "future work"

- **No webhook listener.** Every ticket this project ever processed was fetched manually, by running a script. Nothing fires automatically off a real Jira event.
- **No Jira write-back.** The harness cannot update a real ticket's status, even though it can read one.
- **No resume mechanism.** Directly blocks any real Tier 2/3 workflow, since those tiers always require human review, and there's currently no way to continue past that point except by editing code directly, as was done for testing.
- **Credential question unresolved.** Every single session this project ran, without exception, ran on a personal API key, not a properly scoped service account.
- **Tested against exactly one project and one repository.** The repo-mapping mechanism, and whether Devin's repo-targeting actually works reliably on a second repo, are both unconfirmed.
- **No secret-scan validation.** Nothing checks whether Devin's diff accidentally includes a credential or key before a PR opens.
- **No Exel.Work ↔ Jira consistency check.** Not buildable yet regardless, since no real connection between Exel.Work and the harness exists - but worth naming as its own gap, not folded into the webhook item above.
- **Reviewer-readiness genuinely unconfirmed.** Not a code gap - nobody has actually confirmed Technical Leads have the time and context to meaningfully review AI-generated PRs at the pace this would eventually run at.

### Open decisions still unresolved

- **Whether the current stop-and-flag behavior on an ambiguous ticket satisfies "request clarification,"** or something more active (actually notifying a person, not just an internal flag) is wanted.
- **Whether Jira column moves should happen automatically** once a ticket's status changes - currently always manual.
- **Whether the harness should stay a separate service or be embedded into Exel.Work's own backend** - not something this project proposes an answer to. The harness currently depends on several credentials (Devin, Jira, GitHub) managed independently as environment variables, not through Exel.Work.
- **Who formally owns tier policy going forward** - the mapping mechanism works, but nobody has signed off on it as official policy.
  
## Business readiness assessment - is this actually ready to integrate?

**Short answer: not yet. Here's exactly what's built, what's confirmed working, and what's still blocking a real integration.**

### What's genuinely built and working

The core validation logic is solid and repeatedly tested against real tickets: deterministic scoring, the six analysis gates, automatic tier promotion, retry-on-weak-analysis, and hard boundary enforcement. All of these have real evidence behind them. Three real, complete assess → implement → PR cycles were run end to end, all producing genuine, reviewable PRs with no unintended side effects.

### What's confirmed working but only in a sandboxed, manual way

All real implement tests required a **manual bypass of the human checkpoint**, because there's no resume mechanism - a ticket that stops for review has no built way to be told "approved, continue." This was done deliberately, on a test branch, with fake tickets, specifically to prove the mechanism works - not something to rely on for real usage as-is.

**CI verification is now confirmed working**, with one real caveat worth understanding before trusting it in production: it correctly detects a mismatch between Devin's claim and GitHub's real data, but "no CI configured on this branch at all" and "CI ran and genuinely failed" both currently surface the same way - as a mismatch. Before relying on this for a real integration, confirm the actual target branch has CI properly wired up, or this check will correctly-but-unhelpfully block every PR regardless of code quality.

### Extending to other projects

Everything here has been built and tested against exactly one project (EX) and one repository.

**Recommended first-test approach for a new project:** 
1. Add a new entry to PROJECT_REPO_MAP in jira_client.py: "NEWKEY": "Exelia-Technologies/the-repo-name".
2. Review protected_paths in policy.yaml for that repo's actual structure - alembic/versions/ is this repo's own migration tool's folder name, not a generic pattern, so a different stack will have different sensitive paths, and reusing this list unchanged risks leaving them unprotected.
3. Run one real ticket assess-only: python run_ticket_from_jira.py NEWKEY-<ticket>. Confirm targeting actually worked by checking whether affected_files in the result genuinely references the new repo, not ganttxbyexelia.
4. Once confirmed, create a dedicated sandbox branch on the new repo (same pattern as test/DevinTest) before attempting implement mode - never point a first implement attempt at the new project's real main branch.
5. Treat reviewer/escalation emails and tier expectations as unconfirmed for the new project until directly checked.

**Realistic near-term scope:** small, clearly-scoped bugs and copy/UI fixes can already go from ticket to PR untouched. Larger or judgment-heavy work isn't there yet, but the harness still does a useful first pass - affected files, risk flags, open questions - so review isn't starting from zero. That should get faster as more infrastructure gets built and it's tested on more tickets, saving time rather than adding overhead.

### The direct recommendation

This project set out to answer whether Devin could be safely handed real Exel.Work tickets - not whether AI can write code in general, but whether client work specifically could be delegated with confidence. The evidence supports a genuinely positive answer.

The core risk was always that an AI agent's own claims about its work can't be trusted outright, especially on a client's real codebase. confidence_score swinging 17-45 points between two runs of the identical ticket showed exactly why. The harness built around that - replacing self-reported confidence with deterministic checks - held up under repeated real testing: it correctly refused to retry work a retry couldn't fix, correctly declined to promote a ticket when something else was also wrong, and caught a genuine mismatch between Devin's claim and GitHub's actual data rather than trusting the more convenient answer. These are exactly the situations where handing real client work to an AI without this kind of control would go wrong quietly.

What remains is practical: a webhook, Jira write-back, a resume mechanism, a proper service account - not questions of whether the approach works, but what's needed to move from proof of concept to daily use. Worth being direct: this won't clear a backlog on day one. Every real implement test still needed a manual checkpoint bypass, and most real tickets tested needed a person to step in.

Even so, that's not the right measure of its value yet. On tickets it can't fully resolve, it already does the groundwork a developer would otherwise do manually - affected files, real risk flagged, the actual open question surfaced - so review starts from something, not nothing.

The project is worth continuing to invest in. Not because it's finished, but because the part that needed proving first - whether this specific kind of delegation could be made safe - has been.
