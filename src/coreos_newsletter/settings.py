from __future__ import annotations

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")
    github_owner: str | None = Field(default=None, alias="GITHUB_OWNER")
    github_repo: str | None = Field(default=None, alias="GITHUB_REPO")

    gitlab_token: str | None = Field(default=None, alias="GITLAB_TOKEN")
    gitlab_base_url: str = Field(default="https://gitlab.com", alias="GITLAB_BASE_URL")
    gitlab_project_id: str | None = Field(default=None, alias="GITLAB_PROJECT_ID")

    jira_base_url: str | None = Field(default=None, alias="JIRA_BASE_URL")
    jira_email: str | None = Field(default=None, alias="JIRA_EMAIL")
    jira_api_token: str | None = Field(default=None, alias="JIRA_API_TOKEN")
    jira_project_key: str | None = Field(default=None, alias="JIRA_PROJECT_KEY")

    customer_bug_labels: str = Field(
        default="customer-bug,customer",
        alias="NEWSLETTER_CUSTOMER_BUG_LABELS",
    )
    jira_priority_field: str = Field(default="priority", alias="JIRA_PRIORITY_FIELD")
    jira_priority_names: str = Field(
        default="Highest,High",
        alias="JIRA_PRIORITY_NAMES",
    )

    google_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    )
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")

    @field_validator("google_api_key", mode="before")
    @classmethod
    def _strip_api_key(cls, v: object) -> object:
        if v is None or not isinstance(v, str):
            return v
        s = v.strip()
        if len(s) >= 2 and s[0] in "'\"" and s[0] == s[-1]:
            s = s[1:-1].strip()
        return s or None

    def customer_bug_label_list(self) -> list[str]:
        return [s.strip() for s in self.customer_bug_labels.split(",") if s.strip()]

    def priority_name_list(self) -> list[str]:
        return [s.strip() for s in self.jira_priority_names.split(",") if s.strip()]

    def github_repo_list(self) -> list[str]:
        """One or more repo names under GITHUB_OWNER (comma-separated in GITHUB_REPO)."""
        if not self.github_repo:
            return []
        return [s.strip() for s in self.github_repo.split(",") if s.strip()]

    def gitlab_project_id_list(self) -> list[str]:
        """One or more project IDs or URL-encoded paths (comma-separated in GITLAB_PROJECT_ID)."""
        if not self.gitlab_project_id:
            return []
        return [s.strip() for s in self.gitlab_project_id.split(",") if s.strip()]
