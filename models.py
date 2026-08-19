"""
models.py — Structured-output contracts for the Devin harness.

These are the schemas the harness validates Devin's responses against at
each checkpoint. This is "Supporting" per the doc's own table: it defines
*what* the harness checks, while devin_harness_service.py defines the loop
that does the checking.

Each step in the harness (assess -> implement -> open PR) has its own
expected response shape. Devin is told about this shape via
`structured_output_schema` when the session is created (see devin_client.py),
and Devin is expected to keep `structured_output` updated as it works.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Tier(int, Enum):
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


class TicketType(str, Enum):
    """Matches the Type field on Exel.Work's ticket intake form."""
    BUG = "bug"
    TASK = "task"
    STORY = "story"


class Priority(str, Enum):
    """Matches the Priority field on Exel.Work's ticket intake form."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TicketContext(BaseModel):
    """
    Minimum data contract for a ticket before it can enter the harness at
    all. This is the "pre-flight gate" from the doc's final table — it runs
    once, before the loop, not per-checkpoint.
    """

    jira_ticket_id: str
    repo: str
    target_branch: str
    reviewer_email: str
    escalation_contact_email: str
    ticket_type: TicketType
    priority: Priority
    risk_level: RiskLevel
    tier: Tier
    acceptance_criteria: str
    jira_status: Optional[str] = Field(
        default=None,
        description=(
            "The ticket's real Jira status at fetch time (e.g. 'Done', 'In "
            "Progress'), if known. None for manually-built tickets (interactive "
            "mode) with no real Jira ticket behind them. This is informational "
            "only — nothing currently gates on it — but it's worth recording, "
            "since running a real, closed ticket through assess (EX-42, run "
            "manually while testing) showed Devin has no way to know a ticket "
            "was already marked Done unless this is explicitly passed to it, "
            "and investigated it as an open, unresolved bug as a result."
        ),
    )
    full_description: Optional[str] = Field(
        default=None,
        description=(
            "The complete ticket description/body, verbatim from Jira, including "
            "any itemized rules, conditions, or field lists. If omitted, the "
            "harness falls back to acceptance_criteria alone, which risks Devin "
            "assessing an incomplete picture of the ticket (confirmed on EX-65, "
            "where the required-fields list only existed in full_description, "
            "not in the short acceptance_criteria summary)."
        ),
    )
    estimate_hours: float = Field(le=3.0, description="Must be <=3h or split into sub-tickets")


# ---------------------------------------------------------------------------
# Step 1: Assess impact
# ---------------------------------------------------------------------------

class AssessImpactOutput(BaseModel):
    """Expected structured_output shape for the 'assess impact' checkpoint."""

    confidence_score: float = Field(
        ge=0.0, le=1.0,
        description=(
            "Devin's own self-assigned confidence. INFORMATIONAL ONLY — "
            "per direct guidance, the harness does not gate on this number. "
            "LLMs tend to sound confident regardless of actual grounding; "
            "the harness computes its own score from the evidence fields "
            "below instead. Kept here for logging/comparison, not decisions."
        ),
    )
    affected_files: list[str]
    affected_scope_description: str
    touches_customer_data: bool
    touches_auth_or_security: bool
    touches_production_config: bool
    is_single_focused_change: bool
    has_testable_success_criteria: bool = Field(
        description=(
            "Whether the ticket's acceptance criteria has a measurable, checkable "
            "definition of done. False caught EX-55 (\"simplify text\" — no "
            "baseline, no measurable target). This also serves as evidence "
            "question 7 in the deterministic scoring model."
        )
    )
    has_sufficient_context: bool = Field(
        description=(
            "Whether Devin had enough relevant code patterns/docs to work from, "
            "vs. having to guess. From Devin's own 'Evaluating Tasks' eligibility "
            "criteria (Step 1 of the delegation policy)."
        )
    )
    required_permissions: list[str] = Field(
        default_factory=list,
        description=(
            "Any permission this change would need beyond what's already granted "
            "(e.g. 'jira_transition_issue'). Empty list means no new permission "
            "needed. Caught EX-65 (needed Transition Issues, didn't have it)."
        ),
    )

    # --- Evidence fields for deterministic scoring (evidence questions 1-6; ---
    # --- question 7 is has_testable_success_criteria above) ---
    # These replace trusting Devin's own confidence_score. Devin answers each
    # as a concrete yes/no about an action it actually took, rather than a
    # subjective probability — harder to be vague or lazy about. The harness,
    # not Devin, turns these into the actual gating score.
    read_relevant_documentation: bool = Field(
        description=(
            "Did Devin read the relevant project documentation before assessing? "
            "Only meaningful if relevant_documentation_exists is true — see that "
            "field for whether there was any documentation to read at all."
        )
    )
    relevant_documentation_exists: bool = Field(
        description=(
            "Did Devin find any relevant documentation for this ticket's area "
            "(e.g. docs/, README, architecture notes) to even check? Distinct "
            "from read_relevant_documentation — this field exists so a ticket "
            "with genuinely no relevant docs isn't unfairly penalized for not "
            "reading documentation that doesn't exist."
        )
    )
    read_impacted_files_fully: bool = Field(
        description="Did Devin read the impacted files in their entirety, not just skim/guess?"
    )
    identified_affected_files: bool = Field(
        description="Did Devin explicitly identify the specific affected files/symbols?"
    )
    analysis_is_code_grounded: bool = Field(
        description=(
            "Is the analysis grounded in actual code Devin read, as opposed to "
            "generic reasoning/brainstorming about what the change 'probably' involves?"
        )
    )
    identified_required_tests: bool = Field(
        description=(
            "Did Devin identify which tests need to be run or updated? Only "
            "meaningful if tests_applicable is true — see that field for "
            "whether this change needs test coverage at all."
        )
    )
    tests_applicable: bool = Field(
        description=(
            "Does this change need any test coverage at all? A trivial "
            "change (e.g. a copy/label fix) may genuinely need none. Distinct "
            "from identified_required_tests — exists so a ticket that "
            "correctly needs no tests isn't penalized for not naming any, "
            "same fairness pattern as relevant_documentation_exists."
        )
    )
    checked_protected_areas: bool = Field(
        description=(
            "Did Devin explicitly check whether the change touches protected areas "
            "(auth, customer data, migrations, secrets, production config) — "
            "distinct from touches_auth_or_security etc. above, which record what "
            "it found. This records whether it actually looked."
        )
    )

    # --- Gate-specific fields (Priority 2: analysis gates) ---
    initial_understanding: str = Field(
        default="",
        description=(
            "Gate 1. Devin's plain-language restatement of what it thinks "
            "the ticket is asking for, written before diving into code. "
            "Checked for presence only — content quality isn't machine-gradeable, "
            "but skipping this step entirely is itself a signal of rushing."
        ),
    )
    identified_blast_radius: bool = Field(
        default=False,
        description=(
            "Gate 3. Did Devin explicitly consider what else could be affected "
            "beyond the files it plans to directly edit — callers, consumers, "
            "downstream processes? Distinct from identified_affected_files, "
            "which only covers files touched directly. Devin's own analysis is "
            "the current source for this; an external tool (GitNexus) is being "
            "explored separately as Priority 3, not yet wired in."
        ),
    )
    blast_radius_notes: str = Field(
        default="",
        description="Gate 3 detail — what Devin found when considering downstream impact, if anything.",
    )
    self_critique: str = Field(
        default="",
        description=(
            "Gate 4. Devin's second-pass critique of its own proposal, framed "
            "as an adversarial reviewer: what could break, what was assumed, "
            "what is under-specified. Checked for presence."
        ),
    )
    self_critique_raised_blockers: bool = Field(
        default=False,
        description=(
            "Gate 4. Did Devin's own self-critique surface something that "
            "should stop implementation? This does not fail the ticket — a "
            "critique finding a real concern is the gate working correctly, "
            "not a deficiency — but it forces human review before proceeding, "
            "same treatment as open_questions."
        ),
    )
    documentation_drift_check_performed: bool = Field(
        default=False,
        description=(
            "Gate 3b (reconcile). Only meaningful if relevant_documentation_exists "
            "is true. Did Devin explicitly compare the current code/planned "
            "change against claims made in existing documentation (e.g. a "
            "documented value, behavior, or convention)? Distinct from "
            "read_relevant_documentation, which only checks that docs were "
            "read — this checks whether they were cross-referenced against "
            "the actual code for disagreement."
        ),
    )
    documentation_drift_found: bool = Field(
        default=False,
        description=(
            "Gate 3b. Did Devin find the code and documentation disagreeing "
            "in either direction? This does not fail the ticket — finding "
            "drift is the gate succeeding, not a problem with the analysis — "
            "but it forces human review, since resolving which source is "
            "authoritative is a human decision."
        ),
    )
    documentation_drift_notes: str = Field(
        default="",
        description="Gate 3b detail — what was found, or confirmation none was found.",
    )

    recommended_approach: str
    open_questions: list[str] = Field(default_factory=list)



# ---------------------------------------------------------------------------
# Step 2: Implement + open PR
# ---------------------------------------------------------------------------

class ImplementOutput(BaseModel):
    """Expected structured_output shape for the 'implement and open PR' checkpoint."""

    pull_request_url: Optional[str] = None
    files_changed: list[str]
    tests_added: bool
    tests_passing: bool
    ci_status: str = Field(
        description=(
            "Devin's self-reported CI status ('passed'|'failed'|'pending'). "
            "This is self-report, same category as confidence_score — the "
            "harness independently verifies this against GitHub's actual "
            "check-run status when a GitHub token is configured and a real "
            "PR URL is present. See ValidationResult.ci_verification_source."
        )
    )
    summary_of_changes: str
    attempted_master_merge: bool = False  # hard boundary check — must always be False


# ---------------------------------------------------------------------------
# Validation strictness per tier (feeds policy.yaml at runtime)
# ---------------------------------------------------------------------------

class GateResult(BaseModel):
    """Result of one named analysis gate (Priority 2)."""
    gate: str
    passed: bool
    detail: str = ""


class ValidationResult(BaseModel):
    passed: bool
    step: str
    reasons: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
    human_review_reasons: list[str] = Field(
        default_factory=list,
        description=(
            "Why requires_human_review is true, if it is — tier policy, open "
            "questions Devin flagged, self-critique blockers, or a combination. "
            "Distinct from `reasons`, which explains failures; a ticket can "
            "pass and still require review."
        ),
    )
    gates: list[GateResult] = Field(
        default_factory=list,
        description="Per-gate pass/fail for the six analysis gates (Priority 2), in order.",
    )
    stopped_at_gate: Optional[str] = Field(
        default=None,
        description="Name of the first gate that failed, if any. None means all gates passed.",
    )
    computed_score: Optional[float] = Field(
        default=None,
        description=(
            "The harness-computed score for the assess step, derived from the "
            "evidence fields — NOT Devin's self-reported confidence_score. "
            "Only populated for the assess_impact step."
        ),
    )
    evidence_breakdown: Optional[dict[str, bool]] = Field(
        default=None,
        description="The individual evidence yes/no answers the computed_score was built from, for transparency.",
    )
    ci_verification_source: Optional[str] = Field(
        default=None,
        description=(
            "For the implement step only. 'github_api' means CI status was "
            "independently verified against GitHub's real check-run data — "
            "not just Devin's self-report. 'self_report_only' means no "
            "GitHub token was configured or no PR existed yet to check, so "
            "the harness fell back to trusting ci_status as reported. "
            "'mismatch' means Devin's self-report disagreed with the real "
            "GitHub status, which is treated as a hard failure."
        ),
    )
    tier_promoted_from: Optional[int] = Field(
        default=None,
        description=(
            "If the ticket's tier was automatically promoted (e.g. Tier 1 -> "
            "Tier 2 because the real file count exceeded Tier 1's ceiling), "
            "the tier it started at. None means no promotion occurred. "
            "Promotion only happens when EVERY failure reason is one a "
            "higher tier actually resolves (file-count ceiling, or a "
            "sensitive-data block); if any other reason also failed, the "
            "ticket is blocked instead, since promoting wouldn't fix that "
            "other problem and would hide it behind an apparent resolution."
        ),
    )