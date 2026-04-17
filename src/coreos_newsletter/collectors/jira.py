from __future__ import annotations

import base64
import datetime as dt
from typing import Any
from urllib.parse import quote

import httpx

from coreos_newsletter.models import JiraIssueRecord
from coreos_newsletter.settings import Settings


def _parse_jira_dt(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    # Jira Cloud: "2024-01-15T10:11:12.000+0000" → fromisoformat wants +00:00
    s = value.replace("+0000", "+00:00").replace("-0000", "-00:00")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return None


def _basic_auth_header(email: str, token: str) -> str:
    raw = f"{email}:{token}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _fields() -> list[str]:
    return ["summary", "status", "priority", "issuetype", "labels", "updated"]


def _search_jql(
    client: httpx.Client,
    jql: str,
    *,
    max_results: int,
) -> list[dict[str, Any]]:
    """JQL search via enhanced endpoint (replaces removed /rest/api/3/search)."""
    issues: list[dict[str, Any]] = []
    next_token: str | None = None
    fields_param = ",".join(_fields())

    while len(issues) < max_results:
        page_size = min(50, max_results - len(issues))
        params: dict[str, str | int] = {
            "jql": jql,
            "maxResults": page_size,
            "fields": fields_param,
        }
        if next_token:
            params["nextPageToken"] = next_token

        r = client.get("/rest/api/3/search/jql", params=params)
        r.raise_for_status()
        data = r.json()
        batch = data.get("issues") or []
        issues.extend(batch)

        next_token = data.get("nextPageToken") or data.get("next_page_token")
        if not next_token or not batch:
            break

    return issues[:max_results]


def fetch_jira_issues(
    settings: Settings,
    window_start: dt.datetime,
    window_end: dt.datetime,
    *,
    max_results: int = 100,
) -> tuple[list[JiraIssueRecord], list[str]]:
    warnings: list[str] = []
    required = [
        settings.jira_base_url,
        settings.jira_email,
        settings.jira_api_token,
        settings.jira_project_key,
    ]
    if not all(required):
        warnings.append(
            "Jira skipped: set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY",
        )
        return [], warnings

    base = settings.jira_base_url.rstrip("/")
    auth = _basic_auth_header(settings.jira_email, settings.jira_api_token)
    headers = {
        "Authorization": auth,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    project = settings.jira_project_key
    # Date-only JQL tends to be more portable than full timestamps across Jira sites.
    ws_d = window_start.astimezone(dt.timezone.utc).date().isoformat()

    jql = f'project = "{project}" AND updated >= "{ws_d}" ORDER BY updated DESC'

    records: list[JiraIssueRecord] = []

    with httpx.Client(base_url=base, headers=headers, timeout=60.0) as client:
        raw_issues = _search_jql(client, jql, max_results=max_results)
        for item in raw_issues:
            key = item.get("key") or ""
            fields = item.get("fields") or {}
            status = (fields.get("status") or {}).get("name") or ""
            priority = (fields.get("priority") or {}).get("name")
            itype = (fields.get("issuetype") or {}).get("name")
            labels = fields.get("labels") or []
            if not isinstance(labels, list):
                labels = []
            summary = fields.get("summary") or ""
            updated = _parse_jira_dt(fields.get("updated"))

            if updated is None:
                continue
            if updated > window_end.replace(tzinfo=dt.timezone.utc):
                continue

            url = f"{base}/browse/{quote(key)}"
            records.append(
                JiraIssueRecord(
                    key=key,
                    summary=summary,
                    url=url,
                    status=status,
                    priority=priority,
                    issue_type=itype,
                    labels=[str(x) for x in labels],
                    updated_at=updated,
                    raw={"id": item.get("id")},
                )
            )

    return records, warnings


def fetch_jira_stale_priority(
    settings: Settings,
    stale_before: dt.datetime,
    *,
    max_results: int = 50,
) -> tuple[list[JiraIssueRecord], list[str]]:
    """Issues in priority set not done, not updated since stale_before."""
    warnings: list[str] = []
    required = [
        settings.jira_base_url,
        settings.jira_email,
        settings.jira_api_token,
        settings.jira_project_key,
    ]
    if not all(required):
        return [], warnings

    base = settings.jira_base_url.rstrip("/")
    auth = _basic_auth_header(settings.jira_email, settings.jira_api_token)
    headers = {
        "Authorization": auth,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    project = settings.jira_project_key
    names = settings.priority_name_list()
    if not names:
        return [], warnings

    prio_list = ", ".join(f'"{n}"' for n in names)
    cutoff_d = stale_before.astimezone(dt.timezone.utc).date().isoformat()
    jql = (
        f'project = "{project}" AND priority in ({prio_list}) '
        f'AND statusCategory != Done AND updated <= "{cutoff_d}" '
        "ORDER BY updated ASC"
    )

    issues: list[JiraIssueRecord] = []
    with httpx.Client(base_url=base, headers=headers, timeout=60.0) as client:
        raw_issues = _search_jql(client, jql, max_results=max_results)
        for item in raw_issues:
            key = item.get("key") or ""
            fields = item.get("fields") or {}
            status = (fields.get("status") or {}).get("name") or ""
            priority = (fields.get("priority") or {}).get("name")
            itype = (fields.get("issuetype") or {}).get("name")
            labels = fields.get("labels") or []
            summary = fields.get("summary") or ""
            updated = _parse_jira_dt(fields.get("updated"))
            if updated is None:
                continue
            url = f"{base}/browse/{quote(key)}"
            issues.append(
                JiraIssueRecord(
                    key=key,
                    summary=summary,
                    url=url,
                    status=status,
                    priority=priority,
                    issue_type=itype,
                    labels=[str(x) for x in labels] if isinstance(labels, list) else [],
                    updated_at=updated,
                    raw={"id": item.get("id")},
                )
            )

    return issues, warnings
