from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PullRequestRecord(BaseModel):
    source: Literal["github", "gitlab"]
    id: str
    title: str
    url: str
    author: str | None = None
    state: str
    updated_at: datetime
    merged_at: datetime | None = None
    additions: int | None = None
    deletions: int | None = None
    changed_files: int | None = None
    labels: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict, description="Original subset for debugging")


class JiraIssueRecord(BaseModel):
    key: str
    summary: str
    url: str
    status: str
    priority: str | None = None
    issue_type: str | None = None
    labels: list[str] = Field(default_factory=list)
    updated_at: datetime
    raw: dict[str, Any] = Field(default_factory=dict)


class WeeklyBundle(BaseModel):
    window_start: datetime
    window_end: datetime
    pull_requests: list[PullRequestRecord] = Field(default_factory=list)
    jira_issues: list[JiraIssueRecord] = Field(default_factory=list)
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Counts, warnings, and fetch notes",
    )
