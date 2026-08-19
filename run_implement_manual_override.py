"""
run_implement_manual_override.py — DELIBERATE, ONE-OFF BYPASS of the human
checkpoint, for a single ticket you have ALREADY reviewed and are
comfortable proceeding on. This does NOT modify devin_harness_service.py
or change normal behavior in any way — it's a standalone script that
calls run_implement_step() directly, using the exact AssessImpactOutput
already returned from a real assess run (SANDBOX-1), so no extra Devin
quota is spent re-running the assessment.

This exists ONLY because there's no resume mechanism built yet (a known,
already-flagged gap). Do not use this as a normal way to proceed past a
checkpoint — it's a manual substitute for that missing piece, used here
once, deliberately, on a ticket whose assessment you've already read and
judged safe to proceed on.

Usage:
    python run_implement_manual_override.py
"""

import json
import logging

from devin_harness_service import run_implement_step
from models import AssessImpactOutput, Priority, RiskLevel, Tier, TicketContext, TicketType

logging.basicConfig(level=logging.INFO)


def main() -> None:
    # Reconstructs the exact ticket you already entered interactively.
    ticket = TicketContext(
        jira_ticket_id="SANDBOX-1",
        repo="Exelia-Technologies/ganttxbyexelia",
        target_branch="test/DevinTest",
        reviewer_email="s.angeliniadi@exeliatech.com",
        escalation_contact_email="s.angeliniadi@exeliatech.com",
        ticket_type=TicketType.BUG,
        priority=Priority.LOW,
        risk_level=RiskLevel.LOW,
        tier=Tier.TIER_1,
        acceptance_criteria='Fix "Help & tour" button label to "Help & Tour" (capital T)',
        full_description=(
            "The button currently displays 'Help & tour'. Update the label to "
            "'Help & Tour' (capital T) wherever it appears — the home page, "
            "the worklist page, and the GANTT-X page."
        ),
        estimate_hours=0.5,
    )

    # Reconstructs the EXACT assess_output already returned from the real
    # run — not re-generated, so this doesn't spend a second round of
    # Devin quota just to get back to where you already are.
    assess_output = AssessImpactOutput(
        confidence_score=0.93,
        affected_files=[
            "web/src/app/page.tsx",
            "web/src/app/projects/[key]/worklist/page.tsx",
            "web/src/app/projects/[key]/ganttx/page.tsx",
        ],
        affected_scope_description=(
            "Four hardcoded JSX text literals 'Help & tour' on Buttons that call "
            "handleStartHomeTour / handleStartWorklistTour / handleStartGanttTour: "
            "page.tsx:292, worklist/page.tsx:285 and :291, ganttx/page.tsx:205."
        ),
        touches_customer_data=False,
        touches_auth_or_security=False,
        touches_production_config=False,
        is_single_focused_change=True,
        has_testable_success_criteria=True,
        has_sufficient_context=True,
        required_permissions=[],
        read_relevant_documentation=True,
        relevant_documentation_exists=True,
        read_impacted_files_fully=True,
        identified_affected_files=True,
        analysis_is_code_grounded=True,
        identified_required_tests=True,
        tests_applicable=True,
        checked_protected_areas=True,
        initial_understanding=(
            "Purely cosmetic UI copy fix: the guided-tour trigger button currently "
            "reads 'Help & tour' and should read 'Help & Tour' with a capital T, on "
            "every page where it is rendered."
        ),
        identified_blast_radius=True,
        blast_radius_notes=(
            "Grepped the whole repo for the label — only the 4 JSX literals plus "
            "tour machinery match. Nothing depends on the label text: tour "
            "targeting uses data-tour attributes, completion state uses "
            "localStorage keys, handlers are bound by onClick, not text."
        ),
        self_critique=(
            "Highest real risk is incompleteness, not breakage: worklist/page.tsx "
            "renders the button twice in mutually exclusive role branches (admin "
            "vs everyone else) — a partial fix could leave one role's button "
            "unchanged. The label is HTML-entity encoded ('&amp;'), so a careless "
            "find/replace could introduce a lint regression."
        ),
        self_critique_raised_blockers=False,
        documentation_drift_check_performed=True,
        documentation_drift_found=True,
        documentation_drift_notes=(
            "docs/FrontendGuidelines.md claims an i18n layer and Storybook "
            "coverage that doesn't exist in the code — stale documentation, "
            "unrelated to whether this specific fix is safe to proceed with."
        ),
        recommended_approach=(
            "Single-commit copy change: replace 'Help & tour' with 'Help & Tour' "
            "at page.tsx:292, worklist/page.tsx:285 and :291, ganttx/page.tsx:205 "
            "— 4 edits, 3 files, no logic touched. Keep the & entity. Verify with "
            "pnpm lint/type-check/test."
        ),
        open_questions=[
            "No documented capitalization convention exists — is this a one-off "
            "or the start of a title-case standard?",
            "worklist/page.tsx renders the button twice (role-gated) — confirming "
            "both must change.",
        ],
    )

    print(
        "\n*** MANUAL OVERRIDE: proceeding directly to implement for "
        "SANDBOX-1, bypassing the human checkpoint. This assessment has "
        "already been reviewed. ***\n"
    )

    output, validation = run_implement_step(ticket, assess_output)

    print("\n=== Implement Result ===")
    print(json.dumps({
        "implement_output": output.model_dump(),
        "validation": validation.model_dump(),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
