"""
test_retry.py — quick, no-quota check that run_assess_step_with_retry()
actually works, by faking what run_assess_step() returns instead of
calling the real Devin API. Run this locally after replacing
devin_harness_service.py with the updated version:

    python test_retry.py

This proves the RETRY DECISION LOGIC is correct (does it retry when it
should, does it refuse when it shouldn't) without spending any Devin
quota. It does NOT prove Devin itself will behave well on a real retry
prompt — that still needs a real ticket, see the notes at the bottom.
"""

from unittest.mock import patch

from models import (
    AssessImpactOutput, TicketContext, TicketType, Priority,
    RiskLevel, Tier, ValidationResult,
)
import devin_harness_service as svc


def make_ticket(tier=Tier.TIER_1):
    return TicketContext(
        jira_ticket_id="TEST-1",
        repo="test/repo",
        target_branch="main",
        reviewer_email="lead@example.com",
        escalation_contact_email="pm@example.com",
        ticket_type=TicketType.BUG,
        priority=Priority.MEDIUM,
        risk_level=RiskLevel.LOW,
        tier=tier,
        acceptance_criteria="Fix the thing.",
        estimate_hours=1.0,
    )


def make_output(**overrides):
    base = dict(
        confidence_score=0.8,
        affected_files=["a.py"],
        affected_scope_description="Checked a.py briefly.",
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
        analysis_is_code_grounded=False,   # <-- the one thing failing
        identified_required_tests=True,
        tests_applicable=True,
        checked_protected_areas=True,
        initial_understanding="Understood.",
        identified_blast_radius=True,
        blast_radius_notes="Traced.",
        self_critique="Reviewed.",
        self_critique_raised_blockers=False,
        documentation_drift_check_performed=True,
        documentation_drift_found=False,
        documentation_drift_notes="Match.",
        recommended_approach="Fix it.",
        open_questions=[],
    )
    base.update(overrides)
    return AssessImpactOutput(**base)


print("=" * 70)
print("TEST 1: pure retryable failure -> should retry, and retry succeeds")
print("=" * 70)

first_pass_output = make_output(analysis_is_code_grounded=False)
first_pass_validation = ValidationResult(
    passed=False,
    step="assess_impact",
    reasons=["mandatory evidence field(s) failed regardless of aggregate score: ['analysis_is_code_grounded']"],
    computed_score=0.857,
    evidence_breakdown={
        "documentation_checked_if_exists": True,
        "read_impacted_files_fully": True,
        "identified_affected_files": True,
        "analysis_is_code_grounded": False,
        "tests_identified_if_applicable": True,
        "checked_protected_areas": True,
        "has_testable_success_criteria": True,
    },
)

retry_pass_output = make_output(
    analysis_is_code_grounded=True,
    affected_files=["a.py", "b.py"],  # genuinely different this time
    affected_scope_description="Traced the real call chain through a.py and b.py.",
)
retry_pass_validation = ValidationResult(
    passed=True, step="assess_impact", computed_score=1.0,
    evidence_breakdown={k: True for k in first_pass_validation.evidence_breakdown},
)

with patch.object(
    svc, "run_assess_step",
    side_effect=[(first_pass_output, first_pass_validation), (retry_pass_output, retry_pass_validation)],
) as mock_assess:
    output, validation = svc.run_assess_step_with_retry(make_ticket())

print("Devin was 'called' this many times:", mock_assess.call_count, "(expect 2 — first pass + one retry)")
print("Final passed:", validation.passed, "(expect True)")
print("requires_human_review:", validation.requires_human_review, "(expect False — content genuinely changed)")
print("Final affected_files:", output.affected_files, "(expect ['a.py', 'b.py'])")
assert mock_assess.call_count == 2
assert validation.passed is True
assert validation.requires_human_review is False
print("PASS\n")


print("=" * 70)
print("TEST 2: retryable + non-retryable failure mixed -> must NOT retry")
print("=" * 70)

mixed_validation = ValidationResult(
    passed=False,
    step="assess_impact",
    reasons=[
        "mandatory evidence field(s) failed regardless of aggregate score: ['analysis_is_code_grounded']",
        "acceptance criteria is not testable as written",
    ],
    computed_score=0.71,
    evidence_breakdown={
        "documentation_checked_if_exists": True,
        "read_impacted_files_fully": True,
        "identified_affected_files": True,
        "analysis_is_code_grounded": False,
        "tests_identified_if_applicable": True,
        "checked_protected_areas": True,
        "has_testable_success_criteria": False,  # <-- non-retryable, mixed in
    },
)

with patch.object(
    svc, "run_assess_step",
    side_effect=[(first_pass_output, mixed_validation)],
) as mock_assess:
    output, validation = svc.run_assess_step_with_retry(make_ticket())

print("Devin was 'called' this many times:", mock_assess.call_count, "(expect 1 — no retry attempted)")
print("Final passed:", validation.passed, "(expect False — still fails)")
assert mock_assess.call_count == 1
assert validation.passed is False
print("PASS\n")


print("=" * 70)
print("TEST 3: retry 'succeeds' but content is suspiciously identical -> force review")
print("=" * 70)

faked_retry_output = make_output(analysis_is_code_grounded=True)  # same affected_files, same text as first pass
faked_retry_validation = ValidationResult(
    passed=True, step="assess_impact", computed_score=1.0,
    evidence_breakdown={k: True for k in first_pass_validation.evidence_breakdown},
)

with patch.object(
    svc, "run_assess_step",
    side_effect=[(first_pass_output, first_pass_validation), (faked_retry_output, faked_retry_validation)],
) as mock_assess:
    output, validation = svc.run_assess_step_with_retry(make_ticket())

print("Final passed:", validation.passed, "(expect True)")
print("requires_human_review:", validation.requires_human_review, "(expect True — content looked faked)")
print("human_review_reasons:", validation.human_review_reasons)
assert validation.passed is True
assert validation.requires_human_review is True
print("PASS\n")

print("=" * 70)
print("ALL TESTS PASSED — the retry logic itself is working correctly.")
print("=" * 70)
print(
    "\nNOTE: this only proves the harness's DECISION logic is correct. It "
    "does not prove Devin will actually do better work on a real retry "
    "prompt — that needs a real ticket. Next step: run a real ticket via "
    "run_ticket_from_jira.py and watch the log line for either "
    "'Retrying assessment for...' or 'Not retrying...'."
)
