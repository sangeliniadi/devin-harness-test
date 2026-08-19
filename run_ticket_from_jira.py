"""
run_ticket_from_jira.py — fetch a real Jira ticket by ID, no manual entry.

Usage:
    $env:DEVIN_API_KEY = "your_key_here"       (PowerShell)
    $env:JIRA_BASE_URL = "https://exelia.atlassian.net"
    $env:JIRA_EMAIL = "you@exelia.com"
    $env:JIRA_API_TOKEN = "your_jira_token"
    python run_ticket_from_jira.py EX-55
    python run_ticket_from_jira.py EX-55 --implement

Fetches summary, description, type, priority, and estimate straight from
Jira. Tier is computed automatically from type + priority (tier_mapping.py).
Defaults to assess-only — --implement requires explicit confirmation.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from devin_harness_service import run_assess_only, run_harness
from jira_client import JiraFetchError, build_ticket_context_from_jira

logging.basicConfig(level=logging.INFO)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Devin harness against a live Jira ticket.")
    parser.add_argument("ticket_id", help="Jira ticket ID, e.g. EX-55")
    parser.add_argument(
        "--implement",
        action="store_true",
        help="Run the FULL harness (assess -> implement -> PR), not just assess-only.",
    )
    args = parser.parse_args()

    print(f"Fetching {args.ticket_id} from Jira...")
    try:
        ticket = build_ticket_context_from_jira(args.ticket_id)
    except JiraFetchError as e:
        print(f"Failed to fetch ticket: {e}", file=sys.stderr)
        sys.exit(1)

    print(
        f"\nFetched {ticket.jira_ticket_id} — Type={ticket.ticket_type.value}, "
        f"Priority={ticket.priority.value} -> Tier {ticket.tier.value}\n"
    )
    print(f"Summary: {ticket.acceptance_criteria}")
    print(f"Estimate: {ticket.estimate_hours}h\n")

    if args.implement:
        confirm = input(
            f"This will let Devin actually write code and open a PR against "
            f"{ticket.repo}. Continue (yes/no): "
        ).strip().lower()
        if confirm != "yes":
            print("Cancelled — nothing was run.")
            return
        result = run_harness(ticket)
    else:
        result = run_assess_only(ticket)

    print("\n=== Result ===")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
