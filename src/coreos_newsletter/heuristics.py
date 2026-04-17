from __future__ import annotations

import datetime as dt

from coreos_newsletter.models import JiraIssueRecord, PullRequestRecord, WeeklyBundle


def _pr_impact_score(pr: PullRequestRecord) -> int:
    add = pr.additions or 0
    delete = pr.deletions or 0
    files = pr.changed_files or 0
    return add + delete + files * 50


def top_pull_requests(bundle: WeeklyBundle, *, limit: int = 5) -> list[PullRequestRecord]:
    ranked = sorted(bundle.pull_requests, key=_pr_impact_score, reverse=True)
    return ranked[:limit]


def customer_bug_issues(bundle: WeeklyBundle, label_allowlist: list[str]) -> list[JiraIssueRecord]:
    allow = {x.lower() for x in label_allowlist}
    out: list[JiraIssueRecord] = []
    for issue in bundle.jira_issues:
        labels_l = {x.lower() for x in issue.labels}
        if labels_l & allow:
            out.append(issue)
    return out


def done_customer_bugs(
    bundle: WeeklyBundle,
    label_allowlist: list[str],
    *,
    done_substrings: tuple[str, ...] = ("done", "closed", "resolved"),
) -> list[JiraIssueRecord]:
    """Heuristic: customer-tagged issues whose status looks terminal."""
    hits = customer_bug_issues(bundle, label_allowlist)
    out: list[JiraIssueRecord] = []
    for issue in hits:
        s = issue.status.lower()
        if any(d in s for d in done_substrings):
            out.append(issue)
    return out


def bundle_to_llm_payload(bundle: WeeklyBundle, settings_label_list: list[str]) -> dict:
    """Structured view for LLMs: smaller than full raw, includes heuristic hints."""
    window = {
        "start": bundle.window_start.isoformat(),
        "end": bundle.window_end.isoformat(),
    }
    top = top_pull_requests(bundle, limit=8)
    cust = customer_bug_issues(bundle, settings_label_list)
    done_c = done_customer_bugs(bundle, settings_label_list)
    stale = bundle.meta.get("stale_priority_issues") or []

    return {
        "window": window,
        "top_pull_requests_heuristic": [
            {
                "title": p.title,
                "url": p.url,
                "source": p.source,
                "author": p.author,
                "additions": p.additions,
                "deletions": p.deletions,
                "changed_files": p.changed_files,
                "merged_at": p.merged_at.isoformat() if p.merged_at else None,
            }
            for p in top
        ],
        "jira_updated_in_window_count": len(bundle.jira_issues),
        "customer_bug_issues_in_window": [
            {"key": i.key, "summary": i.summary, "status": i.status, "url": i.url} for i in cust
        ],
        "customer_bug_issues_marked_done_heuristic": [
            {"key": i.key, "summary": i.summary, "status": i.status, "url": i.url} for i in done_c
        ],
        "stale_priority_issues": list(stale),
    }


def default_window(*, days: int = 7, now: dt.datetime | None = None) -> tuple[dt.datetime, dt.datetime]:
    end = now or dt.datetime.now(dt.timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=dt.timezone.utc)
    start = end - dt.timedelta(days=days)
    return start, end
