from __future__ import annotations

import datetime as dt
from typing import Any
from urllib.parse import quote

import httpx

from coreos_newsletter.models import PullRequestRecord
from coreos_newsletter.settings import Settings


def _parse_dt(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    # GitLab often returns ISO8601 with Z
    if isinstance(value, str) and value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return dt.datetime.fromisoformat(value) if value else None


def _path_pid(pid: str) -> str:
    return quote(str(pid), safe="")


def _fetch_gitlab_project(
    client: httpx.Client,
    pid: str,
    window_start: dt.datetime,
    window_end: dt.datetime,
    *,
    max_pages: int,
) -> list[PullRequestRecord]:
    enc = _path_pid(pid)
    start_s = window_start.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mrs: list[PullRequestRecord] = []
    page = 1
    while page <= max_pages:
        r = client.get(
            f"/projects/{enc}/merge_requests",
            params={
                "state": "all",
                "order_by": "updated_at",
                "sort": "desc",
                "updated_after": start_s,
                "page": page,
                "per_page": 50,
            },
        )
        r.raise_for_status()
        batch: list[dict[str, Any]] = r.json()
        if not batch:
            break

        for raw in batch:
            updated = _parse_dt(raw.get("updated_at"))
            if updated is None:
                continue
            if updated > window_end.replace(tzinfo=dt.timezone.utc):
                continue

            iid = raw["iid"]
            detail = client.get(f"/projects/{enc}/merge_requests/{iid}")
            detail.raise_for_status()
            d = detail.json()

            labels = d.get("labels") or []
            if not isinstance(labels, list):
                labels = []

            web = d.get("web_url") or ""
            author = (d.get("author") or {}).get("username")

            changes_count = d.get("changes_count")
            try:
                changed_files = int(changes_count) if changes_count is not None else None
            except (TypeError, ValueError):
                changed_files = None

            merged = _parse_dt(d.get("merged_at"))

            mrs.append(
                PullRequestRecord(
                    source="gitlab",
                    id=str(d.get("id")),
                    title=d.get("title") or "",
                    url=web,
                    author=author,
                    state=d.get("state") or "unknown",
                    updated_at=updated,
                    merged_at=merged,
                    additions=None,
                    deletions=None,
                    changed_files=changed_files,
                    labels=[str(x) for x in labels],
                    raw={
                        "gitlab_project_id": pid,
                        "iid": iid,
                        "target_branch": d.get("target_branch"),
                        "source_branch": d.get("source_branch"),
                    },
                )
            )

        if len(batch) < 50:
            break
        page += 1

    return mrs


def fetch_gitlab_mrs(
    settings: Settings,
    window_start: dt.datetime,
    window_end: dt.datetime,
    *,
    max_pages: int = 5,
) -> tuple[list[PullRequestRecord], list[str]]:
    warnings: list[str] = []
    projects = settings.gitlab_project_id_list()
    if not all([settings.gitlab_token]) or not projects:
        warnings.append("GitLab skipped: set GITLAB_TOKEN and GITLAB_PROJECT_ID")
        return [], warnings

    base = settings.gitlab_base_url.rstrip("/")
    headers = {"PRIVATE-TOKEN": settings.gitlab_token}

    mrs: list[PullRequestRecord] = []
    with httpx.Client(
        base_url=f"{base}/api/v4",
        headers=headers,
        timeout=60.0,
        follow_redirects=False,
    ) as client:
        for pid in projects:
            try:
                mrs.extend(
                    _fetch_gitlab_project(
                        client,
                        pid,
                        window_start,
                        window_end,
                        max_pages=max_pages,
                    ),
                )
            except httpx.HTTPStatusError as e:
                loc = e.response.headers.get("Location", "")
                msg = f"HTTP {e.response.status_code}"
                if e.response.status_code in (301, 302, 303, 307, 308) and "sign_in" in (loc or ""):
                    msg += " (redirect to sign-in: check GITLAB_BASE_URL and GITLAB_TOKEN)"
                warnings.append(f"GitLab project {pid}: {msg}")
            except httpx.HTTPError as e:
                warnings.append(f"GitLab project {pid}: {e}")

    return mrs, warnings
