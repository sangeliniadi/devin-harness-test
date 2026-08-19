"""
run_ticket_interactive.py — build a ticket by answering prompts in the
terminal, instead of writing a JSON file or editing Python.

This is also the first place the Type + Priority -> tier mapping (proposed
in the status report, implemented in tier_mapping.py) actually runs,
rather than tier being typed in by hand.

Usage:
    $env:DEVIN_API_KEY = "your_key_here"   (PowerShell)
    python run_ticket_interactive.py

Defaults to assess-only. You'll be asked explicitly, with a confirmation
step, before it's allowed to run the full implement loop against a real
repo.
"""

from __future__ import annotations

import json
import logging

from devin_harness_service import run_assess_only, run_harness
from models import Priority, TicketContext, TicketType
from tier_mapping import assign_provisional_tier, risk_level_for_tier

logging.basicConfig(level=logging.INFO)


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val or (default or "")


def ask_choice(prompt: str, choices: list[str]) -> str:
    choices_str = "/".join(choices)
    while True:
        val = input(f"{prompt} ({choices_str}): ").strip().lower()
        if val in choices:
            return val
        print(f"  Please enter one of: {choices_str}")


def ask_multiline(prompt: str) -> str:
    print(f"{prompt} (paste the full text, then an empty line to finish):")
    lines: list[str] = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)
    return "\n".join(lines)


def ask_float(prompt: str, default: float) -> float:
    val = ask(prompt, default=str(default))
    try:
        return float(val)
    except ValueError:
        print(f"  Not a number, using default {default}")
        return default


def main() -> None:
    print("=== New ticket for the Devin harness ===\n")

    jira_ticket_id = ask("Jira ticket ID (e.g. EX-70)")
    repo = ask("Repo", default="Exelia-Technologies/ganttxbyexelia")
    target_branch = ask("Target branch", default="main")
    reviewer_email = ask("Reviewer email")
    escalation_contact_email = ask("Escalation contact email")

    print()
    ticket_type_str = ask_choice("Type", ["bug", "task", "story"])
    priority_str = ask_choice("Priority", ["low", "medium", "high"])
    ticket_type = TicketType(ticket_type_str)
    priority = Priority(priority_str)

    tier = assign_provisional_tier(ticket_type, priority)
    print(
        f"\n-> Provisional tier assigned: Tier {tier.value} "
        f"(from Type={ticket_type_str}, Priority={priority_str}). "
        f"This can only be escalated by Devin's own assessment, never relaxed.\n"
    )

    acceptance_criteria = ask("Acceptance criteria (short summary)")
    full_description = ask_multiline("Full ticket description")
    estimate_hours = ask_float("Estimate in hours (max 3)", default=1.0)

    ticket = TicketContext(
        jira_ticket_id=jira_ticket_id,
        repo=repo,
        target_branch=target_branch,
        reviewer_email=reviewer_email,
        escalation_contact_email=escalation_contact_email,
        ticket_type=ticket_type,
        priority=priority,
        risk_level=risk_level_for_tier(tier),
        tier=tier,
        acceptance_criteria=acceptance_criteria,
        full_description=full_description or None,
        estimate_hours=estimate_hours,
    )

    print()
    mode = ask_choice("Run mode", ["assess", "implement"])

    if mode == "implement":
        confirm = ask_choice(
            f"This will let Devin actually write code and open a PR against "
            f"{repo}. Continue",
            ["yes", "no"],
        )
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
