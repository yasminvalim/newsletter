from coreos_newsletter.collectors.github import fetch_github_prs
from coreos_newsletter.collectors.gitlab import fetch_gitlab_mrs
from coreos_newsletter.collectors.jira import fetch_jira_issues

__all__ = ["fetch_github_prs", "fetch_gitlab_mrs", "fetch_jira_issues"]
