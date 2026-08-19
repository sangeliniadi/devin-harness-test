"""
jira_client.py — fetch a real Jira ticket and build a TicketContext from it.

This is mandatory item #2 from the status report: "ticket data is
currently typed in by hand for testing. Needs a real API call to pull the
full ticket." This module is that call — read-only, fetch only. It does
NOT write anything back to Jira (that's item #3, still separate, still
not built, and deliberately so — the harness owns writes, this file only
reads).

Auth: expects JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN in the
environment. Generate a token at https://id.atlassian.com/manage-profile/security/api-tokens.
Jira Cloud uses HTTP Basic auth with email + API token (not a bearer token).

Honest gaps, flagged rather than silently guessed around:
- repo/target_branch aren't Jira fields at all — mapped via a small static
  PROJECT_REPO_MAP below, since Jira has no concept of a GitHub repo.
- reviewer/escalation emails depend on Jira exposing email addresses on
  assignee/reporter, which Jira Cloud often hides by default for privacy.
  Falls back to a placeholder and prints a warning rather than guessing.
- "Original estimate" data quality is questionable — EX-55/EX-65 showed
  values like "2m" and "0m" in the UI, which look like placeholder data,
  not real estimates. Falls back to 1.0h with a warning if missing or zero.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import requests

from models import Priority, RiskLevel, TicketContext, TicketType
from tier_mapping import assign_provisional_tier, risk_level_for_tier

# Map Jira project key -> GitHub repo. Extend as more projects come online.
PROJECT_REPO_MAP: dict[str, str] = {
    "EX": "Exelia-Technologies/ganttxbyexelia",
}
DEFAULT_TARGET_BRANCH = "main"

# Jira's issue type / priority names -> our enums. Extend if Jira's exact
# labels differ from what's assumed here — confirm against a real ticket.
ISSUE_TYPE_MAP: dict[str, TicketType] = {
    "bug": TicketType.BUG,
    "task": TicketType.TASK,
    "story": TicketType.STORY,
}
PRIORITY_MAP: dict[str, Priority] = {
    "highest": Priority.HIGH,
    "high": Priority.HIGH,
    "medium": Priority.MEDIUM,
    "low": Priority.LOW,
    "lowest": Priority.LOW,
}


class JiraFetchError(RuntimeError):
    """Raised when a Jira ticket can't be fetched or is missing required fields."""


def _auth() -> tuple[str, str]:
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    if not email or not token:
        raise JiraFetchError("JIRA_EMAIL and JIRA_API_TOKEN must both be set in the environment.")
    return (email, token)


def _base_url() -> str:
    base = os.environ.get("JIRA_BASE_URL")
    if not base:
        raise JiraFetchError("JIRA_BASE_URL is not set (e.g. https://exelia.atlassian.net).")
    return base.rstrip("/")


def _adf_to_text(node: Any) -> str:
    """
    Minimal Atlassian Document Format -> plain text converter. Jira Cloud's
    v3 API returns descriptions as ADF (a nested JSON doc), not plain
    strings. Covers paragraphs, text, lists, and hard breaks — enough for
    a ticket description, not a full ADF implementation.
    """
    if node is None:
        return ""
    if isinstance(node, str):
        return node

    node_type = node.get("type")
    content = node.get("content", [])

    if node_type == "text":
        return node.get("text", "")
    if node_type == "hardBreak":
        return "\n"

    parts = [_adf_to_text(child) for child in content]

    if node_type == "paragraph":
        return "".join(parts) + "\n"
    if node_type in ("bulletList", "orderedList"):
        return "".join(parts)
    if node_type == "listItem":
        return "- " + "".join(parts).strip() + "\n"
    if node_type == "doc":
        return "".join(parts)

    return "".join(parts)


def fetch_raw_ticket(ticket_id: str) -> dict[str, Any]:
    url = f"{_base_url()}/rest/api/3/issue/{ticket_id}"
    resp = requests.get(url, auth=_auth(), headers={"Accept": "application/json"})
    if resp.status_code == 404:
        raise JiraFetchError(f"Ticket {ticket_id} not found.")
    if resp.status_code in (401, 403):
        raise JiraFetchError(
            f"Auth failed fetching {ticket_id} ({resp.status_code}). "
            f"Check JIRA_EMAIL/JIRA_API_TOKEN."
        )
    resp.raise_for_status()
    return resp.json()


def build_ticket_context_from_jira(
    ticket_id: str,
    *,
    reviewer_email: Optional[str] = None,
    escalation_contact_email: Optional[str] = None,
) -> TicketContext:
    """
    Fetch a real ticket and build a TicketContext from it. reviewer_email
    and escalation_contact_email can be overridden explicitly; otherwise
    this tries assignee/reporter email, falling back to a placeholder with
    a printed warning if Jira doesn't expose one.
    """
    raw = fetch_raw_ticket(ticket_id)
    fields = raw["fields"]

    project_key = raw["key"].split("-")[0]
    repo = PROJECT_REPO_MAP.get(project_key)
    if repo is None:
        raise JiraFetchError(
            f"No repo mapping for project '{project_key}'. Add it to "
            f"PROJECT_REPO_MAP in jira_client.py."
        )

    summary = fields.get("summary", "")
    full_description = _adf_to_text(fields.get("description")).strip() or summary

    issue_type_name = (fields.get("issuetype", {}) or {}).get("name", "").lower()
    ticket_type = ISSUE_TYPE_MAP.get(issue_type_name)
    if ticket_type is None:
        raise JiraFetchError(
            f"Unrecognized issue type '{issue_type_name}' for {ticket_id}. "
            f"Add it to ISSUE_TYPE_MAP in jira_client.py."
        )

    priority_name = (fields.get("priority", {}) or {}).get("name", "").lower()
    priority = PRIORITY_MAP.get(priority_name, Priority.MEDIUM)
    if priority_name not in PRIORITY_MAP:
        print(f"  Warning: unrecognized priority '{priority_name}', defaulting to medium.")

    tier = assign_provisional_tier(ticket_type, priority)

    # Status — informational, not currently gated on anywhere. Recorded
    # specifically because manually running a real, closed ticket through
    # assess (EX-42) showed Devin has no way to know a ticket was already
    # resolved unless this is explicitly surfaced — it investigated a
    # "Done" ticket as if it were a live, open bug. In the fully-built
    # webhook-driven flow this should rarely come up (new tickets enter
    # the pipeline right when created, not after), but reopened tickets
    # and manual testing (like this) can still hit it, so it's worth a
    # visible warning here rather than a silent gap.
    status_name = (fields.get("status", {}) or {}).get("name")
    CLOSED_STATUSES = {"done", "closed", "resolved"}
    if status_name and status_name.lower() in CLOSED_STATUSES:
        print(
            f"  Warning: {ticket_id} is already marked '{status_name}' in Jira. "
            f"Devin will still assess it as if it were an open, unresolved "
            f"ticket — nothing currently tells it otherwise. If you're expecting "
            f"'already fixed, nothing to do,' that's not a mode this harness "
            f"currently distinguishes from a genuine open bug."
        )

    # Reviewer/escalation: Jira Cloud often hides emailAddress by default
    # (GDPR privacy setting) — accountId is reliably present, email is not.
    if reviewer_email is None:
        assignee = fields.get("assignee") or {}
        reviewer_email = assignee.get("emailAddress")
        if not reviewer_email:
            print(
                "  Warning: Jira didn't expose an assignee email (privacy setting). "
                "Pass reviewer_email explicitly or fill it in manually."
            )
            reviewer_email = "team-lead@example.com"

    if escalation_contact_email is None:
        reporter = fields.get("reporter") or {}
        escalation_contact_email = reporter.get("emailAddress")
        if not escalation_contact_email:
            print(
                "  Warning: Jira didn't expose a reporter email (privacy setting). "
                "Pass escalation_contact_email explicitly or fill it in manually."
            )
            escalation_contact_email = "pm@example.com"

    # Original estimate — data quality here is questionable (EX-55/EX-65
    # showed values like "2m"/"0m" in the UI, and even a raw fetch can
    # return small-but-nonzero values like ~108s that are clearly
    # placeholder data, not real estimates). Anything under 15 minutes is
    # treated as unusable rather than taken at face value.
    MIN_PLAUSIBLE_ESTIMATE_SECONDS = 15 * 60
    estimate_seconds = (fields.get("timetracking", {}) or {}).get("originalEstimateSeconds")
    if estimate_seconds and estimate_seconds >= MIN_PLAUSIBLE_ESTIMATE_SECONDS:
        estimate_hours = min(round(estimate_seconds / 3600, 2), 3.0)
    else:
        print(
            f"  Warning: no usable original estimate on {ticket_id} "
            f"(got {estimate_seconds!r}s, treating anything under 15min as "
            f"placeholder data) — defaulting to 1.0h. Verify manually."
        )
        estimate_hours = 1.0

    return TicketContext(
        jira_ticket_id=raw["key"],
        repo=repo,
        target_branch=DEFAULT_TARGET_BRANCH,
        reviewer_email=reviewer_email,
        escalation_contact_email=escalation_contact_email,
        ticket_type=ticket_type,
        priority=priority,
        risk_level=RiskLevel(risk_level_for_tier(tier)),
        tier=tier,
        acceptance_criteria=summary,
        jira_status=status_name,
        full_description=full_description,
        estimate_hours=estimate_hours,
    )