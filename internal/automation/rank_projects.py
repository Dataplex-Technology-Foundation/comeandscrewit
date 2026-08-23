#!/usr/bin/env python3
"""
rank_projects.py — derives "top 5" rankings of NWS Grand Challenge awarded
projects from reference/nws-grand-challenge-tracker.md, by two axes:

  1. Award size — parsed from dollar figures mentioned in each project's
     "Progress" text (e.g. "$3.74 million", "$404,000"). Most projects do
     not have a publicly disclosed amount; only projects where a figure
     was actually found are eligible for this ranking.
  2. Information density — a proxy for "how much is publicly known/being
     published about this project," scored from the number of distinct
     sources checked plus the length of the progress writeup. This is a
     proxy, not a citation-impact metric: a project with a long "nothing
     found" writeup and many dead-end sources checked can still rank
     lower than intended if it doesn't distinguish real content from
     search-exhaustion notes. Treat as directional, not authoritative.

Designed to run on a schedule (weekly) so rankings can be diffed over time
as more research/press coverage accumulates — see
reference/nws-grand-challenge-rankings-history.json for the run log this
script appends to.

Writes:
  - reference/nws-grand-challenge-rankings.md (current snapshot, human-readable)
  - reference/nws-grand-challenge-rankings-history.json (append-only run log)
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = REPO_ROOT / "site"
INTERNAL_ROOT = REPO_ROOT / "internal"
TRACKER_FILE = INTERNAL_ROOT / "reference" / "nws-grand-challenge-tracker.md"
RANKINGS_FILE = INTERNAL_ROOT / "reference" / "nws-grand-challenge-rankings.md"
RANKINGS_HISTORY_FILE = INTERNAL_ROOT / "reference" / "nws-grand-challenge-rankings-history.json"

PROJECT_HEADER_RE = re.compile(r"^### (?P<id>\S+)\s+—\s+(?P<recipient>.+)$", re.MULTILINE)

DOLLAR_RE = re.compile(
    r"\$\s?([\d,.]+)\s?(million|M\b|thousand|K\b)?",
    re.IGNORECASE,
)


def log(msg):
    print(msg, file=sys.stderr)


PROGRAM_TOTAL_DENYLIST = (
    "package", "total", "nationwide", "nationally", "40 project", "40-project",
    "40 funded", "overall program", "across all", "of 40", "usda's $105",
    "usda aphis's $105", "grand challenge funding", "$105 million package",
)


def parse_dollar_amount(text):
    """
    Returns the largest dollar figure mentioned in text, in whole dollars,
    or None. Skips sentences that read as references to the ~$105M/40-project
    program total (a recurring confounder in the tracker's writeups) rather
    than this specific project's own award size.
    """
    best = None
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        lowered = sentence.lower()
        if any(term in lowered for term in PROGRAM_TOTAL_DENYLIST):
            continue
        for match in DOLLAR_RE.finditer(sentence):
            raw_num, unit = match.groups()
            try:
                num = float(raw_num.replace(",", ""))
            except ValueError:
                continue
            unit = (unit or "").lower()
            if unit in ("million", "m"):
                num *= 1_000_000
            elif unit in ("thousand", "k"):
                num *= 1_000
            if best is None or num > best:
                best = num
    return best


def parse_projects(md_text):
    """
    Splits the tracker markdown into per-project blocks and extracts
    id, recipient, title, progress text, and sources-checked list.
    """
    headers = list(PROJECT_HEADER_RE.finditer(md_text))
    projects = []
    for i, m in enumerate(headers):
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(md_text)
        block = md_text[start:end]

        title_m = re.search(r"\*\*Title:\*\*\s*(.+)", block)
        progress_m = re.search(r"\*\*Progress:\*\*\s*(.+?)(?=\n\*\*Sources checked|\Z)", block, re.DOTALL)
        sources_block_m = re.search(r"\*\*Sources checked:\*\*(.*?)(?=\n###|\Z)", block, re.DOTALL)

        title = title_m.group(1).strip() if title_m else ""
        progress = progress_m.group(1).strip() if progress_m else ""
        sources = []
        if sources_block_m:
            sources = re.findall(r"^- (https?://\S+)", sources_block_m.group(1), re.MULTILINE)

        projects.append(
            {
                "id": m.group("id"),
                "recipient": m.group("recipient").strip(),
                "title": title,
                "progress": progress,
                "sources": sources,
                "dollar_amount": parse_dollar_amount(progress),
                "info_score": len(sources) * 10 + len(progress.split()),
            }
        )
    return projects


def render_markdown(projects, run_date):
    by_award = sorted(
        (p for p in projects if p["dollar_amount"]),
        key=lambda p: p["dollar_amount"],
        reverse=True,
    )[:5]
    by_info = sorted(projects, key=lambda p: p["info_score"], reverse=True)[:5]

    lines = [
        "# NWS Grand Challenge — Top 5 Project Rankings",
        "",
        f"Generated: {run_date} (automated, see `scripts/rank_projects.py`)",
        f"Derived from: `{TRACKER_FILE.relative_to(REPO_ROOT)}` ({len(projects)} projects parsed)",
        "",
        "Two independent rankings — a project can appear in one, both, or neither.",
        "'Info density' is a proxy (source count + writeup length), not a",
        "measure of actual research impact; treat as directional only.",
        "",
        "---",
        "",
        "## Top 5 by disclosed award size",
        "",
    ]
    if by_award:
        lines.append("| Rank | Project | Recipient | Disclosed amount |")
        lines.append("|---|---|---|---|")
        for i, p in enumerate(by_award, 1):
            lines.append(
                f"| {i} | {p['id']} — {p['title']} | {p['recipient']} | "
                f"${p['dollar_amount']:,.0f} |"
            )
    else:
        lines.append("_No projects had a parseable disclosed dollar amount this run._")
    lines.append("")

    lines.append("## Top 5 by information density (proxy for publication activity)")
    lines.append("")
    lines.append("| Rank | Project | Recipient | Sources checked | Score |")
    lines.append("|---|---|---|---|---|")
    for i, p in enumerate(by_info, 1):
        lines.append(
            f"| {i} | {p['id']} — {p['title']} | {p['recipient']} | "
            f"{len(p['sources'])} | {p['info_score']} |"
        )
    lines.append("")

    return "\n".join(lines), [p["id"] for p in by_award], [p["id"] for p in by_info]


def main():
    if not TRACKER_FILE.exists():
        log(f"Tracker file not found: {TRACKER_FILE}")
        sys.exit(1)

    md_text = TRACKER_FILE.read_text(encoding="utf-8")
    projects = parse_projects(md_text)
    log(f"Parsed {len(projects)} projects")

    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rendered, top5_award_ids, top5_info_ids = render_markdown(projects, run_date)
    RANKINGS_FILE.write_text(rendered, encoding="utf-8")

    history = []
    if RANKINGS_HISTORY_FILE.exists():
        history = json.loads(RANKINGS_HISTORY_FILE.read_text(encoding="utf-8"))
    entry = {"date": run_date, "top5_by_award": top5_award_ids, "top5_by_info": top5_info_ids}
    if history and history[-1].get("date") == run_date:
        history[-1] = entry
    else:
        history.append(entry)
    RANKINGS_HISTORY_FILE.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")

    log(f"Wrote {RANKINGS_FILE.relative_to(REPO_ROOT)} and updated {RANKINGS_HISTORY_FILE.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
