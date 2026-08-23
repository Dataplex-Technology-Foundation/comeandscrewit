# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A hand-written static site (no generator, no bundler, no build-time dependency) published to
comeandscrewit.com via GitHub Pages, plus the Python automation that keeps its outbreak data
current. Python is used only for automation and its tests — never at request time.

## The one invariant

**If it is not under `site/`, it is not on the website.**

`site/` *is* the GitHub Pages artifact. `.github/workflows/publish.yml` uploads that directory and
nothing else, so everything outside it is **absent from what deploys** rather than excluded from it
by a rule someone could edit. Pages is set to `build_type: workflow`; if it is ever reverted to
`legacy`, GitHub runs Jekyll over the whole branch and republishes every file in the repo — which
is the defect this layout exists to prevent. `scripts/0009` detects that reversion.

Corollary worth internalising: adding a file under `internal/` or `scripts/` is safe by
construction. Adding one under `site/` is a publishing decision.

## Commands

```sh
# Gate the publish boundary. Run before pushing anything that touches site/.
python3 scripts/0005_build_site_artifact.py --check

# Build the artifact locally (what publish.yml uploads)
python3 scripts/0005_build_site_artifact.py --out _site

# Tests
python3 -m unittest discover -s internal/tests
python3 -m unittest internal.tests.test_scrape_outbreak_data.ParseConfirmedCasesTests.test_county_requires_state_adjacency_not_bare_mention

# What is live that should not be, and where every tracked path belongs
scripts/0002_exposure_inventory.sh --exposure
scripts/0002_exposure_inventory.sh --disposition

# Full acceptance / drift check (safe, read-only, re-runnable)
scripts/0009_verify_final_state.sh [--skip-docker]

# Local preview — image copies site/ only, so what you see is what publishes
docker compose -f internal/container/docker-compose.yml up --build   # :8093

# Run automation by hand
python3 internal/automation/scrape_outbreak_data.py     # network; writes site/ + internal/
python3 internal/automation/rank_projects.py            # offline; writes internal/reference/
```

`scripts/nnnn_name.ext` is the convention for operational scripts: numbered in execution order,
idempotent, `--check`/`--dry-run` where they mutate. New ones continue the sequence.

## Architecture

### The gate (`scripts/0005_build_site_artifact.py`)

Single source of truth for what is publishable, called by **both** `ci.yml` (at review time) and
`publish.yml` (at deploy time), so the two cannot disagree. It auto-detects the publish root:
`site/` if present, otherwise pattern-selected from the repo root (a transitional mode kept so the
script still works against pre-reorg commits).

Layer 1 is the directory. Layer 2 catches what a directory cannot — internal content misfiled
*into* it:

- **extension allowlist**, not a denylist. `robots.txt` is allowlisted by exact name; allowing
  `.txt` would readmit notes-in-a-text-file.
- **symlink rejection.** `upload-pages-artifact` runs `tar --dereference --hard-dereference`, so
  `ln -s ../internal site/docs` would publish the whole target. This defeats *both* layers
  otherwise: layer 1 sees a path inside the root, the extension check sees no extension. The
  publish root is tested for being a symlink *separately*, because `find site/ -type l` (trailing
  slash) dereferences its own start point.
- **placeholder tiers** (below), same-origin reference resolution, sitemap↔robots consistency,
  no `../` traversal, no `http://` subresources.
- **`check_jekyll_exclusions()`** only fires in transitional mode and is inert now.

`ci.yml` additionally **proves on every PR that the gate still rejects its four known bypasses**.
If you change the gate, keep those proofs meaningful — they went stale once when the layout moved
and passed vacuously.

### Placeholders — two tiers, no scalar counts

The site ships unreplaced `[TOKEN]` placeholders awaiting content the owner has not supplied.

- **Tier A** — machine-consumed URLs (`rel=canonical`, `og:url`, `og:image`, `twitter:*`, `<loc>`,
  `robots.txt` `Sitemap:`, JSON-LD `url`/`logo`/`mainEntityOfPage`). Hard fail, no baseline,
  currently empty. Matched on **values only**, never whole lines — `[OG IMAGE]` sits in a comment
  on the `og:image` line and `[SOCIAL LINK]` shares a line with JSON-LD `url` in most files.
- **Tier B** — prose placeholders. Keyed `(file, token, count)` inventory in
  `internal/publish/placeholder-baseline.txt`, may not grow. Never scan CSS or JS: they contain 17
  legitimate `[...]` attribute selectors and array literals.

A scalar total is deliberately not used anywhere — three reviewers measured 229/234/235 for the
same site with different regexes. `internal/publish/unresolved-refs-baseline.txt` ratchets broken
same-origin references the same way — 16 entries covering 3 distinct missing images
(`og-default.png`, `icon-192.png`, `icon-512.png`).

Known gap: a fourth image, `logo.png`, is also missing but is referenced only from JSON-LD, which
`check_references()` does not walk — it reads `href`/`src` and URL-bearing `<meta content>` plus
the webmanifest. Widening it to JSON-LD `logo`/`image` would catch that, and would need the
baseline regenerating.

### Automation crosses the boundary

`internal/automation/*.py` derive paths from `REPO_ROOT = Path(__file__).resolve().parents[2]`,
then `SITE_ROOT = REPO_ROOT/"site"` and `INTERNAL_ROOT = REPO_ROOT/"internal"`. The daily scraper
writes to **both** sides: `site/assets/data/*.json` (published, rendered by
`site/assets/js/outbreak-map.js`) and `internal/reference/*.md` (never published). When moving
these files, rewrite **constant-assignment lines only** — a blind `sed` also hits path strings
inside docstrings and workflow PR-body prose.

Both scheduled workflows have `git diff` path filters and `add-paths:` blocks. A missed path there
fails **silently and green**: the diff matches nothing, `changed=false`, no PR opens, scraped data
is discarded. Verify by seeding a change and asserting a PR touching exact paths — never by "the
job ran green".

## Known-broken

**Actions cannot open pull requests.** An *organisation*-level policy blocks it:

```
409 Conflict — "The organization does not allow GitHub Actions to create or approve pull requests"
```

The daily outbreak refresh scrapes successfully, detects changes, then discards them — it has
failed every scheduled run since 2026-08-21. No change in this repo fixes it; it needs an org owner
at the org's Actions settings. `scripts/0009` reports this as BLOCKED rather than failing.

## Conventions

- **[ADR 0001](internal/docs/adr/0001-branch-pr-and-issue-workflow.md): no direct commits to
  `main`.** Branch `<type>/<short-description>`, PR, reference the issue, CI green before merge.
  Nothing enforces this — there is no branch protection and no rulesets (offered and declined).
- Every `uses:` is pinned to a full commit SHA with the tag in a trailing comment. CI enforces it
  by grep. Do **not** re-enable the repo's `sha_pinning_required` setting: it also applies to
  first-party composite actions' internal references, and `upload-pages-artifact@v3` depends on
  `upload-artifact@v4` unpinned — it breaks every Pages deploy.
- pip dependencies pinned to exact versions, deliberately.
- Update `<lastmod>` in `site/sitemap.xml` when editing a page.

## Gotchas that have already caused incidents here

- **Regex over HTML with a lookahead.** A lazy quantifier expands to satisfy a trailing lookahead,
  so one heading match swallowed the entire homepage hero. It passed tag-balance and
  token-absence assertions. `scripts/0003` now asserts no visitor-facing prose disappears
  unaccounted for — keep that class of check on any content-mutating script, and prefer line- or
  structure-based edits over whole-document regex.
- **Hashing a response body via command substitution strips its trailing newline.** Pipe `curl`
  straight into `sha256sum` on both sides of a comparison, or every file reads as changed.
- **`read` strips leading IFS whitespace**, so an empty first TSV field shifts every column left.
- **Checks that consult `git ls-files` must fail closed** if it returns nothing — otherwise they
  pass by asserting nothing.

## Where the reasoning lives

`internal/docs/plan/0003-publish-boundary-plan.md` is the current design;
`internal/docs/plan/review-findings.md` records what three independent reviews found in the
earlier drafts and why decisions went the way they did (notably: why there is a single public repo,
and why the git-history rewrite was abandoned — `refs/pull/*/head` are server-owned and keep every
old commit fetchable regardless). `internal/docs/removed-content-inventory.md` lists content
removed from the live site verbatim, with restoration snippets.
