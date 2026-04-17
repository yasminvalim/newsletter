from __future__ import annotations

import datetime as dt

import httpx

from coreos_newsletter.collectors.github import fetch_github_prs
from coreos_newsletter.collectors.gitlab import fetch_gitlab_mrs
from coreos_newsletter.collectors.jira import fetch_jira_issues, fetch_jira_stale_priority
from coreos_newsletter.models import JiraIssueRecord, WeeklyBundle
from coreos_newsletter.settings import Settings


def build_weekly_bundle(
    settings: Settings,
    window_start: dt.datetime,
    window_end: dt.datetime,
) -> WeeklyBundle:
    meta: dict = {"warnings": []}

    gh_prs, gh_w = fetch_github_prs(settings, window_start, window_end)
    meta["warnings"].extend(gh_w)

    gl_prs, gl_w = fetch_gitlab_mrs(settings, window_start, window_end)
    meta["warnings"].extend(gl_w)

    jira_issues: list[JiraIssueRecord] = []
    try:
        jira_issues, j_w = fetch_jira_issues(settings, window_start, window_end)
        meta["warnings"].extend(j_w)
    except httpx.HTTPStatusError as e:
        meta["warnings"].append(
            f"Jira issues fetch failed: HTTP {e.response.status_code} ({e.request.url})",
        )
    except httpx.HTTPError as e:
        meta["warnings"].append(f"Jira issues fetch failed: {e}")

    stale_issues: list[JiraIssueRecord] = []
    stale_cutoff = window_end - dt.timedelta(days=3)
    try:
        stale_issues, st_w = fetch_jira_stale_priority(settings, stale_cutoff)
        meta["warnings"].extend(st_w)
    except httpx.HTTPStatusError as e:
        meta["warnings"].append(
            f"Jira stale-priority fetch failed: HTTP {e.response.status_code}",
        )
    except httpx.HTTPError as e:
        meta["warnings"].append(f"Jira stale-priority fetch failed: {e}")

    meta["stale_priority_issues"] = [
        {
            "key": i.key,
            "summary": i.summary,
            "status": i.status,
            "priority": i.priority,
            "url": i.url,
            "last_updated": i.updated_at.isoformat(),
        }
        for i in stale_issues
    ]

    return WeeklyBundle(
        window_start=window_start,
        window_end=window_end,
        pull_requests=gh_prs + gl_prs,
        jira_issues=jira_issues,
        meta=meta,
    )
