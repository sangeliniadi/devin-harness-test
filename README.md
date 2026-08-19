# Devin Harness - Exel.Work Delegation System

A control layer that sits between Exel.Work tickets and Devin, deciding when Devin is allowed to proceed rather than trusting Devin's own judgment about its own work. Built over two weeks as an internship proof-of-concept; this document reflects the system's actual, current state.

## What this does today

A ticket goes through up to two checkpoints: **assess** (Devin investigates and reports back, writes no code) and **implement** (Devin writes code and opens a PR). The harness independently validates Devin's output at each step using deterministic checks, not Devin's own self-reported confidence - replacing a self-rated score with seven concrete evidence questions, six named analysis gates, automatic tier-based strictness (with a safe, narrow promotion mechanism), a guarded retry on a weak first pass, and independent CI verification against GitHub's real check-run data.

See **[`docs/SystemOverview.md`](docs/SystemOverview.md)** for the full detail on how each of these actually works.

## Files

| File | Role |
|---|---|
| `devin_client.py` | Single scoped call to Devin's real API - one call in, one structured result out. Doesn't decide whether to call again. |
| `devin_harness_service.py` | The actual harness - the loop, all validation logic, gates, tiering, retry, session-error handling. |
| `models.py` | Structured-output contracts Devin's responses are validated against at each checkpoint. |
| `policy.yaml` | Per-tier strictness - score thresholds, mandatory evidence fields, file ceilings, human-review requirements. |
| `jira_client.py` | Fetches a real ticket from Jira (read-only) and builds a ticket object from it. |
| `github_client.py` | Independently verifies a PR's real CI status via GitHub's API. |
| `tier_mapping.py` | Type + Priority → provisional tier. |
| `run_ticket_from_jira.py` | Primary way to run a real ticket - `python run_ticket_from_jira.py EX-55`. |
| `run_ticket_interactive.py` | Build a ticket by answering prompts - used for hypothetical or test tickets. |
| `run_ticket.py` | JSON-file-based ticket runner, superseded by the two above. |
| `test_retry.py` | Local, quota-free tests proving the retry decision logic is correct. |

## What this deliberately does not do yet

- **No Jira write-back.** Reads tickets, never writes status changes or comments back.
- **No webhook trigger.** Everything is run by hand; nothing fires automatically off a real Jira event.
- **No resume mechanism.** A ticket that stops for human checkpoint review has no built way to be told "approved, continue."
- **No Exel.Work connection of any kind.** See `docs/ExelWorkIntegration.md` for what this would require.
- **Not tested on any project besides `EX`.** The repo mapping only has one entry.
- **Real end-to-end (assess → implement → PR) has been tested exactly twice**, both on a sandboxed test branch, both requiring a manual checkpoint bypass since no resume mechanism exists.

Full list of smaller known gaps: **[`docs/KnownFollowUps.md`](docs/KnownFollowUps.md)**.

## Running it

```bash
pip install -r requirements.txt
export DEVIN_API_KEY=your_key_here
export JIRA_BASE_URL=https://your-instance.atlassian.net
export JIRA_EMAIL=you@example.com
export JIRA_API_TOKEN=your_jira_token
python run_ticket_from_jira.py EX-55
```

Assess-only by default - add `--implement` only against a repo/branch you're fully comfortable with Devin actually committing to; the script asks for explicit confirmation before doing so.

## Documentation

- **[`docs/SystemOverview.md`](docs/SystemOverview.md)** - how each mechanism actually works, in full detail.
- **[`docs/ExelWorkIntegration.md`](docs/ExelWorkIntegration.md)** - proposed Exel.Work configuration model and a plain readiness assessment: what's confirmed working, and what's still blocking a real integration.
- **[`docs/KnownFollowUps.md`](docs/KnownFollowUps.md)** - smaller known code gaps, documented honestly rather than built.
- **[`docs/FutureIntegrations.md`](docs/FutureIntegrations.md)** - genuine Devin platform capabilities not yet used (Knowledge, Skills, Playbooks, Automations), with concrete recommendations for whoever continues this - none of it built or approved yet.
