"""
run_implement_manual_override_sandbox2.py — DELIBERATE, ONE-OFF BYPASS of
the human checkpoint for SANDBOX-2, whose assessment has already been
reviewed and is clean (no hard blocks, self_critique_raised_blockers=False,
stopped only on open_questions). Reuses the exact AssessImpactOutput
already returned, so no extra Devin quota is spent re-assessing.

See run_implement_manual_override.py's docstring for the full explanation
of why this exists — same reasoning applies here, on a second ticket.

Usage:
    python run_implement_manual_override_sandbox2.py
"""

import json
import logging

from devin_harness_service import run_implement_step
from models import AssessImpactOutput, Priority, RiskLevel, Tier, TicketContext, TicketType

logging.basicConfig(level=logging.INFO)


def main() -> None:
    ticket = TicketContext(
        jira_ticket_id="SANDBOX-2",
        repo="Exelia-Technologies/ganttxbyexelia",
        target_branch="test/DevinTest",
        reviewer_email="s.angeliniadi@exeliatech.com",
        escalation_contact_email="s.angeliniadi@exeliatech.com",
        ticket_type=TicketType.BUG,
        priority=Priority.LOW,
        risk_level=RiskLevel.LOW,
        tier=Tier.TIER_1,
        acceptance_criteria=(
            'Change the Worklist table\'s Epic column to show the Jira epic '
            'key (e.g. "EX-2") instead of the internal ID label (e.g. "Epic-13")'
        ),
        full_description=None,
        estimate_hours=1.0,
    )

    # Reconstructs the EXACT assess_output already returned.
    assess_output = AssessImpactOutput(
        confidence_score=0.9,
        affected_files=["web/src/components/worklist-table-v2.tsx"],
        affected_scope_description=(
            "Single presentational cell in the Worklist table's Epic column. "
            "The Jira epic key is already available on the same row object "
            "as epic_key and already populated server-side — frontend-only, "
            "one-line display change: render row.original.epic_key, fall "
            "back to '-'. No API, schema, DB, or migration change needed."
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
            "The Epic column currently shows a synthetic label built from "
            "the internal database row id (e.g. 'Epic-13'). Change it to "
            "display the real Jira epic key (e.g. 'EX-2') for each issue, "
            "keeping a placeholder when the issue has no epic."
        ),
        identified_blast_radius=True,
        blast_radius_notes=(
            "Direct edit: the Epic column cell in worklist-table-v2.tsx. "
            "Only consumer of the component is the worklist page. Switching "
            "the display to epic_key makes the column consistent with the "
            "existing filter, which already filters by key. Column widths "
            "are persisted in localStorage keyed by column id — keeping "
            "accessorKey as 'epic_id' (only changing the cell renderer) "
            "avoids resetting users' saved widths. Same 'Epic-<id>' pattern "
            "also exists on the Metrics page — out of scope, flagged as a "
            "natural follow-up."
        ),
        self_critique=(
            "The column id / localStorage coupling is the one real "
            "regression risk — swapping accessorKey would change the "
            "TanStack column id used in the persisted width map, resetting "
            "a returning user's saved Epic-column width. The ticket leaves "
            "open whether the cell should show only the key or key+summary, "
            "and whether it should link to the epic. No existing tests for "
            "either worklist table, so nothing catches a regression "
            "automatically without adding one."
        ),
        self_critique_raised_blockers=False,
        documentation_drift_check_performed=True,
        documentation_drift_found=True,
        documentation_drift_notes=(
            "docs/ExecutiveAnalysis.md and docs/Suggested way forward.md "
            "already document this exact defect and quote the offending "
            "code. The docs recommend 'key + summary,' broader than this "
            "ticket's 'show the epic key' — noted, not treated as a reason "
            "to expand scope."
        ),
        recommended_approach=(
            "Frontend-only, one file. In worklist-table-v2.tsx, change the "
            "Epic column cell to render row.original.epic_key, fall back to "
            "'-'. Keep accessorKey as 'epic_id' to preserve users' saved "
            "column widths. Verify with pnpm type-check and pnpm lint, plus "
            "a manual check that real keys render and no-epic issues still "
            "show '-'. Do not change the API, schemas, or migrations."
        ),
        open_questions=[
            "Key only, or key + epic summary?",
            "Should the Epic cell link to the epic, or stay plain text?",
            "Acceptable to reset users' saved Epic-column width by changing "
            "accessorKey, or should it stay 'epic_id' with only the "
            "renderer changed?",
            "Should raw Jira epic keys be shown to customer-role users, or "
            "routed through the Brand Key alias?",
            "Out of scope but same defect: fix the identical labels on the "
            "metrics page in a follow-up?",
        ],
    )

    print(
        "\n*** MANUAL OVERRIDE: proceeding directly to implement for "
        "SANDBOX-2, bypassing the human checkpoint. This assessment has "
        "already been reviewed — clean pass, stopped only on "
        "open_questions, no hard blocks. ***\n"
    )

    output, validation = run_implement_step(ticket, assess_output)

    print("\n=== Implement Result ===")
    print(json.dumps({
        "implement_output": output.model_dump(),
        "validation": validation.model_dump(),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
