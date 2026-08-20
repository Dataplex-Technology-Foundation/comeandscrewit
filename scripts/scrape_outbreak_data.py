#!/usr/bin/env python3
"""
scrape_outbreak_data.py — automated daily scrape of outbreak figures and
grant-research publication listings (DTS tracker automation).

RELATIONSHIP TO refresh-outbreak-data.py (DTS-806):
That script is deliberately manual-entry-only and NOT scheduled anywhere,
because at the time it was written, direct fetches of APHIS/CDC/TAHC pages
from this project's dev sandbox returned ECONNRESET/timeout/403 on every
attempt. This script is the automated counterpart, intended to run from
GitHub Actions (a different network egress than the dev sandbox — may or
may not fare better against the same WAFs; failures here are handled
gracefully, not treated as fatal).

TRUST MODEL: this script never pushes directly to a protected branch and
is never wired to auto-merge. The GitHub Actions workflow that runs it
commits its output to a throwaway branch and opens a pull request. A human
reviewing and merging that PR *is* the verification gate — it replaces the
interactive "type APPROVE" step from refresh-outbreak-data.py with a PR
review, appropriate for unattended/scheduled execution.

WHAT IT DOES:
  1. Fetches the APHIS confirmed-cases page and attempts to parse US case
     count, affected states, and affected counties.
  2. Appends a dated snapshot to assets/data/outbreak-history.json
     (append-only time series — this is what powers trend/over-time
     views), regardless of whether the live parse succeeded, so gaps are
     visible instead of silently missing.
  3. Only overwrites assets/data/outbreak-data.json fields where a fresh
     value was actually parsed; unparsed fields (including the two
     regional [VERIFY:...] placeholders, which have no confirmed
     machine-readable source) are left untouched.
  4. Fetches the Screwworm.gov Innovation & Research page and diffs its
     publication list against reference/screwworm-gov-research-publications.md,
     appending skeleton entries (title + DOI, retrieval status "pending
     research pass") for anything new. It does not try to auto-write
     citation notes — that step still wants a research pass, same as the
     original manual process.
  5. Writes a human-readable run summary to scratch/pr-body.md for the
     workflow to use as the PR description, and sets changed=true/false
     in $GITHUB_OUTPUT so the workflow skips opening a PR when nothing
     changed.

CAVEAT: the CSS/regex selectors below are best-effort. A first live test
run (2026-08-20, from this dev environment, not a GitHub Actions runner)
found the confirmed-cases page IS reachable via plain requests (unlike
prior WebFetch-tool attempts), but its case-count and county table appear
to be rendered client-side (no case count or "<County> County" text is
present in the static HTML) -- so usCases and affectedCounties will
routinely come back unparsed and that is expected, not a bug. State names
ARE present in static HTML, but only reliably as "<State> Animal Health
Commission" / "<State> Livestock Board" links -- a bare state-name scan
produced false positives (the page's unrelated international-travel nav
text mentions Hawaii/Alaska/Guam). DO NOT loosen the state matcher back to
a bare name scan, and DO NOT guess at case counts/counties from partial
text; leaving a field unparsed (and flagged in the PR body) is the safe
failure mode. If GitHub Actions gets a different response shape, check
scratch/last-fetch-*.html (uploaded as a workflow artifact) before
changing selectors.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTBREAK_DATA_FILE = REPO_ROOT / "assets" / "data" / "outbreak-data.json"
OUTBREAK_HISTORY_FILE = REPO_ROOT / "assets" / "data" / "outbreak-history.json"
PUBLICATIONS_FILE = REPO_ROOT / "reference" / "screwworm-gov-research-publications.md"
SCRATCH_DIR = REPO_ROOT / "scratch"

CONFIRMED_CASES_URL = (
    "https://www.aphis.usda.gov/animals/animal-health/livestock-and-poultry-disease/"
    "stop-screwworm/current-status/confirmed"
)
RESEARCH_PAGE_URL = (
    "https://www.aphis.usda.gov/animals/animal-health/livestock-and-poultry-disease/"
    "stop-screwworm/innovation-research"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ScrewwormTrackerBot/1.0; "
        "+https://github.com/Dataplex-Technology-Foundation/comeandscrewit)"
    ),
    "Accept": "text/html,application/xhtml+xml",
}

US_STATE_NAMES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York",
    "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "West Virginia", "Wisconsin", "Wyoming",
]


def log(msg):
    print(msg, file=sys.stderr)


def fetch(url, retries=3, timeout=20):
    """Best-effort GET with retries. Returns response text or None."""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
            last_err = f"HTTP {resp.status_code}"
        except requests.RequestException as exc:
            last_err = str(exc)
        log(f"  fetch attempt {attempt}/{retries} for {url} failed: {last_err}")
    log(f"  giving up on {url}: {last_err}")
    return None


def save_debug_html(name, html):
    if html is None:
        return
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    (SCRATCH_DIR / f"last-fetch-{name}.html").write_text(html, encoding="utf-8")


def parse_confirmed_cases(html):
    """
    Best-effort extraction of US case count / states / counties from the
    APHIS confirmed-cases page. Returns a dict of only the fields it
    managed to parse (missing keys mean "could not confirm, leave as-is").
    """
    result = {}
    if not html:
        return result

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    # Case count: look for "NN confirmed cases" or "NN cases" near "screwworm".
    case_match = re.search(r"(\d{1,4})\s+confirmed\s+cases", text, re.IGNORECASE)
    if case_match:
        result["usCases"] = int(case_match.group(1))

    # States: this page links to each affected state's own animal-health-agency
    # NWS page (e.g. "Texas Animal Health Commission NWS Website", "New Mexico
    # Livestock Board NWS Website"). Matching on that adjacency avoids false
    # positives from unrelated boilerplate elsewhere on the page (e.g. this
    # page's international-travel nav text mentions "Hawaii", "Alaska", "Guam"
    # in a completely unrelated context — confirmed via manual inspection of
    # a live fetch; do not loosen this back to a bare state-name scan).
    found_states = [
        s for s in US_STATE_NAMES
        if re.search(rf"\b{re.escape(s)}\s+(?:Animal Health Commission|Livestock Board|Department of Agriculture)\b", text)
    ]
    if found_states:
        result["usStates"] = found_states
        result["usStateCount"] = len(found_states)

    # Counties: look for "<Name> County" patterns, dedup preserving order.
    county_matches = re.findall(r"\b([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)\s+County\b", text)
    if county_matches:
        seen = []
        for c in county_matches:
            if c not in seen:
                seen.append(c)
        if seen:
            result["affectedCounties"] = seen

    return result


def parse_publications(html):
    """
    Extracts (title, doi_url) pairs from the research page's citation-style
    <p> blocks. Mirrors the mhtml-parsing approach used for the initial
    manual pass over this same page.
    """
    if not html:
        return []
    doi_urls = re.findall(r'https://doi\.org/[^\s"\'<>)]+', html)
    return sorted(set(doi_urls))


def existing_doi_urls(publications_md_text):
    return set(re.findall(r'https://doi\.org/[^\s"\'<>)]+', publications_md_text))


def append_new_publication_stubs(new_dois):
    if not new_dois:
        return 0
    if not PUBLICATIONS_FILE.exists():
        log("  publications tracker file not found, skipping stub append")
        return 0

    text = PUBLICATIONS_FILE.read_text(encoding="utf-8")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    stub_block = "\n## Newly detected — needs research pass ({})\n".format(today)
    for doi in sorted(new_dois):
        stub_block += (
            f"\n### (unreviewed) — detected {today}\n"
            f"**Title:** _unknown — not yet researched_\n"
            f"**DOI URL:** {doi}\n"
            f"**Retrieval status:** _pending research pass_\n"
        )

    PUBLICATIONS_FILE.write_text(text.rstrip() + "\n" + stub_block, encoding="utf-8")
    return len(new_dois)


def load_json(path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    summary_lines = [f"# Automated outbreak data refresh — {today}", ""]

    log(f"Fetching {CONFIRMED_CASES_URL}")
    cases_html = fetch(CONFIRMED_CASES_URL)
    save_debug_html("confirmed-cases", cases_html)
    parsed_cases = parse_confirmed_cases(cases_html)

    if parsed_cases:
        summary_lines.append("## Confirmed-cases page")
        summary_lines.append(f"Source: {CONFIRMED_CASES_URL}")
        for k, v in parsed_cases.items():
            summary_lines.append(f"- `{k}` -> {v}")
        summary_lines.append("")
    else:
        summary_lines.append(
            "## Confirmed-cases page\n"
            f"Could not parse any fields from {CONFIRMED_CASES_URL} this run "
            "(fetch failed, or page structure has changed — see "
            "scratch/last-fetch-confirmed-cases.html if fetch succeeded but "
            "parsing failed). outbreak-data.json left unchanged for these "
            "fields.\n"
        )

    outbreak_data = load_json(OUTBREAK_DATA_FILE, {})
    outbreak_data_changed = False
    for key in ("usCases", "usStates", "usStateCount", "affectedCounties"):
        if key in parsed_cases and outbreak_data.get(key) != parsed_cases[key]:
            outbreak_data[key] = parsed_cases[key]
            outbreak_data_changed = True

    if outbreak_data_changed:
        outbreak_data["lastUpdated"] = datetime.now(timezone.utc).strftime("%B %d, %Y")
        save_json(OUTBREAK_DATA_FILE, outbreak_data)
        summary_lines.append("outbreak-data.json fields were updated from the parse above.\n")
    else:
        summary_lines.append("No outbreak-data.json fields changed (either unparsed, or unchanged).\n")

    history = load_json(OUTBREAK_HISTORY_FILE, [])
    history_entry = {
        "date": today,
        "usCases": parsed_cases.get("usCases", outbreak_data.get("usCases")),
        "usStateCount": parsed_cases.get("usStateCount", outbreak_data.get("usStateCount")),
        "affectedCountyCount": len(parsed_cases.get("affectedCounties", outbreak_data.get("affectedCounties", []))),
        "scrapeStatus": "ok" if parsed_cases else "failed",
        "source": CONFIRMED_CASES_URL,
    }
    if not history or history[-1].get("date") != today:
        history.append(history_entry)
    else:
        history[-1] = history_entry
    save_json(OUTBREAK_HISTORY_FILE, history)
    summary_lines.append(
        f"## Trend history\nAppended snapshot for {today} to "
        f"`{OUTBREAK_HISTORY_FILE.relative_to(REPO_ROOT)}` "
        f"({len(history)} days on record).\n"
    )

    log(f"Fetching {RESEARCH_PAGE_URL}")
    research_html = fetch(RESEARCH_PAGE_URL)
    save_debug_html("research-page", research_html)
    live_dois = set(parse_publications(research_html))

    new_doi_count = 0
    if live_dois:
        known_dois = existing_doi_urls(
            PUBLICATIONS_FILE.read_text(encoding="utf-8") if PUBLICATIONS_FILE.exists() else ""
        )
        new_dois = live_dois - known_dois
        new_doi_count = append_new_publication_stubs(new_dois)
        summary_lines.append("## Research publications page")
        if new_doi_count:
            summary_lines.append(
                f"{new_doi_count} new DOI(s) detected and stubbed into "
                f"`{PUBLICATIONS_FILE.relative_to(REPO_ROOT)}` for a follow-up research pass:"
            )
            for doi in sorted(new_dois):
                summary_lines.append(f"- {doi}")
        else:
            summary_lines.append("No new publication DOIs detected.")
        summary_lines.append("")
    else:
        summary_lines.append(
            f"## Research publications page\nCould not fetch/parse {RESEARCH_PAGE_URL} this run.\n"
        )

    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    (SCRATCH_DIR / "pr-body.md").write_text("\n".join(summary_lines), encoding="utf-8")

    any_change = outbreak_data_changed or new_doi_count > 0
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"changed={'true' if any_change else 'false'}\n")

    log("Done. changed=" + str(any_change))


if __name__ == "__main__":
    main()
