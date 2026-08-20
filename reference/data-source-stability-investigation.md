# Data source stability investigation (tracking)

Two follow-up items from the architecture review of the daily/weekly data
automation (DTS-806). Neither is implemented yet — this file tracks scope
and next steps so the work isn't lost between sessions. Each should land
as its own PR when picked up, not bundled together.

## 1. Investigate an ArcGIS/Tableau-backed API for outbreak data

**Problem:** `scripts/scrape_outbreak_data.py` regex-parses static HTML
from the APHIS confirmed-cases page. Case count and county-level data are
rendered client-side and are routinely unparseable from that static HTML
(documented in the script's module docstring). State-name matching works
today via adjacency to "<State> Animal Health Commission" link text, but
that's still fragile to a page redesign.

**Hypothesis (unconfirmed):** USDA/APHIS "current status" dashboards of
this kind are commonly built on an ArcGIS Online/ArcGIS Hub feature layer
or a Tableau embed, and those typically expose a stable, queryable
JSON/REST endpoint (e.g. `.../FeatureServer/0/query?f=json...` or a
Tableau `vizql` data endpoint) even though the wrapping page is
client-rendered.

**Next step:** open the confirmed-cases page in a browser with DevTools
Network tab open, filter to XHR/Fetch, reload, and look for a JSON
response feeding the map/table/case-count widget. If one exists:
- Confirm it's public (no auth/API key required) and has no restrictive
  rate limit or ToS concern for a once-daily poll.
- Record the endpoint URL, query parameters, and response shape here.
- If confirmed, this should replace the case-count/county HTML-regex
  parsing in `parse_confirmed_cases()` entirely — structured JSON, no
  selector fragility.
- Also check whether screwworm.gov (as opposed to aphis.usda.gov) exposes
  a lighter-weight or already-JSON-backed summary, and whether APHIS
  publishes an RSS/press-release feed usable as a corroborating signal.

## 2. Swap grant award amounts to USAspending.gov instead of regex-mining the tracker markdown

**Problem:** `scripts/rank_projects.py`'s `parse_dollar_amount()` regex-mines
prose in `reference/nws-grand-challenge-tracker.md` (a human-written
research log) for dollar figures, and already needed one bugfix (a
denylist) to stop misattributing the ~$105M/40-project program total to
individual projects. This coupling means every future edit to the
tracker's prose is an implicit regex-contract change.

**Proposed fix:** query **api.usaspending.gov** (free, no auth required,
well-documented REST API, authoritative for actual disbursed federal
award data) filtered by awarding agency (USDA/APHIS) and relevant
keyword/CFDA code, to get recipient, obligated/award amount, and dates
directly — no regex needed for the dollar-amount axis.

**Next step:**
- Confirm APHIS Grand Challenge awards are queryable via USAspending
  (try `POST /api/v2/search/spending_by_award/` filtered by awarding
  sub-agency = APHIS and a relevant time period/keyword).
- Design a matching strategy from USAspending award records back to the
  40 project entries in the tracker (likely by recipient name + award
  ID/APP-number, since the tracker already records APP IDs).
- Keep `reference/nws-grand-challenge-tracker.md` as the source for the
  "information density" ranking axis (source count + writeup length) —
  that's explicitly a proxy over the human research log and doesn't need
  to change. Only the award-size axis should move to USAspending.
- grants.gov was considered and rejected as the source for this: it's
  oriented toward pre-award/solicitation data, not post-award disbursed
  amounts, so it's a worse fit than USAspending for this specific need.
