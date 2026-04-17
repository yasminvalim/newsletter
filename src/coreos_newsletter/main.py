from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import TypeAdapter

from coreos_newsletter.heuristics import bundle_to_llm_payload, default_window
from coreos_newsletter.llm.gemini_step import (
    draft_newsletter_gemini,
    parse_json_strict,
    summarize_bundle_gemini,
)
from coreos_newsletter.models import WeeklyBundle
from coreos_newsletter.pipeline.bundle_builder import build_weekly_bundle
from coreos_newsletter.settings import Settings


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, WeeklyBundle):
        payload = data.model_dump(mode="json")
    else:
        payload = data
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_bundle(path: Path) -> WeeklyBundle:
    return TypeAdapter(WeeklyBundle).validate_json(path.read_text(encoding="utf-8"))


def cmd_fetch(args: argparse.Namespace) -> int:
    settings = Settings()
    start, end = default_window(days=args.days)
    bundle = build_weekly_bundle(settings, start, end)
    out = Path(args.out) / "bundle.json"
    _write_json(out, bundle)
    print(f"Wrote {out}")
    for w in bundle.meta.get("warnings", []):
        print(f"warning: {w}", file=sys.stderr)
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    settings = Settings()
    bundle_path = Path(args.bundle)
    bundle = _read_bundle(bundle_path)
    payload = bundle_to_llm_payload(bundle, settings.customer_bug_label_list())
    try:
        raw = summarize_bundle_gemini(settings, bundle, payload)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2
    try:
        parsed = parse_json_strict(raw)
    except json.JSONDecodeError:
        parsed = {"_raw_model_output": raw}

    out = Path(args.out) / "gemini_summary.json"
    _write_json(out, parsed)
    print(f"Wrote {out}")
    return 0


def cmd_draft(args: argparse.Namespace) -> int:
    settings = Settings()
    summary_path = Path(args.summary)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    try:
        md = draft_newsletter_gemini(settings, summary)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2
    out = Path(args.out) / "newsletter.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    rc = cmd_fetch(args)
    if rc != 0:
        return rc
    args.bundle = str(Path(args.out) / "bundle.json")
    rc = cmd_summarize(args)
    if rc != 0:
        return rc
    args.summary = str(Path(args.out) / "gemini_summary.json")
    return cmd_draft(args)


def main() -> int:
    p = argparse.ArgumentParser(description="CoreOS newsletter POC pipeline")
    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--out", default="output", help="Output directory")

    f = sub.add_parser("fetch", parents=[common], help="Fetch GitHub/GitLab/Jira into bundle.json")
    f.add_argument("--days", type=int, default=7, help="Rolling window length in days")
    f.set_defaults(func=cmd_fetch)

    s = sub.add_parser("summarize", parents=[common], help="Run Gemini on bundle.json")
    s.add_argument("--bundle", required=True, help="Path to bundle.json")
    s.set_defaults(func=cmd_summarize)

    d = sub.add_parser("draft", parents=[common], help="Run Gemini on gemini_summary.json → newsletter.md")
    d.add_argument("--summary", required=True, help="Path to gemini_summary.json")
    d.set_defaults(func=cmd_draft)

    a = sub.add_parser("all", parents=[common], help="fetch + summarize + draft")
    a.add_argument("--days", type=int, default=7)
    a.set_defaults(func=cmd_all)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
