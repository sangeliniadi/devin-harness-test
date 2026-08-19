"""
run_example.py — Stage 1 smoke test: ASSESS-ONLY, no implementation.

Usage:
    $env:DEVIN_API_KEY = "your_key_here"   (PowerShell)
    python run_example.py

IMPORTANT: this calls run_assess_only(), not run_harness(). That means it
only asks Devin to assess a ticket and report back — it will NOT write
code, commit anything, or open a pull request, regardless of what tier is
set below. This is deliberate: safe to point at a real company repo for
exploration, without risking any real change to it.

Once you're ready to test the full loop (assess -> implement -> PR), swap
run_assess_only(ticket) for run_harness(ticket) below — but only do that
against a repo/branch you're fully comfortable with Devin actually
committing to.

NOTE: this now includes full_description, the complete verbatim ticket
text — not just acceptance_criteria. This was added after EX-65 revealed
that acceptance_criteria alone was too trimmed for Devin to see the real
required-fields list, which only existed in the full ticket body.
"""

import json
import logging

from devin_harness_service import run_assess_only
from models import RiskLevel, Tier, TicketContext

logging.basicConfig(level=logging.INFO)


def main() -> None:
    ticket = TicketContext(
        jira_ticket_id="EX-65",
        repo="Exelia-Technologies/ganttxbyexelia",
        target_branch="main",  # confirm the right branch to reference — do not assume
        reviewer_email="team-lead@example.com",  # replace with the real reviewer
        escalation_contact_email="pm@example.com",  # replace with the real escalation contact
        risk_level=RiskLevel.LOW,
        tier=Tier.TIER_1,
        acceptance_criteria=(
            "If a user attempts to move an Epic or Ticket to another status while "
            "one or more required fields are unmet, the transition must be blocked "
            "with a clear validation message. Once all required fields are set, "
            "the transition should proceed normally."
        ),
        full_description=(
            "Extend validation rules to prevent status movement when required "
            "fields are missing.\n\n"
            "As an extension to EX-63 (Add validation to prevent 'Blocked' items "
            "from moving to other statuses), we need to apply additional "
            "validation rules, in JIRA, to prevent items (Epics and Tickets) from "
            "moving to another status when certain mandatory fields are not set. "
            "These validations should block the transition and provide a clear "
            "error message to the user.\n\n"
            "Required Validation Rules\n\n"
            "For Epics — reject movement if ANY of the following are missing:\n"
            "1. Objective Year - not set.\n"
            "2. Quarter Target - not set.\n"
            "3. Blocked field - if enabled (field does not currently exist; only "
            "Blocker Reason exists).\n\n"
            "For Tickets — reject movement if:\n"
            "1. Blocked field - enabled.\n\n"
            "Expected Behavior:\n"
            "- If a user attempts to move an Epic or Ticket to another status "
            "while one or more of the above conditions are unmet, the transition "
            "must be blocked.\n"
            "- The system should show a clear validation message explaining "
            "which field(s) still need to be completed.\n"
            "- Once all required fields are set correctly, the transition should "
            "proceed normally."
        ),
        estimate_hours=1.0,
    )

    result = run_assess_only(ticket)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
