# Devin Harness - Exel.Work Delegation System

A control layer that sits between Exel.Work tickets and Devin, deciding when Devin is allowed to proceed rather than trusting Devin's own judgment about its own work. Built as a proof-of-concept; this document reflects the system's actual, current state.

## What this does today

The harness sits between a ticket and Devin's own output, independently validating each step with deterministic checks rather than trusting Devin's self-reported confidence - replacing a self-rated score with seven concrete evidence questions, six named analysis gates, automatic tier-based strictness, a guarded retry on a weak first pass, and independent CI verification against GitHub's real check-run data.

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
| `run_implement_manual_override.py`, `run_implement_manual_override_sandbox2.py` |	Testing-only scripts that bypass the human checkpoint on an already-reviewed assessment, used since no resume mechanism exists yet — see docs/SystemOverview.md for exactly how and why. |

## What this deliberately does not do yet

- **No Jira write-back.** Reads tickets, never writes status changes or comments back.
- **No webhook trigger.** Everything is run by hand; nothing fires automatically off a real Jira event.
- **No resume mechanism.** A ticket that stops for human checkpoint review has no built way to be told "approved, continue."
- **No Exel.Work connection of any kind.** See `docs/ExelWorkIntegration.md` for what this would require.
- **Not tested on any project besides `EX`.** The repo mapping only has one entry.
- **Real end-to-end (assess → implement → PR) has been tested three times**, all on a sandboxed test branch, all requiring a manual checkpoint bypass since no resume mechanism exists. CI verification is now confirmed working — see `docs/ExelWorkIntegration.md` for the one real caveat found.

Full list of smaller known gaps: **[`docs/KnownFollowUps.md`](docs/KnownFollowUps.md)**.

## Setup and running it

```bash
git clone https://github.com/Exelia-Technologies/devin-harness-test.git
cd devin-harness-test
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows (PowerShell: venv\Scripts\Activate.ps1)
pip install -r requirements.txt
```
Then set the required environment variables (only last for the current terminal session):

```bash
export DEVIN_API_KEY=your_key_here
export JIRA_BASE_URL=https://your-instance.atlassian.net
export JIRA_EMAIL=you@example.com
export JIRA_API_TOKEN=your_jira_token
export GITHUB_TOKEN=your_github_token   # optional — enables real CI verification; without it, falls back to trusting Devin's self-reported status
```

Then run a real ticket, assess-only by default:

```bash
python run_ticket_from_jira.py EX-55
```

Or build a hypothetical/manual ticket instead, no real Jira ticket needed:

```bash
python run_ticket_interactive.py
```

Add `--implement` only against a repo/branch you're fully comfortable with Devin actually committing to — this is a real, visible action, not a dry run, and the script asks for explicit confirmation before proceeding.

**Troubleshooting:** `... is not set` means an environment variable didn't actually take in this terminal session (check with `echo $DEVIN_API_KEY`). `ModuleNotFoundError` usually means you're not in the venv — check for `(venv)` in your prompt. A long hang is normal for real Devin sessions, which are asynchronous; a 30-minute timeout is itself useful signal a ticket may be mis-scoped for its tier.

## Documentation

- **[`docs/SystemOverview.md`](docs/SystemOverview.md)** - how each mechanism actually works, in full detail.
- **[`docs/ExelWorkIntegration.md`](docs/ExelWorkIntegration.md)** - proposed Exel.Work configuration model, what's confirmed working, what's still blocking a real integration and a business readiness assessment with a final recommendation.
- **[`docs/KnownFollowUps.md`](docs/KnownFollowUps.md)** - smaller known code gaps, documented rather than built.
- **[`docs/FutureIntegrations.md`](docs/FutureIntegrations.md)** - Devin platform capabilities not yet used (Automations, Session Insights, Knowledge, Skills, Playbooks), with recommendations for whoever continues this project.
