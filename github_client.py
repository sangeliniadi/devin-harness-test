"""
github_client.py — independently verify a PR's real CI status via GitHub's
API, instead of trusting ImplementOutput.ci_status (Devin's own self-report).

This is Gate 6 (PR readiness) made real rather than self-reported, the same
pattern as jira_client.py fetching real ticket data instead of manual entry.
Devin's ci_status field is the same category of claim as confidence_score —
plausible-sounding, unverified. This module checks the actual GitHub
check-run data for the PR's head commit.

Auth: expects GITHUB_TOKEN in the environment — a personal access token
(classic or fine-grained) with at least read access to checks on the target
repo. Generate one at https://github.com/settings/tokens.

Honest limitation: if GITHUB_TOKEN isn't set, or the PR doesn't exist yet
(e.g. Devin claims a PR was opened but the URL doesn't resolve), this
degrades to self-report only rather than blocking outright — a real
deployment likely wants this to be a hard requirement, but for now the
harness surfaces which mode was used (ci_verification_source) rather than
silently pretending verification happened.
"""

from __future__ import annotations

import os
import re
from typing import Any, Optional

import requests

API_BASE = "https://api.github.com"


class GitHubVerificationError(RuntimeError):
    """Raised when a PR's CI status cannot be independently verified."""


def _headers() -> Optional[dict[str, str]]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    """Extract (owner, repo, pr_number) from a GitHub PR URL."""
    match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url.strip()
    )
    if not match:
        raise GitHubVerificationError(f"Could not parse a PR number from URL: {pr_url!r}")
    owner, repo, number = match.groups()
    return owner, repo, int(number)


def fetch_real_ci_status(pr_url: str) -> dict[str, Any]:
    """
    Fetch the real, current CI status for a PR's head commit from GitHub.

    Returns a dict: {"status": "passed"|"failed"|"pending"|"unknown", "checks": [...]}
    Raises GitHubVerificationError if verification can't be performed at all
    (no token, PR not found, API error) — callers should treat this as
    "verification unavailable," not as a CI failure.
    """
    headers = _headers()
    if headers is None:
        raise GitHubVerificationError("GITHUB_TOKEN is not set — cannot independently verify CI.")

    owner, repo, pr_number = _parse_pr_url(pr_url)

    pr_resp = requests.get(f"{API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}", headers=headers)
    if pr_resp.status_code == 404:
        raise GitHubVerificationError(f"PR not found: {pr_url}")
    pr_resp.raise_for_status()
    head_sha = pr_resp.json()["head"]["sha"]

    checks_resp = requests.get(
        f"{API_BASE}/repos/{owner}/{repo}/commits/{head_sha}/check-runs", headers=headers
    )
    checks_resp.raise_for_status()
    check_runs = checks_resp.json().get("check_runs", [])

    if not check_runs:
        return {"status": "unknown", "checks": [], "note": "no check runs found for this commit"}

    conclusions = [c.get("conclusion") for c in check_runs]
    statuses = [c.get("status") for c in check_runs]

    if any(s != "completed" for s in statuses):
        overall = "pending"
    elif all(c == "success" for c in conclusions):
        overall = "passed"
    else:
        overall = "failed"

    return {
        "status": overall,
        "checks": [
            {"name": c.get("name"), "status": c.get("status"), "conclusion": c.get("conclusion")}
            for c in check_runs
        ],
    }
