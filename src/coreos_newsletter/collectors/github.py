from __future__ import annotations

import datetime as dt
from typing import Any

import httpx

from coreos_newsletter.models import PullRequestRecord
from coreos_newsletter.settings import Settings


def _parse_dt(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    # GitHub returns Z suffix
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return dt.datetime.fromisoformat(value)


def _fetch_one_repo(
    client: httpx.Client,
    owner: str,
    repo: str,
    window_start: dt.datetime,
    window_end: dt.datetime,
    *,
    max_list: int,
) -> list[PullRequestRecord]:
    prs: list[PullRequestRecord] = []
    r = client.get(
        f"/repos/{owner}/{repo}/pulls",
        params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 100},
    )
    r.raise_for_status()
    items: list[dict[str, Any]] = r.json()

    for raw in items[:max_list]:
        updated = _parse_dt(raw.get("updated_at"))
        if updated is None:
            continue
        if updated < window_start.replace(tzinfo=dt.timezone.utc):
            break
        if updated > window_end.replace(tzinfo=dt.timezone.utc):
            continue

        num = raw["number"]
        detail = client.get(f"/repos/{owner}/{repo}/pulls/{num}")
        detail.raise_for_status()
        d = detail.json()

        merged = _parse_dt(d.get("merged_at"))
        labels = [lb["name"] for lb in d.get("labels", []) if isinstance(lb, dict) and "name" in lb]

        prs.append(
            PullRequestRecord(
                source="github",
                id=str(d["id"]),
                title=d.get("title") or "",
                url=d.get("html_url") or "",
                author=(d.get("user") or {}).get("login"),
                state=d.get("state") or "unknown",
                updated_at=updated,
                merged_at=merged,
                additions=d.get("additions"),
                deletions=d.get("deletions"),
                changed_files=d.get("changed_files"),
                labels=labels,
                raw={
                    "repo": f"{owner}/{repo}",
                    "number": num,
                    "base": (d.get("base") or {}).get("ref"),
                    "head": (d.get("head") or {}).get("ref"),
                },
            )
        )

    return prs


def fetch_github_prs(
    settings: Settings,
    window_start: dt.datetime,
    window_end: dt.datetime,
    *,
    max_list: int = 50,
) -> tuple[list[PullRequestRecord], list[str]]:
    warnings: list[str] = []
    repos = settings.github_repo_list()
    if not all([settings.github_token, settings.github_owner]) or not repos:
        warnings.append("GitHub skipped: set GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO")
        return [], warnings

    owner = settings.github_owner
    base = "https://api.github.com"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {settings.github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    prs: list[PullRequestRecord] = []
    with httpx.Client(base_url=base, headers=headers, timeout=60.0) as client:
        for repo in repos:
            try:
                prs.extend(
                    _fetch_one_repo(client, owner, repo, window_start, window_end, max_list=max_list),
                )
            except httpx.HTTPStatusError as e:
                warnings.append(f"GitHub repo {owner}/{repo}: HTTP {e.response.status_code}")
            except httpx.HTTPError as e:
                warnings.append(f"GitHub repo {owner}/{repo}: {e}")

    return prs, warnings
