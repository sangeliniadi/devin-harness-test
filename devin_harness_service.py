"""
devin_harness_service.py — the harness itself.

Per the policy doc: "harness is not a safety feature bolted onto Devin —
it is the specific way Devin is called." This file is that orchestration:
call -> validate -> conditional next call, with Exel.Work's backend
(this code) actively in the loop at every checkpoint, never letting Devin
chain steps on its own.

This is deliberately the smallest possible version of the full sequence —
Stage 1 of the rollout plan (5.11): one step, one validation check, on a
Tier-1-type ticket. Extend step-by-step from here rather than building the
full assess -> implement -> PR sequence in one go.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from devin_client import DevinSessionError, run_scoped_step
from github_client import GitHubVerificationError, fetch_real_ci_status
from models import (
    AssessImpactOutput,
    GateResult,
    ImplementOutput,
    Tier,
    TicketContext,
    ValidationResult,
)

logger = logging.getLogger("devin_harness")

POLICY_PATH = Path(__file__).parent / "policy.yaml"


class HardBoundaryViolation(RuntimeError):
    """
    Raised when Devin's output would violate a deterministic, non-negotiable
    boundary (e.g. merging to master). This is never tier-dependent and is
    never a validation "score" — it's a hard stop, always, per section 5.4.
    """


def _load_policy() -> dict[str, Any]:
    with open(POLICY_PATH) as f:
        return yaml.safe_load(f)


def _tier_policy(tier: Tier) -> dict[str, Any]:
    policy = _load_policy()
    return policy["tiers"][tier.value]


# ---------------------------------------------------------------------------
# Hard boundary enforcement — applies at every tier, no exceptions (5.4)
# ---------------------------------------------------------------------------

def enforce_hard_boundaries(implement_output: ImplementOutput) -> None:
    if implement_output.attempted_master_merge:
        raise HardBoundaryViolation(
            "Devin's output indicates an attempted direct merge to master. "
            "The harness will not issue any further API call for this ticket. "
            "Escalating to a human immediately."
        )

    policy = _load_policy()
    protected_paths = policy.get("protected_paths", [])
    touched_protected = [
        f for f in implement_output.files_changed
        if any(f.startswith(p) or p in f for p in protected_paths)
    ]
    if touched_protected:
        raise HardBoundaryViolation(
            f"Implementation touched protected path(s): {touched_protected}. "
            f"This is a hard boundary, independent of tier or reported risk — "
            f"Devin's default GitHub permissions technically allow writes here, "
            f"so this check is the actual enforcement, not the tier's own risk "
            f"flags. Escalating to a human immediately."
        )


def compute_deterministic_score(output: AssessImpactOutput) -> tuple[float, dict[str, bool]]:
    """
    The harness computes its own score from concrete yes/no evidence, instead
    of trusting Devin's self-reported confidence_score. Per direct guidance:
    "don't let the LLM figure out the probability of whether it's right or
    wrong... I will set up the criteria, you will just ask it to say yes or
    no, and then you will create the score."

    Each evidence field is a discrete, falsifiable claim about an action
    Devin actually took (read files, identified tests, etc.) — harder to be
    vague or lazy about than a bare probability. The score is simply the
    fraction of evidence questions answered True. This is not a claim that
    evidence fields are independently verified (they're still Devin's own
    report) — it's a claim that the *scoring itself* is no longer up to
    Devin, only the underlying yes/no answers are.
    """
    # Documentation check is derived, not taken directly from Devin's raw
    # answer: a ticket with no relevant documentation shouldn't be penalized
    # for not reading documentation that doesn't exist. Passes if either
    # there's no relevant documentation, or there is and Devin read it.
    documentation_check_passed = (
        not output.relevant_documentation_exists
        or output.read_relevant_documentation
    )
    tests_check_passed = (
        not output.tests_applicable
        or output.identified_required_tests
    )

    evidence: dict[str, bool] = {
        "documentation_checked_if_exists": documentation_check_passed,
        "read_impacted_files_fully": output.read_impacted_files_fully,
        "identified_affected_files": output.identified_affected_files,
        "analysis_is_code_grounded": output.analysis_is_code_grounded,
        "tests_identified_if_applicable": tests_check_passed,
        "checked_protected_areas": output.checked_protected_areas,
        "has_testable_success_criteria": output.has_testable_success_criteria,
    }
    score = sum(1 for v in evidence.values() if v) / len(evidence)
    return score, evidence


# ---------------------------------------------------------------------------
# Priority 2: analysis gates
#
# Six named gates, evaluated in order. Gates 1-5 run within the existing
# assess-only call, as structured fields the harness checks independently —
# this was chosen over six separate Devin API calls to avoid the cost/time
# of a much heavier session sequence, consistent with the "smallest possible
# harness loop" approach used since Stage 1. Gate 6 (PR readiness) already
# exists as the implement-step validation (validate_implement_step,
# enforce_hard_boundaries) — documented here, not reimplemented.
#
# Gate 3 (impact/blast-radius) currently relies on Devin's own self-report
# (identified_blast_radius). The policy doc names an external tool
# (GitNexus) as an alternative source for this gate — that's Priority 3,
# not yet wired in. This is a known, documented limitation of Gate 3 as it
# stands today, not an oversight.
# ---------------------------------------------------------------------------

def evaluate_gates(output: AssessImpactOutput) -> tuple[list[GateResult], Optional[str]]:
    """
    Evaluate gates 1-5 in order. Returns (all gate results, name of first
    failed gate or None). Gates are evaluated independently and all results
    are returned for transparency, but `stopped_at_gate` names only the
    first failure, since that's the point a real deployment would actually
    halt at.
    """
    gates: list[GateResult] = []

    gates.append(GateResult(
        gate="1_initial_understanding",
        passed=bool(output.initial_understanding.strip()),
        detail=output.initial_understanding or "not provided",
    ))

    gate2_passed = (
        output.analysis_is_code_grounded
        and len(output.affected_files) > 0
        and bool(output.affected_scope_description.strip())
    )
    gates.append(GateResult(
        gate="2_code_grounded_analysis",
        passed=gate2_passed,
        detail=(
            f"{len(output.affected_files)} file(s) identified, "
            f"analysis_is_code_grounded={output.analysis_is_code_grounded}"
        ),
    ))

    gates.append(GateResult(
        gate="3_impact_blast_radius",
        passed=output.identified_blast_radius,
        detail=output.blast_radius_notes or "not provided (Devin self-report only — GitNexus not yet wired in, see Priority 3)",
    ))

    # Gate 3b (reconcile) — not in the original six named gates, added after
    # reviewing an external example. Fair the same way documentation_checked
    # _if_exists is fair: only requires the check when there's documentation
    # to reconcile against at all.
    reconcile_passed = (
        not output.relevant_documentation_exists
        or output.documentation_drift_check_performed
    )
    gates.append(GateResult(
        gate="3b_documentation_reconciliation",
        passed=reconcile_passed,
        detail=output.documentation_drift_notes or (
            "no relevant documentation to reconcile against" if not output.relevant_documentation_exists
            else "not provided"
        ),
    ))

    gates.append(GateResult(
        gate="4_critical_self_review",
        passed=bool(output.self_critique.strip()),
        detail=(
            output.self_critique or "not provided"
        ) + (
            " [raised blockers — requires human review]" if output.self_critique_raised_blockers else ""
        ),
    ))

    gates.append(GateResult(
        gate="5_testability",
        passed=output.has_testable_success_criteria,
        detail="measurable success criteria present" if output.has_testable_success_criteria else "not testable as written",
    ))

    stopped_at = next((g.gate for g in gates if not g.passed), None)
    return gates, stopped_at


# ---------------------------------------------------------------------------
# Step 1: Assess impact
# ---------------------------------------------------------------------------

def validate_assess_step(
    output: AssessImpactOutput, ticket: TicketContext
) -> ValidationResult:
    policy = _load_policy()
    rules = _tier_policy(ticket.tier)["assess_step"]
    reasons: list[str] = []
    # Promotable reasons are tracked separately: these are specifically the
    # failures a HIGHER tier would actually resolve (more room, or a tier
    # that doesn't block sensitive-data changes outright). Everything else
    # goes only into `reasons` and blocks promotion entirely — a low score,
    # a failed mandatory field, or an untestable ticket isn't fixed by
    # moving to a stricter tier, so mixing those with a promotable reason
    # should never result in an automatic promotion.
    promotable_reasons: list[str] = []

    computed_score, evidence = compute_deterministic_score(output)
    min_score = rules.get("require_computed_score_min", rules.get("require_confidence_score_min", 0.6))
    if computed_score < min_score:
        failed_evidence = [k for k, v in evidence.items() if not v]
        reasons.append(
            f"harness-computed score {computed_score:.2f} below tier minimum "
            f"{min_score} — failed evidence: {failed_evidence}"
        )

    # Mandatory evidence fields — a HARD gate, independent of the aggregate
    # score. A weak answer here cannot be averaged away by strong answers
    # elsewhere. This exists because the averaged score alone reintroduces
    # the exact problem this design was meant to fix: one real gap hiding
    # behind an otherwise-good result. See EX-61, where read_relevant_
    # documentation=false still passed on aggregate score alone (0.857).
    mandatory_fields = rules.get("mandatory_evidence_fields", [])
    failed_mandatory = [f for f in mandatory_fields if not evidence.get(f, False)]
    if failed_mandatory:
        reasons.append(
            f"mandatory evidence field(s) failed regardless of aggregate score: "
            f"{failed_mandatory} — these cannot be offset by other passing checks"
        )

    # These three ARE promotable: Tier 1/2 block sensitive-data changes
    # outright, but Tier 3 exists specifically to handle them, under
    # guaranteed human review. A higher tier genuinely resolves this.
    if rules.get("block_if_touches_customer_data") and output.touches_customer_data:
        msg = "touches customer data — not eligible at this tier"
        reasons.append(msg)
        promotable_reasons.append(msg)

    if rules.get("block_if_touches_auth_or_security") and output.touches_auth_or_security:
        msg = "touches auth/security-sensitive code — not eligible at this tier"
        reasons.append(msg)
        promotable_reasons.append(msg)

    if rules.get("block_if_touches_production_config") and output.touches_production_config:
        msg = "touches production config — not eligible at this tier"
        reasons.append(msg)
        promotable_reasons.append(msg)

    if rules.get("require_single_focused_change") and not output.is_single_focused_change:
        reasons.append("bundles multiple unrelated changes — should be split into sub-tickets")

    if rules.get("require_explicit_scope_flag") and not output.affected_scope_description.strip():
        reasons.append("impact assessment did not explicitly name affected scope/files")

    # NOTE: testability is no longer checked here directly — Gate 5 (below,
    # via evaluate_gates) is now the single, formal named checkpoint for
    # has_testable_success_criteria. Checking it twice produced duplicate
    # reasons on the same underlying failure (confirmed on EX-87's real
    # output: "acceptance criteria is not testable" and "gate '5_testability'
    # failed" both firing for the same field). mandatory_evidence_fields
    # below can still independently list has_testable_success_criteria for
    # tiers where it's mandatory — that message serves a different purpose
    # (explains the failure bypasses the aggregate score), so it's kept.

    if rules.get("require_sufficient_context") and not output.has_sufficient_context:
        reasons.append(
            "insufficient code patterns/docs available — Devin would be guessing "
            "rather than working from real context"
        )

    granted = set(policy.get("granted_permissions", []))
    missing_permissions = [p for p in output.required_permissions if p not in granted]
    if missing_permissions:
        reasons.append(
            f"requires permission(s) not currently granted: {missing_permissions} "
            f"(see EX-65 — a low-risk change can still need access nobody has)"
        )

    # This one IS promotable: a genuinely bigger change than the tier
    # assumed. Higher tiers have a larger or uncapped file ceiling, along
    # with a correspondingly stricter score threshold and more mandatory
    # checks — the tradeoff is real, not a loophole.
    max_files = rules.get("max_affected_files")
    if max_files is not None and len(output.affected_files) > max_files:
        msg = (
            f"touches {len(output.affected_files)} files, over this tier's ceiling "
            f"of {max_files} — diff too large to review meaningfully at this tier"
        )
        reasons.append(msg)
        promotable_reasons.append(msg)

    # Priority 2: six-gate analysis sequence. Gates 1-5 evaluated here;
    # Gate 6 (PR readiness) lives in validate_implement_step, documented
    # separately. A failed gate is added to reasons like any other check —
    # gates aren't a separate pass/fail track, they're additional named
    # checkpoints within the same decision.
    gates, stopped_at_gate = evaluate_gates(output)
    for gate in gates:
        if not gate.passed:
            reasons.append(f"gate '{gate.gate}' failed: {gate.detail}")

    passed = len(reasons) == 0

    # requires_human_review has three independent sources: tier policy
    # (Tier 2/3 always require checkpoint-level review), open_questions,
    # and now self_critique_raised_blockers (Gate 4) — Devin's own
    # adversarial self-review surfacing a real concern. None of these fail
    # the ticket on their own; each just forces a human to look before
    # implementation proceeds.
    tier_requires_human = _tier_policy(ticket.tier)["human_review"]["checkpoint_level"]
    has_open_questions = bool(output.open_questions)
    self_critique_flagged = output.self_critique_raised_blockers
    drift_found = output.documentation_drift_found
    requires_human = (
        tier_requires_human or has_open_questions or self_critique_flagged or drift_found
    )

    human_review_reasons: list[str] = []
    if tier_requires_human:
        human_review_reasons.append(
            f"Tier {ticket.tier.value} policy requires checkpoint-level human review"
        )
    if has_open_questions:
        human_review_reasons.append(
            f"Devin flagged {len(output.open_questions)} open question(s) "
            f"requiring a decision before implementation proceeds"
        )
    if self_critique_flagged:
        human_review_reasons.append(
            "Devin's own self-critique (Gate 4) surfaced a concern requiring review"
        )
    if drift_found:
        human_review_reasons.append(
            "Gate 3b found documentation and code disagreeing — a human must "
            "decide which source is authoritative"
        )

    # Tier promotion — only when EVERY failure reason is one a higher tier
    # actually resolves. If any non-promotable reason also failed (a low
    # score, a missing mandatory field, a gate failure), promotion is
    # skipped entirely: moving to a stricter tier wouldn't fix those, and
    # silently "resolving" the ticket via promotion while a real problem
    # remains would hide it rather than surface it.
    can_promote = (
        not passed
        and promotable_reasons
        and set(reasons) == set(promotable_reasons)
        and ticket.tier != Tier.TIER_3
    )
    if can_promote:
        original_tier = ticket.tier
        promoted_tier = Tier(ticket.tier.value + 1)
        logger.info(
            "Tier %s -> Tier %s promotion for %s: every failure reason was "
            "promotable (%s). Re-validating against the new tier's rules "
            "using the same assess output — no new Devin call needed.",
            original_tier.value, promoted_tier.value, ticket.jira_ticket_id,
            promotable_reasons,
        )
        ticket.tier = promoted_tier
        promoted_result = validate_assess_step(output, ticket)
        # Preserve the original starting tier even if this promotes more
        # than once in a chain (e.g. Tier 1 -> 2 -> 3), and force human
        # review regardless of what the new tier's own policy would
        # otherwise require — an automatic tier change is itself a
        # consequential decision a human should see and confirm, not
        # something the harness decides alone.
        if promoted_result.tier_promoted_from is None:
            promoted_result.tier_promoted_from = original_tier.value
        promoted_result.requires_human_review = True
        promoted_result.human_review_reasons.append(
            f"Ticket was automatically promoted from Tier {original_tier.value} "
            f"to Tier {promoted_tier.value} ({'; '.join(promotable_reasons)}) — "
            f"confirm this reflects the ticket's actual scope before proceeding"
        )
        return promoted_result

    return ValidationResult(
        passed=passed,
        step="assess_impact",
        reasons=reasons,
        requires_human_review=requires_human,
        human_review_reasons=human_review_reasons,
        gates=gates,
        stopped_at_gate=stopped_at_gate,
        computed_score=computed_score,
        evidence_breakdown=evidence,
    )


def run_assess_step(ticket: TicketContext) -> tuple[AssessImpactOutput, ValidationResult]:
    ticket_body = ticket.full_description or ticket.acceptance_criteria
    prompt = (
        f"Assess the impact of the following change before any code is written.\n"
        f"Jira ticket: {ticket.jira_ticket_id}\n"
        f"Full ticket description (verbatim from Jira):\n{ticket_body}\n\n"
        f"Short acceptance-criteria summary (may be incomplete — defer to the "
        f"full description above for specifics): {ticket.acceptance_criteria}\n"
        f"Target branch: {ticket.target_branch}\n\n"
        f"Do not write or modify any code in this step. Only assess and report.\n\n"
        f"IMPORTANT — do not simply assign yourself a confidence score. Instead, "
        f"answer each evidence question honestly with true/false, based on "
        f"actions you actually took, not how confident you feel:\n"
        f"- Is there any relevant project documentation for this area at all "
        f"(docs/, README, architecture notes)? And if so, did you read it? "
        f"(A ticket with no relevant documentation is not penalized for this "
        f"— report honestly whether documentation exists, separately from "
        f"whether you read it.)\n"
        f"- Did you read the impacted files in their entirety, not just skim them?\n"
        f"- Did you explicitly identify the specific affected files/symbols?\n"
        f"- Is your analysis grounded in code you actually read, not generic "
        f"reasoning about what the change 'probably' involves?\n"
        f"- Does this change need any test coverage at all, and if so, did "
        f"you identify which tests need to be run or updated? (A genuinely "
        f"trivial change may need none — report honestly whether tests "
        f"apply, separately from whether you identified them.)\n"
        f"- Did you explicitly check whether this touches auth, customer data, "
        f"migrations, secrets, or production config — regardless of the answer?\n"
        f"- Does the ticket have a measurable, testable success criterion?\n\n"
        f"The confidence_score field is informational only and will not be used "
        f"to decide whether this proceeds — only your answers to the evidence "
        f"questions above determine that.\n\n"
        f"Additionally, work through this sequence explicitly and report each step:\n"
        f"1. Initial understanding — before touching code, state in your own "
        f"words what you think this ticket is asking for.\n"
        f"2. Ground your analysis in actual files/functions/config you read, "
        f"not general reasoning about what the change probably involves.\n"
        f"3. Blast radius — beyond the files you'd directly edit, did you check "
        f"what else depends on them (callers, consumers, downstream processes)? "
        f"Report what you found, even if the answer is 'nothing else depends on this.'\n"
        f"4. Critique your own proposal as an adversarial reviewer would: what "
        f"could break, what did you assume, what is under-specified? If this "
        f"critique surfaces a real concern, say so explicitly — flagging a "
        f"genuine problem is the correct outcome, not a failure on your part.\n"
        f"5. Confirm whether the ticket has a measurable, testable definition of done.\n"
        f"6. If relevant documentation exists, explicitly compare it against the "
        f"actual current code — report whether they agree or whether you found "
        f"drift in either direction (a documented value/behavior that no longer "
        f"matches the code, or vice versa). Finding drift is a useful result, "
        f"not something to avoid reporting."
    )
    result = run_scoped_step(prompt, AssessImpactOutput, repo=ticket.repo)
    if result.status == "expired":
        raise DevinSessionError(
            f"Session {result.session_id} expired without Devin reporting "
            f"completion — any structured_output present is unconfirmed and "
            f"not trusted as a real assessment."
        )
    if result.structured_output is None:
        raise DevinSessionError("Assess-impact step returned no structured_output.")

    output = AssessImpactOutput.model_validate(result.structured_output)
    validation = validate_assess_step(output, ticket)
    return output, validation


# ---------------------------------------------------------------------------
# Retry / iteration on a weak first-pass assessment
# ---------------------------------------------------------------------------

# Fields directly tied to how thoroughly Devin did its own investigation —
# a second, more careful pass could plausibly fix these, since they're
# about effort/attention, not a fact about the ticket or the change itself.
# Everything NOT in this set (has_testable_success_criteria,
# has_sufficient_context, is_single_focused_change, the touches_* flags,
# required_permissions, and any gate/tier/hard-boundary failure) is a
# property of the ticket or the change, not of how carefully Devin worked —
# retrying won't fix those. Same reasoning already used to decide which
# tier-1-vs-ceiling failures are eligible for automatic tier promotion.
RETRYABLE_EVIDENCE_FIELDS = {
    "read_relevant_documentation",
    "read_impacted_files_fully",
    "identified_affected_files",
    "analysis_is_code_grounded",
    "identified_required_tests",
    "checked_protected_areas",
}

MAX_ASSESS_RETRIES = 1


def _failed_evidence_fields(evidence: dict[str, bool]) -> set[str]:
    return {field for field, passed in evidence.items() if not passed}


def _retry_prompt_addendum(failed_fields: set[str]) -> str:
    """Built once we know exactly which evidence questions the first pass
    answered false on — tells Devin specifically what to redo, rather than
    a generic 'try harder,' which risks wasting the retry on the same gaps."""
    field_explanations = {
        "read_relevant_documentation": "you reported not reading relevant documentation that does exist — go read it now",
        "read_impacted_files_fully": "you reported not reading the impacted files in their entirety — go read them fully now",
        "identified_affected_files": "you didn't explicitly identify the specific affected files/symbols — name them explicitly this time",
        "analysis_is_code_grounded": "your analysis wasn't grounded in code you actually read — re-do the analysis grounded in real files, not general reasoning",
        "identified_required_tests": "tests apply to this change but you didn't identify which ones — identify the specific tests now",
        "checked_protected_areas": "you didn't explicitly check whether this touches auth, customer data, migrations, secrets, or production config — check explicitly now",
    }
    lines = [field_explanations[f] for f in sorted(failed_fields) if f in field_explanations]
    return (
        "\n\nThis is a second attempt at the same assessment. On the first "
        "pass, specifically: " + "; ".join(lines) + ". Everything else about "
        "your first assessment was fine — only redo the parts named above, "
        "then report the full assessment again."
    )


def _retry_shows_genuine_change(
    original: AssessImpactOutput,
    retried: AssessImpactOutput,
    failed_fields: set[str],
) -> bool:
    """
    Cheap, automated proxy check: did the retry produce genuinely different
    substantive content, or did the booleans just flip with identical (or
    near-identical) supporting text? This cannot prove real extra work
    happened — it can only catch the cheapest way of gaming a retry
    (flip the flags, change nothing else). Not a full defense, just a
    filter so obviously-faked retries don't sail through silently while
    genuinely-improved ones don't get penalized with unnecessary review.
    """
    if ("identified_affected_files" in failed_fields or "read_impacted_files_fully" in failed_fields):
        if set(retried.affected_files) == set(original.affected_files):
            return False  # claims to have identified/read files, but the list didn't change at all

    original_text = (
        original.affected_scope_description + original.blast_radius_notes
        + original.recommended_approach
    ).strip()
    retried_text = (
        retried.affected_scope_description + retried.blast_radius_notes
        + retried.recommended_approach
    ).strip()
    if original_text == retried_text:
        return False  # identical supporting text — nothing substantive changed

    return True


def run_assess_step_with_retry(
    ticket: TicketContext,
) -> tuple[AssessImpactOutput, ValidationResult]:
    """
    Wraps run_assess_step with one optional retry, following the same
    safety pattern as tier promotion: only retry when EVERY failed
    evidence field is one a second, more careful pass could plausibly
    fix, and no OTHER kind of failure (a mandatory-field message beyond
    the evidence breakdown, a gate failure, a hard block, tier
    ineligibility, a missing permission) is present alongside it. If a
    non-retryable reason is mixed in, retrying wouldn't fix that reason,
    and a clean-looking retry pass would incorrectly suggest the ticket
    is fine when it still isn't — capped at one retry so this can't loop.

    A successful retry is NOT automatically forced into human review —
    that would mean Tier 1's whole point (auto-continue on a clean pass)
    is defeated every time a retry happens, even a genuinely successful
    one. Instead, a cheap automated check (_retry_shows_genuine_change)
    looks for evidence the retried content actually differs from the
    first pass; only if it looks suspiciously unchanged does this force
    review. Tier 2/3 are unaffected either way, since they already
    require checkpoint review on every ticket regardless of retries.
    """
    output, validation = run_assess_step(ticket)

    if validation.passed or validation.evidence_breakdown is None:
        return output, validation

    failed_evidence = _failed_evidence_fields(validation.evidence_breakdown)

    # Every reason string must be explainable by a retryable evidence gap
    # (either the generic mandatory-evidence-field message, or explicitly
    # naming one of the failed retryable fields) — anything else present
    # blocks the retry entirely, same as mixed reasons blocking promotion.
    def _reason_is_retryable(reason: str) -> bool:
        if "mandatory evidence field(s) failed" in reason:
            return True
        return any(field in reason for field in failed_evidence)

    can_retry = (
        bool(failed_evidence)
        and failed_evidence.issubset(RETRYABLE_EVIDENCE_FIELDS)
        and all(_reason_is_retryable(r) for r in validation.reasons)
    )

    if not can_retry:
        logger.info(
            "Not retrying %s: failure includes a reason beyond retryable "
            "evidence gaps (%s) — a second pass wouldn't fix these.",
            ticket.jira_ticket_id, validation.reasons,
        )
        return output, validation

    logger.info(
        "Retrying assessment for %s once: every failure reason traces to "
        "a retryable evidence gap (%s), nothing else present.",
        ticket.jira_ticket_id, sorted(failed_evidence),
    )

    ticket_body = ticket.full_description or ticket.acceptance_criteria
    retried_ticket = ticket.model_copy(deep=True)
    retried_ticket.full_description = ticket_body + _retry_prompt_addendum(failed_evidence)

    try:
        retry_output, retry_validation = run_assess_step(retried_ticket)
    except DevinSessionError as e:
        # The retry itself failed at the session level (timeout/expired) —
        # fall back to the original first-pass result rather than crashing.
        # We already have a valid, real result from the first attempt; the
        # retry was a bonus chance, not something worth losing that for.
        logger.warning(
            "Retry attempt for %s failed at the session level (%s) — "
            "falling back to the original first-pass result rather than "
            "crashing or discarding it.",
            ticket.jira_ticket_id, e,
        )
        validation.human_review_reasons.append(
            f"A retry was attempted after the first assessment failed on "
            f"retryable evidence gaps, but the retry itself failed at the "
            f"session level ({e}) — this is the original first-pass result, "
            f"not a retried one."
        )
        return output, validation

    if retry_validation.passed:
        genuine = _retry_shows_genuine_change(output, retry_output, failed_evidence)
        if genuine:
            logger.info(
                "Retry for %s passed with content that genuinely differs from "
                "the first pass — proceeding per the tier's normal rules, no "
                "forced review added just because a retry happened.",
                ticket.jira_ticket_id,
            )
        else:
            logger.warning(
                "Retry for %s passed, but the retried content looks "
                "suspiciously unchanged from the first attempt (same file "
                "list / same supporting text) — forcing human review rather "
                "than trusting a possibly-faked retry.",
                ticket.jira_ticket_id,
            )
            retry_validation.requires_human_review = True
            retry_validation.human_review_reasons.append(
                f"This is a retry result, and the automated content check found "
                f"the retried answer(s) for {sorted(failed_evidence)} suspiciously "
                f"unchanged from the first attempt (same affected files and/or "
                f"identical supporting text) — a human should confirm this wasn't "
                f"just a flipped flag with no real additional work behind it."
            )

    return retry_output, retry_validation


# ---------------------------------------------------------------------------
# Step 2: Implement + open PR
# ---------------------------------------------------------------------------

def validate_implement_step(
    output: ImplementOutput, ticket: TicketContext
) -> ValidationResult:
    rules = _tier_policy(ticket.tier)["implement_step"]
    reasons: list[str] = []

    if rules.get("require_tests_passing") and not output.tests_passing:
        reasons.append("tests are not passing")

    # Gate 6 (PR readiness), made real: verify CI against GitHub's actual
    # check-run data instead of trusting Devin's self-reported ci_status.
    # Same self-report problem as confidence_score, applied to CI status —
    # a plausible-sounding "passed" claim is not the same as a real one.
    ci_verification_source = "self_report_only"
    real_ci_status = None
    if output.pull_request_url:
        try:
            result = fetch_real_ci_status(output.pull_request_url)
            real_ci_status = result["status"]
            ci_verification_source = "github_api"
        except GitHubVerificationError as e:
            logger.warning(
                "Could not independently verify CI for %s: %s — falling back "
                "to Devin's self-reported ci_status.",
                output.pull_request_url, e,
            )

    expected_ci = rules.get("require_ci_status")
    if real_ci_status is not None:
        # Real data available — this is the actual check, self-report is ignored.
        if output.ci_status != real_ci_status:
            ci_verification_source = "mismatch"
            reasons.append(
                f"Devin reported ci_status='{output.ci_status}' but GitHub's "
                f"actual check-run status is '{real_ci_status}' — self-report "
                f"disagreed with reality, treated as a hard failure regardless "
                f"of which one looks better"
            )
        elif expected_ci and real_ci_status != expected_ci:
            reasons.append(f"verified CI status is '{real_ci_status}', expected '{expected_ci}'")
    else:
        # No independent verification available — fall back to self-report,
        # but this is visibly weaker and surfaced as such via ci_verification_source.
        if expected_ci and output.ci_status != expected_ci:
            reasons.append(
                f"ci_status is '{output.ci_status}' (self-reported, not "
                f"independently verified), expected '{expected_ci}'"
            )

    if not output.pull_request_url:
        reasons.append("no pull_request_url returned")

    passed = len(reasons) == 0
    requires_human = True  # final PR always gets human eyes, per policy 5.2/5.10

    return ValidationResult(
        passed=passed,
        step="implement_and_open_pr",
        reasons=reasons,
        requires_human_review=requires_human,
        ci_verification_source=ci_verification_source,
    )


def run_implement_step(
    ticket: TicketContext, assess_output: AssessImpactOutput
) -> tuple[ImplementOutput, ValidationResult]:
    ticket_body = ticket.full_description or ticket.acceptance_criteria
    rules = _tier_policy(ticket.tier)["implement_step"]
    auto_fix = rules.get("auto_fix_enabled", False)
    prompt = (
        f"Implement the change assessed in the previous step and open a pull "
        f"request against {ticket.target_branch} (NEVER against master).\n"
        f"Jira ticket: {ticket.jira_ticket_id}\n"
        f"Full ticket description (verbatim from Jira):\n{ticket_body}\n\n"
        f"Recommended approach: {assess_output.recommended_approach}\n"
    )
    if auto_fix:
        prompt += (
            "\nIf review comments or CI failures come back on your PR, "
            "respond to them and fix them yourself rather than waiting."
        )
    else:
        prompt += (
            "\nDo not respond to review comments or CI failures automatically — "
            "a human will handle any follow-up on this PR."
        )
    # NOTE: this passes auto_fix as a session tag for now, since the exact
    # Devin API field for enabling Auto-Fix/Devin Review on a session isn't
    # confirmed against current API docs — verify the real parameter name
    # before relying on this for enforcement. The prompt instruction above
    # is the actual mechanism until that's confirmed either way.
    result = run_scoped_step(
        prompt, ImplementOutput, repo=ticket.repo,
        tags=[f"auto_fix_{'on' if auto_fix else 'off'}", f"tier_{ticket.tier.value}"],
    )
    if result.status == "expired":
        raise DevinSessionError(
            f"Session {result.session_id} expired without Devin reporting "
            f"completion — any structured_output present is unconfirmed and "
            f"not trusted, especially for an implement step that may have "
            f"written partial/uncommitted code."
        )
    if result.structured_output is None:
        raise DevinSessionError("Implement step returned no structured_output.")

    output = ImplementOutput.model_validate(result.structured_output)
    enforce_hard_boundaries(output)  # non-negotiable, checked before anything else

    validation = validate_implement_step(output, ticket)
    return output, validation


# ---------------------------------------------------------------------------
# The loop itself — Stage 1 proof of concept
# ---------------------------------------------------------------------------

def run_assess_only(ticket: TicketContext) -> dict[str, Any]:
    """
    Assess-only mode: calls Devin for the 'assess impact' checkpoint and
    stops there, no matter what the tier says. Never proceeds to the
    implement/PR step. Use this for read-only exploration against a real
    repo — e.g. testing how the harness would react to a real ticket
    without writing or committing anything.
    """
    logger.info(
        "Running ASSESS-ONLY (no implementation) for %s against %s",
        ticket.jira_ticket_id,
        ticket.repo,
    )
    try:
        assess_output, assess_validation = run_assess_step_with_retry(ticket)
    except DevinSessionError as e:
        logger.error("Assess step failed at the session level for %s: %s", ticket.jira_ticket_id, e)
        return {
            "ticket": ticket.jira_ticket_id,
            "mode": "assess_only",
            "halted_at": "assess_impact",
            "status": "devin_session_error",
            "error": str(e),
            "escalate_to": ticket.escalation_contact_email,
            "note": (
                "Devin's session failed or timed out before returning a usable "
                "assessment (not a validation failure — this is a Devin/API-level "
                "problem, not the harness rejecting the ticket's content)."
            ),
        }
    return {
        "ticket": ticket.jira_ticket_id,
        "mode": "assess_only",
        "validation": assess_validation.model_dump(),
        "assess_output": assess_output.model_dump(),
        "note": (
            "No code was written and no PR was opened. This mode never "
            "calls the implement step, regardless of tier or validation result."
        ),
    }


def run_harness(ticket: TicketContext) -> dict[str, Any]:
    """
    Smallest possible harness loop, per rollout plan Stage 1:
    one step -> structured response -> validation -> conditional next call.

    Returns a dict summarizing what happened, suitable for logging /
    surfacing back to Jira as a comment. Does NOT auto-post to Jira in this
    proof-of-concept — that's a follow-up integration step.
    """
    logger.info("Starting harness run for %s (tier %s)", ticket.jira_ticket_id, ticket.tier)

    # --- Checkpoint 1: assess impact ---
    try:
        assess_output, assess_validation = run_assess_step_with_retry(ticket)
    except DevinSessionError as e:
        logger.error("Assess step failed at the session level for %s: %s", ticket.jira_ticket_id, e)
        return {
            "ticket": ticket.jira_ticket_id,
            "halted_at": "assess_impact",
            "status": "devin_session_error",
            "error": str(e),
            "escalate_to": ticket.escalation_contact_email,
            "note": (
                "Devin's session failed or timed out before returning a usable "
                "assessment (not a validation failure — this is a Devin/API-level "
                "problem, not the harness rejecting the ticket's content)."
            ),
        }
    if not assess_validation.passed:
        logger.warning(
            "Assess step failed validation for %s: %s",
            ticket.jira_ticket_id,
            assess_validation.reasons,
        )
        return {
            "ticket": ticket.jira_ticket_id,
            "halted_at": "assess_impact",
            "validation": assess_validation.model_dump(),
            "escalate_to": ticket.escalation_contact_email,
        }

    if assess_validation.requires_human_review:
        # Tier 2/3: stop here and wait for a human to approve this
        # checkpoint's output before the next API call is made. In a real
        # deployment this is where we'd post to Jira and pause; the
        # proof-of-concept just returns the pending state.
        logger.info(
            "Assess step passed for %s but requires human checkpoint review "
            "before proceeding (tier %s).",
            ticket.jira_ticket_id,
            ticket.tier,
        )
        return {
            "ticket": ticket.jira_ticket_id,
            "halted_at": "assess_impact",
            "status": "pending_human_checkpoint_review",
            "assess_output": assess_output.model_dump(),
            "reviewer": ticket.reviewer_email,
        }

    # --- Checkpoint 2: implement + open PR ---
    try:
        implement_output, implement_validation = run_implement_step(ticket, assess_output)
    except HardBoundaryViolation as e:
        logger.error("Hard boundary violation for %s: %s", ticket.jira_ticket_id, e)
        return {
            "ticket": ticket.jira_ticket_id,
            "halted_at": "implement_and_open_pr",
            "status": "hard_boundary_violation",
            "reason": str(e),
            "escalate_to": ticket.escalation_contact_email,
        }
    except DevinSessionError as e:
        logger.error("Implement step failed at the session level for %s: %s", ticket.jira_ticket_id, e)
        return {
            "ticket": ticket.jira_ticket_id,
            "halted_at": "implement_and_open_pr",
            "status": "devin_session_error",
            "error": str(e),
            "escalate_to": ticket.escalation_contact_email,
            "note": (
                "Devin's session failed or timed out during implementation — "
                "worth checking manually whether a PR was opened or partial "
                "code was committed before the session failed, since this is "
                "a Devin/API-level failure, not a clean validation stop."
            ),
        }

    if not implement_validation.passed:
        logger.warning(
            "Implement step failed validation for %s: %s",
            ticket.jira_ticket_id,
            implement_validation.reasons,
        )
        return {
            "ticket": ticket.jira_ticket_id,
            "halted_at": "implement_and_open_pr",
            "validation": implement_validation.model_dump(),
            "escalate_to": ticket.escalation_contact_email,
        }

    logger.info(
        "Harness run complete for %s. PR: %s. Awaiting final human review before merge.",
        ticket.jira_ticket_id,
        implement_output.pull_request_url,
    )
    return {
        "ticket": ticket.jira_ticket_id,
        "status": "pr_ready_for_final_review",
        "pull_request_url": implement_output.pull_request_url,
        "reviewer": ticket.reviewer_email,
    }