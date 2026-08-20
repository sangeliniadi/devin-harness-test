# Real Assessment Reports — Summaries

Condensed summaries of five real assess-only runs against `ganttxbyexelia`. The full, unedited narrative reports these are drawn from are longer and more detailed (exact file/line citations, full reasoning trails) — these summaries capture the key finding from each, not the full investigation. See `docs/SystemOverview.md`, "What the harness actually sees vs. what Devin actually did", for how this compares to what `structured_output` itself captures.

Cited as evidence throughout `docs/SystemOverview.md`, `docs/ExelWorkIntegration.md`, and `docs/KnownFollowUps.md`. All were run assess-only — no code was written or committed for any of these.

| Report | What it demonstrates |
|---|---|
| [EX-42](#ex-42) | Devin has no way to know a ticket is already resolved unless told. |
| [EX-61](#ex-61) | Self-critique surfaced two pre-existing defects a "simple" fix wouldn't touch. |
| [EX-65](#ex-65) | Correctly scoped the request as Jira config, not a code change; caught a missing permission and a production-data risk. |
| [EX-71](#ex-71) | Traced a reported bug to its real root cause, not the ticket's own diagnosis. |
| [EX-87](#ex-87) | Recognized a non-actionable ticket and declined to invent requirements. |

---

<a id="ex-42"></a>
## EX-42 — GANTT-X page renders an error instead of the chart

Traced two possible causes: a chart-render crash from an unparseable `quarter_target` string, or a failed API call. Found the real underlying issue — two different code paths write `quarter_target` in two different formats ("Q1 2026" vs. bare "Q1"), and one rendering path can't handle the second format, crashing the page. Flagged as unverified without seeing the actual error text or production data, and declined to guess which of the two paths caused this specific report. This ticket was later confirmed to already be **Done** in Jira — Devin had no way to know that and investigated it as a live, open defect throughout (direct evidence for the `jira_status` gap in `KnownFollowUps.md`).

---

<a id="ex-61"></a>
## EX-61 — Worklist Epic column shows an internal ID instead of the Jira key

Straightforward root cause: one table cell renders the wrong field (`epic_id`, a database primary key) instead of the one already available on the same row (`epic_key`). A one-line fix. Self-critique caught two things the ticket didn't ask about but the fix would surface: the epic filter dropdown is empty for non-admin users, and the table/filter are fed by two independent data sources (mirrored DB vs. live Jira) that will keep disagreeing after the fix. Both flagged as decisions for a human before proceeding, not silently treated as out of scope.

---

<a id="ex-65"></a>
## EX-65 — Jira should block status transitions when required fields are missing

Investigated the codebase and concluded the actual deliverable isn't a code change at all — it's Jira workflow configuration, since nothing in the repo drives or can veto Jira transitions. Along the way, found the ticket's own premise was wrong (it claimed a "Blocked" field doesn't exist yet; the code shows it already exists as Jira's built-in Flagged field), surfaced a missing service-account permission needed for the work, and flagged a production-data risk — enforcing the rule would strand existing Epics that already have null values for these fields. Recommended against implementation as written, with a clear next step (a human decision, then Jira admin config, not this repo).

---

<a id="ex-71"></a>
## EX-71 — "Don't show this tour again" checkbox request

Ticket asked for a checkbox to stop a tour popup from reappearing. Investigation found the popup reappears because the suppression flag lives in browser `localStorage`, which gets wiped on every logout — so a UI-only checkbox wouldn't actually fix the reported bug on a new device or browser, and fixing the real persistence bug might resolve the complaint without any new UI at all. Flagged that the ticket was likely conflating two separate fixes and needed a decision from the reporter on which was actually wanted, rather than picking one silently.

---

<a id="ex-87"></a>
## EX-87 — Exploratory ticket with no defined ask

Ticket text was a test note ("testing what happens when..."), not a change request — no defect, no expected behaviour, no acceptance criteria. Rather than inventing requirements to fill the gap, Devin traced what the code actually does in that scenario (and found a real, separate bug: three different code paths write the same field in three different formats), then recommended the ticket be sent back and split into three properly-scoped follow-ups instead of proceeding.
