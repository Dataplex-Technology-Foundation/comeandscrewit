# Operating plan: professional NWS case/migration/news reporting

Status: PROPOSAL — not implemented. For discussion before any of this is built.

## What already exists (deterministic, working today)

- `scripts/scrape_outbreak_data.py` + `.github/workflows/daily-outbreak-data.yml`:
  daily fetch of APHIS confirmed-case data, appends to
  `assets/data/outbreak-history.json` (append-only time series), only
  overwrites `outbreak-data.json` fields it actually parsed, opens a PR for
  every change. Never auto-merges.
- `scripts/rank_projects.py` + `.github/workflows/weekly-project-rankings.yml`:
  same PR-gated pattern for grant-recipient rankings.
- Both follow the same trust model: **scripts never push to `main`; a human
  merges the PR.** Any new automation should keep this invariant.

## The gap

The existing pipeline captures *numbers* (case counts, states, counties). It
does not:
- cross-check a number against more than one source before it lands in a PR
- notice when a change is significant (new state, county spike, a trade
  restriction) versus routine
- turn a data delta into a short human-readable narrative for the
  outbreak-status/news copy
- watch anything besides APHIS (no CDC, no TAHC, no Mexico/Canada trade
  actions)

Closing that gap by hand-writing more scraper code only gets you more
numbers, not narrative. Closing it by pointing an LLM at the open web to
"write the outbreak update" reintroduces exactly the fabrication risk this
project has already worked hard to avoid (see the removal of the
`[VERIFY:...]` placeholders in this same branch).

## Proposed architecture: deterministic ingestion + gated agentic synthesis

```
[Tier 1: Deterministic ingestion]  (scheduled GH Actions, existing pattern)
  scrape_outbreak_data.py  (APHIS)          — exists
  scrape_cdc_data.py       (CDC)            — new, same shape
  scrape_tahc_data.py      (TAHC)           — new, same shape
  scrape_trade_actions.py  (Mexico SENASICA / Canada CFIA import notices) — new
      ↓ each appends to its own *-history.json (append-only, source-tagged)

[Tier 2: Deterministic change detection]  (pure code, no LLM)
  diff_outbreak_deltas.py
      reads today's vs. yesterday's history entries
      emits a structured delta object only for real changes:
        { type: "new_county", county: "X", source: "APHIS", date: ... }
        { type: "case_count_change", from: 46, to: 51, source: "APHIS" }
        { type: "trade_action", country: "Canada", action: "...", source: "CFIA" }
      writes nothing if there is no delta — most days this tier is silent

[Tier 3: Local agentic drafting]  (only runs when Tier 2 emits a delta)
  a local agent (Claude Code running as a scheduled/triggered local job,
  not a hosted always-on service) is invoked with ONLY the structured
  delta objects from Tier 2 as input — no open-web browsing, no access to
  write anything except a draft PR.
  Its job:
    - write a 2-4 sentence "what changed" summary, citing only the fields
      it was given (never allowed to add a number that isn't in the delta)
    - propose the corresponding copy edit to outbreak-status.html /
      a future news page as a diff
  Output: opens a PR. Does not merge. Does not touch main.

[Tier 4: Notification]  (deterministic)
  when Tier 2 emits a delta and Tier 3 opens a PR, send one notification
  (Slack webhook or email) so a human knows review is waiting, instead of
  relying on someone checking GH Actions.
```

## Why this split (deterministic vs. agentic) matters

- **Numbers come only from Tier 1/2 (code).** The agent in Tier 3 is never
  the source of a fact — it only rephrases facts it's handed. This is the
  same guardrail already written into `scrape_outbreak_data.py`'s docstring
  ("only overwrites fields where a fresh value was actually parsed") and
  into the placeholder-removal work on this branch (no fabricated regional
  figures). Extending that principle to narrative content, not just numbers,
  is the whole point of this design.
- **The agent only runs on a real delta**, not on a fixed schedule — most
  days there's nothing to say, and saying nothing is correct behavior, not
  a failure.
- **PR-gate stays the single trust boundary.** No new auto-publish path is
  introduced anywhere in this design.

## Open questions for you before building any of this

1. Which additional sources are worth the scraper effort — CDC and TAHC
   specifically, or a narrower/broader set?
2. Is "local agentic" here meant to be Claude Code invoked from a
   scheduled job on infrastructure you control, or should Tier 3 instead
   run as another GitHub Actions step calling the Anthropic API directly?
   Both fit the architecture; the choice affects where credentials live.
3. Do you want a public-facing "News" page at all, or should Tier 3's
   output stay scoped to updating `outbreak-status.html` copy?
4. Notification channel for Tier 4 (Slack webhook / email / other)?
