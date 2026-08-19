"""
run_ticket.py — run the harness against a ticket defined in a JSON file,
instead of hardcoding a TicketContext into a Python script each time.

Usage:
    python run_ticket.py tickets/ex-65.json
    python run_ticket.py tickets/ex-65.json --implement

By default this ONLY runs assess-only mode — safe to point at a real repo,
nothing gets written or committed. The --implement flag is required to run
the full harness (assess -> implement -> open PR). This is a deliberate
safety default, not an oversight: don't pass --implement unless you're
fully comfortable with Devin actually committing to the ticket's repo/branch.

To test a new ticket: copy tickets/_template.json, fill it in, run it. No
Python editing required.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from devin_harness_service import run_assess_only, run_harness
from models import TicketContext

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_ticket")


def load_ticket(path: Path) -> TicketContext:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return TicketContext.model_validate(data)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Devin harness against a ticket defined in a JSON file."
    )
    parser.add_argument(
        "ticket_file",
        type=Path,
        help="Path to a ticket JSON file, e.g. tickets/ex-65.json",
    )
    parser.add_argument(
        "--implement",
        action="store_true",
        help=(
            "Run the FULL harness (assess -> implement -> open PR), not just "
            "assess-only. Only use this against a repo/branch you're fully "
            "comfortable with Devin actually committing to."
        ),
    )
    args = parser.parse_args()

    if not args.ticket_file.exists():
        print(f"Ticket file not found: {args.ticket_file}", file=sys.stderr)
        sys.exit(1)

    try:
        ticket = load_ticket(args.ticket_file)
    except Exception as e:  # noqa: BLE001 — surface any schema/JSON error clearly to the user
        print(f"Failed to load {args.ticket_file}: {e}", file=sys.stderr)
        sys.exit(1)

    if args.implement:
        logger.info("Running FULL harness (assess -> implement -> PR) for %s", ticket.jira_ticket_id)
        result = run_harness(ticket)
    else:
        logger.info("Running ASSESS-ONLY for %s", ticket.jira_ticket_id)
        result = run_assess_only(ticket)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
