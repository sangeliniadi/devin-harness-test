"""
devin_client.py — "go to Devin once, for one step" primitive.

This is the core piece per the doc's final table: it wraps Devin's real v1
API (https://docs.devin.ai/api-reference/v1) for a single scoped call, and
does NOT itself decide whether to call again — that's devin_harness_service.py's
job. Keeping this file "dumb" (one call in, one structured result out) is
what makes the harness loop auditable: every decision to proceed lives in
one place, not scattered across API calls.

Auth: expects DEVIN_API_KEY in the environment. Swap for your org's actual
key management (e.g. a secrets manager) before this touches anything real.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests
from pydantic import BaseModel

API_BASE = "https://api.devin.ai/v1"
DEFAULT_POLL_INTERVAL_S = 5
DEFAULT_POLL_TIMEOUT_S = 60 * 30  # 30 min ceiling for a single scoped step

TERMINAL_STATUSES = {"blocked", "finished", "expired"}


class DevinSessionError(RuntimeError):
    """Raised when a Devin session fails, times out, or returns unusable output."""


@dataclass
class DevinStepResult:
    session_id: str
    status: str
    structured_output: Optional[dict[str, Any]]
    pull_request_url: Optional[str]
    raw: dict[str, Any]


def _headers() -> dict[str, str]:
    api_key = os.environ.get("DEVIN_API_KEY")
    if not api_key:
        raise DevinSessionError("DEVIN_API_KEY is not set in the environment.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def create_scoped_session(
    prompt: str,
    structured_output_schema: type[BaseModel],
    *,
    repo: Optional[str] = None,
    playbook_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
    max_acu_limit: Optional[int] = None,
) -> str:
    """
    Create a single Devin session for one scoped step.

    `structured_output_schema` is a Pydantic model (from models.py) — we send
    its JSON Schema to Devin so it knows the exact shape to keep its
    structured_output in. This is the harness's contract with Devin for
    this step; Devin updates structured_output on its own schedule as it
    works (per Devin's docs), and we poll for it below.
    """
    payload: dict[str, Any] = {
        "prompt": prompt,
        "structured_output_schema": structured_output_schema.model_json_schema(),
        "tags": tags or [],
    }
    if repo:
        # NOTE: repo targeting depends on how your org's Devin<->GitHub
        # connection is configured (org-level repo permissions vs. an
        # explicit repos param on session creation). Confirm the exact
        # field with whoever administers the Devin.ai org connection —
        # this is one of the "Still open" items in section 5.7 of the
        # policy doc.
        payload["prompt"] = f"[repo: {repo}]\n\n{prompt}"
    if playbook_id:
        payload["playbook_id"] = playbook_id
    if max_acu_limit:
        payload["max_acu_limit"] = max_acu_limit

    resp = requests.post(f"{API_BASE}/sessions", json=payload, headers=_headers())
    resp.raise_for_status()
    data = resp.json()
    session_id = data["session_id"]
    return session_id


def poll_session(
    session_id: str,
    *,
    poll_interval_s: int = DEFAULT_POLL_INTERVAL_S,
    timeout_s: int = DEFAULT_POLL_TIMEOUT_S,
) -> DevinStepResult:
    """
    Poll a Devin session until it reaches a terminal status (blocked/finished/expired)
    or we hit our own timeout. Devin sessions are asynchronous — this can
    take minutes to hours per the doc, so timeout_s should be set per-step,
    not globally.
    """
    elapsed = 0
    backoff = poll_interval_s

    while elapsed < timeout_s:
        resp = requests.get(f"{API_BASE}/session/{session_id}", headers=_headers())
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status_enum") or data.get("status")
        print(f"  ...session status: {status}")
        if status in TERMINAL_STATUSES:
            pr = data.get("pull_request") or {}
            return DevinStepResult(
                session_id=session_id,
                status=status,
                structured_output=data.get("structured_output"),
                pull_request_url=pr.get("url"),
                raw=data,
            )

        time.sleep(backoff)
        elapsed += backoff
        backoff = min(backoff * 2, 30)  # exponential backoff, capped

    raise DevinSessionError(
        f"Session {session_id} did not reach a terminal status within {timeout_s}s. "
        f"This itself is a signal worth logging — per the doc's Session Insights "
        f"guidance, repeated timeouts on a tier suggest the eligibility bar is wrong."
    )


def run_scoped_step(
    prompt: str,
    structured_output_schema: type[BaseModel],
    **create_kwargs: Any,
) -> DevinStepResult:
    """Convenience wrapper: create a session for one step, then poll to completion."""
    session_id = create_scoped_session(prompt, structured_output_schema, **create_kwargs)
    return poll_session(session_id)