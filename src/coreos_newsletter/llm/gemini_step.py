from __future__ import annotations

import json
from typing import Any

from coreos_newsletter.models import WeeklyBundle
from coreos_newsletter.settings import Settings


def summarize_bundle_gemini(
    settings: Settings,
    bundle: WeeklyBundle,
    payload: dict[str, Any],
) -> str:
    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set")

    try:
        from google import genai
    except ImportError as e:
        raise RuntimeError('Install LLM extras: pip install "google-genai>=1.0.0"') from e

    client = genai.Client(api_key=settings.google_api_key)

    instruction = (
        "You are an engineering manager assistant. Given the JSON payload, produce a "
        "STRICT JSON object (no markdown fences) with keys:\n"
        "  top_prs: array of {rank,title,url,source,rationale,lead} (max 5)\n"
        "  priority_issue_updates: array of {key,summary,url,note}\n"
        "  customer_bug_updates: array of {key,summary,url,status_note}\n"
        "  stale_priority: array of {key,summary,url,why_it_matters}\n"
        "  risks_blockers: array of short strings\n"
        "Rules: only use facts present in the JSON; if unknown, use empty arrays; "
        "rationale must cite metrics from payload when available."
    )

    user = json.dumps({"payload": payload, "bundle_counts": {
        "pull_requests": len(bundle.pull_requests),
        "jira_issues": len(bundle.jira_issues),
    }}, ensure_ascii=False)

    resp = client.models.generate_content(
        model=settings.gemini_model,
        contents=[instruction, user],
    )
    text = (resp.text or "").strip()
    return text


def parse_json_strict(blob: str) -> dict[str, Any]:
    blob = blob.strip()
    if blob.startswith("```"):
        blob = blob.strip("`")
        if blob.lower().startswith("json"):
            blob = blob[4:].lstrip()
    return json.loads(blob)


def draft_newsletter_gemini(
    settings: Settings,
    summary: dict[str, Any] | str,
) -> str:
    """Turn structured summary JSON into Markdown (same model as summarize)."""
    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set")

    try:
        from google import genai
    except ImportError as e:
        raise RuntimeError('Install LLM extras: pip install "google-genai>=1.0.0"') from e

    client = genai.Client(api_key=settings.google_api_key)

    summary_text = (
        json.dumps(summary, indent=2, ensure_ascii=False)
        if isinstance(summary, dict)
        else str(summary)
    )

    instruction = (
        "You write crisp internal engineering newsletters. Stay faithful to the facts "
        "in the JSON; do not invent tickets or PRs or URLs.\n"
        "Output Markdown only (no JSON, no markdown code fence wrapping the whole doc).\n"
        "Use a 'space exploration' metaphor lightly (section titles only).\n"
        "Include: TL;DR bullets, Top PRs, Priority issues, Customer bugs, Blockers, "
        "Shoutouts for PR leads.\n"
        "Tone: encouraging, precise about risks."
    )

    resp = client.models.generate_content(
        model=settings.gemini_model,
        contents=[instruction, "SUMMARY:\n" + summary_text],
    )
    return (resp.text or "").strip()
