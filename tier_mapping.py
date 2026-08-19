"""
tier_mapping.py — Type + Priority -> provisional tier.

Implements the mapping proposed in the guardrails status report (item 6).
The client never sets a tier directly — Type and Priority are fields they
already fill in on the Exel.Work intake form for their own reasons, and
this maps those to a starting tier by policy, once.

Deliberately asymmetric across types, not a flat grid — see the reasoning
in the status report:
- Bug: risk comes from *what* it touches, not urgency. Priority barely
  moves the tier, except a High-priority bug often means an active
  incident, and incident tickets tend to be rushed/under-specified.
- Task: carries more inherent ambiguity than a bug, so urgency compounds
  risk rather than just reflecting business pain.
- Story: needs product judgment a client can't be expected to specify
  precisely, regardless of urgency — Type alone floors it at Tier 2.

This tier is always provisional. Devin's own assess-step findings
(validate_assess_step in devin_harness_service.py) can escalate a ticket
to stricter handling via the existing block checks, but nothing here ever
relaxes a tier below what this mapping assigns.
"""

from __future__ import annotations

from models import Priority, Tier, TicketType

_MAPPING: dict[tuple[TicketType, Priority], Tier] = {
    (TicketType.BUG, Priority.LOW): Tier.TIER_1,
    (TicketType.BUG, Priority.MEDIUM): Tier.TIER_1,
    (TicketType.BUG, Priority.HIGH): Tier.TIER_2,

    (TicketType.TASK, Priority.LOW): Tier.TIER_2,
    (TicketType.TASK, Priority.MEDIUM): Tier.TIER_2,
    (TicketType.TASK, Priority.HIGH): Tier.TIER_3,

    (TicketType.STORY, Priority.LOW): Tier.TIER_2,
    (TicketType.STORY, Priority.MEDIUM): Tier.TIER_3,
    (TicketType.STORY, Priority.HIGH): Tier.TIER_3,
}

# RiskLevel is kept on TicketContext for readability/reporting; derive it
# 1:1 from tier rather than asking a human to set two related values.
_RISK_LEVEL_BY_TIER = {
    Tier.TIER_1: "low",
    Tier.TIER_2: "medium",
    Tier.TIER_3: "high",
}


def assign_provisional_tier(ticket_type: TicketType, priority: Priority) -> Tier:
    """Look up the starting tier for a ticket. Always provisional — see module docstring."""
    return _MAPPING[(ticket_type, priority)]


def risk_level_for_tier(tier: Tier) -> str:
    return _RISK_LEVEL_BY_TIER[tier]
