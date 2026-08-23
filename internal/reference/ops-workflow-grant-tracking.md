# Operating plan: grant opportunity discovery + recipient tracking

Status: PROPOSAL — not implemented. For discussion before any of this is built.

## What already exists (deterministic, working today)

- `reference/nws-grand-challenge-tracker.md`: manually maintained list of
  *already-awarded* projects under the USDA NWS Grand Challenge.
- `scripts/rank_projects.py` + `.github/workflows/weekly-project-rankings.yml`:
  weekly, PR-gated re-ranking of that tracker by disclosed award size and an
  information-density proxy. Same never-auto-merge trust model as the
  outbreak-data automation.

This is a **recipient-tracking** pipeline only. It has no view of grant
*opportunities* — solicitations that haven't been awarded yet, or programs
beyond the one Grand Challenge tracker currently covers.

## The gap

Two distinct jobs are currently conflated under "grant tracking" and should
be split:

1. **Opportunity discovery** — is there new funding to know about / apply
   to? (grants.gov postings, USDA-APHIS press releases, other screwworm-
   relevant programs.) Nothing currently watches for this.
2. **Recipient tracking** — who got funded, how much, what are they doing
   with it. (Exists today via `rank_projects.py`, but only for one program.)

## Proposed architecture

```
[Tier 1: Deterministic discovery]  (scheduled GH Actions)
  scrape_grant_opportunities.py
      sources: grants.gov API/search, USDA-APHIS newsroom, any other
      screwworm-program pages you want watched
      diffs against reference/nws-grant-opportunities-tracker.md
      appends new postings as skeleton stubs:
        { id, title, source_url, posted_date, deadline, amount_ceiling,
          status: "new — needs triage" }
      opens a PR (same pattern as scrape_outbreak_data.py) — human review
      gate, never auto-merges

[Tier 2: Local agentic triage]  (runs only on new stubs from Tier 1)
  a local agent is given ONLY the source URL + fetched page text for each
  new stub (no open-web browsing beyond the provided source) and asked to
  fill in what it can actually find on that page: eligibility, deadline,
  topic area, amount. Anything it can't confirm from the source text is
  left as "needs human research" rather than guessed.
  Output: a PR updating the stub's fields. Does not auto-publish to the
  live site — this tracker is an internal/reference doc, same as today.

[Tier 3: Recipient tracking]  (existing — rank_projects.py, unchanged)
  Extend reference/nws-grand-challenge-tracker.md's schema with an
  optional `opportunity_id` field so an awarded project can link back to
  the opportunity that funded it (from Tier 1's tracker), giving
  opportunity → award lineage over time. Pure data-model change, no new
  automation needed.

[Tier 4: Research-brief drafting]  (agentic, gated, opt-in per opportunity)
  For opportunities a human flags as worth a closer look (large ceiling,
  close topical fit, or manually marked "review"), a local agent drafts a
  one-page brief: what the program funds, what related work already
  exists in the recipient tracker, and an initial worth-applying read.
  Written to reference/nws-grant-briefs/<id>.md as a PR. This is drafting
  material for your actual research/decision team to react to and correct
  — it is explicitly not a go/no-go recommendation the agent is trusted to
  make unsupervised.
```

## Why this split matters

- Opportunity discovery (Tier 1) and recipient tracking (Tier 3) are
  different questions with different cadences and different failure modes
  — merging them into one pipeline is why the current tracker can't answer
  "what's coming up" at all. Splitting them lets each stay simple and
  auditable.
- The agentic tiers (2 and 4) are strictly downstream of a human-visible
  PR and strictly bounded to the source text they're handed — same
  guardrail as the reporting workflow in
  `reference/ops-workflow-nws-reporting.md`. No step in this pipeline is
  trusted to invent a dollar figure, deadline, or eligibility rule.
- Nothing here writes to the public site. All of this stays in
  `reference/` as internal tracking, same as the current tracker — the
  live site only reflects grant/recipient info if and when you choose to
  publish a summary of it, which is a separate, later decision.

## Open questions for you before building any of this

1. Beyond grants.gov and USDA-APHIS, which other sources should Tier 1
   watch (state-level TX/NM ag programs? private foundations?)?
2. Who is "the research team" for Tier 4 — is this brief meant for you
   directly, or for other named people who should be pulled in/notified
   when a brief lands?
3. Same infra question as the reporting plan: local Claude Code job vs.
   GitHub Actions step calling the Anthropic API directly for Tiers 2/4?
