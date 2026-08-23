#!/usr/bin/env python3
"""
refresh-outbreak-data.py — manual-entry-assisted refresh scaffold for
assets/data/outbreak-data.json.

WHY THIS IS MANUAL-ENTRY-ASSISTED, NOT A SCRAPER (DTS-806):
Per T1's sourcing research (see /tmp .../T1-handoff.json at time of writing,
and the T1 findings folded into this project's notes), none of the three
candidate sources offer a clean, reliably-automatable structured feed as of
this pass:
  - USDA APHIS (screwworm.gov / aphis.usda.gov current-status pages):
    described only via search results as "a current dashboard... updated
    regularly" — direct WebFetch attempts this session hit repeated
    ECONNRESET / 60s timeouts (likely bot/WAF blocking). No API, RSS, or
    data.gov dataset was located. Treated as a scrapeable-bulletin/manual
    source, not an API.
  - CDC (New World Screwworm situation summary): direct WebFetch returned
    HTTP 403 on every attempt this session. CDC's page is also human-health
    (myiasis) focused, secondary to livestock case counts for this project.
  - TAHC (Texas Animal Health Commission veterinary resources): confirmed
    (via what could be fetched) to be a static page with a map IMAGE and
    PDF guidance documents — there is no live HTML table to parse and no
    machine-readable feed.

Given that, this script does NOT scrape any of these pages. It is a
human-in-the-loop assistant: it prints exactly which fields need checking,
against which source URLs, shows the current value, and only writes a new
value after the operator explicitly types the confirmation token for that
field. It is safe to run repeatedly; declining every field is a no-op.

SECURITY / PROCESS CONSTRAINTS (do not remove or bypass these):
  1. No network calls. This script never fetches any URL itself. A human
     must open the source URLs printed below in a browser and read the
     current figures themselves — this avoids relying on scraping of pages
     that already returned ECONNRESET/timeout/403 during automated access
     attempts, and avoids silently publishing a scraped value that could be
     wrong (e.g. stale cache, WAF interstitial page, JS-rendered content).
  2. No value is written to outbreak-data.json without an explicit,
     per-field confirmation token typed by the operator at the prompt
     (default mode). --apply-only-confirmed enforces this even in
     non-interactive/scripted use; there is no flag that forces an
     unconfirmed value through.
  3. This script is NOT registered in any cron table, systemd timer, CI
     workflow, or scheduled task, and must not be added to one as part of
     this task. Scheduling cadence is a recommendation left to T5's
     workflow doc, not implemented here.
  4. Every run that writes changes creates a timestamped backup of the
     previous outbreak-data.json alongside the target file before writing.

USAGE:
  python3 scripts/refresh-outbreak-data.py                # interactive review
  python3 scripts/refresh-outbreak-data.py --dry-run       # show fields/sources only, write nothing
  python3 scripts/refresh-outbreak-data.py --show-sources  # print the per-field source checklist and exit
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = REPO_ROOT / "site"
INTERNAL_ROOT = REPO_ROOT / "internal"
DATA_FILE = SITE_ROOT / "assets" / "data" / "outbreak-data.json"

# Per-field source checklist. Each field names which source(s) a human must
# consult and cross-check before entering a real value. This is descriptive
# metadata only — no URL here is ever fetched by this script.
FIELD_SOURCES = {
    "lastUpdated": {
        "description": "Human-readable date this data snapshot was verified (e.g. \"August 11, 2026\").",
        "sources": ["Set this to today's date once you have verified at least one field below."],
    },
    "usCases": {
        "description": "Confirmed U.S. animal case count.",
        "sources": [
            "USDA APHIS current status: https://www.aphis.usda.gov/animals/animal-health/livestock-and-poultry-disease/current-status",
            "USDA APHIS confirmed cases: https://www.aphis.usda.gov/animals/animal-health/livestock-and-poultry-disease/current-status/us-confirmed-cases-new-world",
            "screwworm.gov (public-facing mirror of APHIS status)",
        ],
    },
    "usStates": {
        "description": "List of affected U.S. state names.",
        "sources": [
            "USDA APHIS current status page (same as usCases).",
        ],
    },
    "usStateCount": {
        "description": "Count of affected U.S. states — must equal len(usStates).",
        "sources": ["Derived from usStates; do not enter independently of that list."],
    },
    "regionAnimalCases": {
        "description": "Mexico & Central America animal case count.",
        "sources": [
            "USDA APHIS current status page (regional summary section, if present).",
            "TAHC veterinary resources (map/PDF): check veterinary.texas.gov New World Screwworm page for regional references.",
        ],
    },
    "regionHumanCases": {
        "description": "Regional human myiasis case count.",
        "sources": [
            "CDC New World Screwworm situation summary: https://www.cdc.gov/new-world-screwworm/situation-summary/index.html",
            "CDC About page: https://www.cdc.gov/new-world-screwworm/about/index.html",
        ],
    },
    "firstUsCase": {
        "description": "Narrative description of first U.S. detection (location + date). Should only change if a new, earlier case is confirmed — verify carefully before editing.",
        "sources": [
            "USDA APHIS news announcement: https://www.aphis.usda.gov/news/agency-announcements/usda-confirms-presence-new-world-screwworm-united-states",
        ],
    },
    "affectedCounties": {
        "description": "List of county names surfaced on status/rancher pages.",
        "sources": [
            "USDA APHIS confirmed cases page (county/state/species breakdown).",
        ],
    },
    "sterilePupaePerWeek": {
        "description": "COPEG facility (Pacora, Panama) weekly sterile pupae production figure.",
        "sources": [
            "USDA APHIS / COPEG program pages — no direct COPEG URL confirmed by T1; search current APHIS program pages for the latest production figure.",
        ],
    },
}

CONFIRM_TOKEN = "APPROVE"


def load_data():
    if not DATA_FILE.exists():
        print(f"ERROR: {DATA_FILE} does not exist.", file=sys.stderr)
        sys.exit(1)
    with DATA_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def print_sources():
    print("Per-field manual-verification checklist (no field is fetched automatically):\n")
    for field, meta in FIELD_SOURCES.items():
        print(f"  [{field}]")
        print(f"    {meta['description']}")
        for src in meta["sources"]:
            print(f"      - {src}")
        print()


def backup_existing():
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = DATA_FILE.with_name(f"outbreak-data.json.bak-{ts}")
    shutil.copy2(DATA_FILE, backup_path)
    return backup_path


def interactive_review(data, apply_only_confirmed=True):
    changed = False
    for field, meta in FIELD_SOURCES.items():
        current = data.get(field)
        print(f"\n--- {field} ---")
        print(f"  Description: {meta['description']}")
        for src in meta["sources"]:
            print(f"  Source: {src}")
        print(f"  Current value: {current!r}")

        new_value_raw = input(
            f"  Enter new value for '{field}' (blank = skip/keep current): "
        ).strip()
        if not new_value_raw:
            print("  Skipped (unchanged).")
            continue

        # usStates / affectedCounties are arrays: accept comma-separated input.
        if isinstance(current, list):
            new_value = [v.strip() for v in new_value_raw.split(",") if v.strip()]
        else:
            new_value = new_value_raw

        confirm = input(
            f"  Type {CONFIRM_TOKEN} to confirm this human-verified value for "
            f"'{field}' (anything else cancels this field): "
        ).strip()

        if apply_only_confirmed and confirm != CONFIRM_TOKEN:
            print("  Not confirmed — value discarded, field left unchanged.")
            continue

        data[field] = new_value
        changed = True
        print(f"  Set {field} = {new_value!r} (pending write).")

    # Keep usStateCount consistent with usStates if usStates was just edited.
    if isinstance(data.get("usStates"), list):
        data["usStateCount"] = str(len(data["usStates"]))

    return data, changed


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the field/source checklist and current values; write nothing.",
    )
    parser.add_argument(
        "--show-sources",
        action="store_true",
        help="Print the per-field source checklist and exit (no data loaded/written).",
    )
    args = parser.parse_args()

    if args.show_sources:
        print_sources()
        return

    data = load_data()

    if args.dry_run:
        print(f"DRY RUN — no writes will occur. Target file: {DATA_FILE}\n")
        print_sources()
        print("Current values:")
        print(json.dumps(data, indent=2))
        return

    print("Outbreak data manual-verification refresh")
    print("=" * 60)
    print(
        "This script does NOT fetch any source itself. For each field below,\n"
        "open the listed source URL(s) in a browser, verify the current\n"
        f"figure yourself, then type {CONFIRM_TOKEN} when prompted to confirm\n"
        "you have personally checked it. Leaving a field blank keeps its\n"
        "current value unchanged. Nothing is written to disk until you\n"
        "finish the review below."
    )

    updated, changed = interactive_review(dict(data))

    if not changed:
        print("\nNo fields were confirmed/changed. Exiting without writing.")
        return

    print("\nPending changes:")
    diff_fields = {k: v for k, v in updated.items() if data.get(k) != v}
    print(json.dumps(diff_fields, indent=2))

    final_confirm = input(
        f"\nWrite these changes to {DATA_FILE.relative_to(REPO_ROOT)}? "
        f"Type {CONFIRM_TOKEN} to write, anything else aborts: "
    ).strip()
    if final_confirm != CONFIRM_TOKEN:
        print("Aborted — no changes written.")
        return

    backup_path = backup_existing()
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2)
        f.write("\n")

    print(f"\nBackup of previous data written to: {backup_path}")
    print(f"Updated data written to: {DATA_FILE}")
    print(
        "\nReminder: this script is not scheduled anywhere (no cron/CI). "
        "Re-run it manually whenever a source needs re-checking."
    )


if __name__ == "__main__":
    main()
