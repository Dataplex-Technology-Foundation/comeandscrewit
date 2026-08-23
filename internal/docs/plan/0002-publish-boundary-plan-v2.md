# Plan 0002 — Publish boundary for comeandscrewit.com (v2)

Status: **REVISED after review.** Supersedes `0001-publish-boundary-plan.md`, which failed
review — see `review-findings.md` for the record.
Date: 2026-08-23
Repository: `Dataplex-Technology-Foundation/comeandscrewit` (single, public)

---

## 1. Problem

GitHub Pages is configured as `build_type: legacy`, `source: {branch: main, path: /}`.

`legacy` is **not** a verbatim copy — it is a **Jekyll build**. That has two consequences v1
got wrong:

- Jekyll **excludes** dot-prefixed paths, so `/.gitignore`, `/.github/workflows/ci.yml` and
  `/CNAME` are 404.
- Jekyll **transforms** markdown, so every internal `.md` is published **twice**: once raw,
  and once as a themed HTML page carrying `<title>`, `og:site_name` and a
  `<link rel="canonical">`.

```
https://comeandscrewit.com/reference/nws-grand-challenge-tracker.html   → 200
<title>USDA APHIS New World Screwworm (NWS) Grand Challenge — Project Tracker | comeandscrewit</title>
<meta name="generator" content="Jekyll v3.10.0" />
<link rel="canonical" href="http://comeandscrewit.com/reference/nws-grand-challenge-tracker.html" />
```

The rendered twins are worse than the raw files: a canonical tag presents internal research to
crawlers as first-class site content.

**Live exposure: 25 URLs** — 19 raw paths + 6 rendered twins. The exposure table is generated
by `scripts/0002_exposure_inventory.sh`, never hand-maintained; v1's hand-written table
undercounted by 46% and its acceptance criterion inherited the error.

A second, independent exposure: `Dockerfile` does `COPY . /usr/share/nginx/html` then `rm -f`
four files. Anyone running `docker compose up` served the same internal material on
`localhost:8093`.

A third, found during review and **more severe than either**: internal editorial notes render
as visible body text on live, indexable pages — see §3.

## 2. Goals

- **G1** No file outside the publish set is reachable on `comeandscrewit.com`.
- **G2** Accidental publication is impossible; deliberate publication requires editing the
  publish workflow itself. *(v1 claimed "structurally impossible" — false; see §8.4.)*
- **G3** The repo layout makes the boundary obvious.
- **G4** Automation is **fixed** — it is currently broken (§4) — and keeps working after the move.
- **G5** The publish path is more secure after the change.
- **G6** Zero downtime, zero content regression, verified by byte-identity.
- **G7** Every action is a re-runnable numbered script in `scripts/`.

## 3. Confirmed decisions

| # | Decision | Note |
|---|---|---|
| D1 | Single **public** repo. Pages source → GitHub Actions publishing `site/`. | Pages requires a public repo on the org's Free plan. |
| D2 | **PR-0 first**: delete internal editorial notes, mechanical `[DOMAIN]` pass. | Zero requester input required. |
| D3 | Enable `can_approve_pull_request_reviews`, **without** branch protection. | Requester's call. Residual risk recorded in §8.4 — declined once, not re-litigated. |
| D4 | **Rewrite history**, keeping one public repo. | Requester accepted the stated trade-off: content stays readable at `internal/`; the rewrite kills old blob URLs and indexed twins, it does not confer confidentiality. |
| D5 | Cutover may proceed without a scheduling window. | |

## 4. Automation is broken right now — fix first

Every scheduled run since 2026-08-21 has failed:

```
##[error]GitHub Actions is not permitted to create or approve pull requests.
```

The scraper succeeds and detects changes; PR creation is refused by
`can_approve_pull_request_reviews: false`. **Fresh outbreak data is fetched and discarded
daily**, on a tracker whose sitemap declares `changefreq: daily`.

v1 blamed a missing `automated-data-refresh` label. That was wrong twice over: labelling is
never reached, and no automated PR has ever existed, so "every automated PR failed to be
labelled" was vacuous. The label is still created (it is referenced by both workflows) but as
housekeeping, not as the fix.

Per D3: `PATCH /repos/.../actions/permissions/workflow {"can_approve_pull_request_reviews": true}`.
If this is enforced at org level the call fails — I cannot read
`orgs/.../actions/permissions/workflow` (403, needs `admin:org`) — and it becomes a requester
action. `0003` reports which.

## 5. Layout

```
site/          ◀── the publish root. This directory IS the Pages artifact.
  *.html (15)  assets/{css,js,data,img}/  favicon.svg  robots.txt
  site.webmanifest  sitemap.xml
internal/      ◀── never published
  automation/  tests/  reference/  container/  docs/{adr,plan}/
scripts/       ◀── numbered operational scripts
.github/workflows/   publish.yml  ci.yml  daily-outbreak-data.yml  weekly-project-rankings.yml
```

`CNAME` is **excluded from the artifact**. Under `build_type: workflow` the custom domain
comes from the Pages API setting; a `CNAME` file is ignored. It is currently 404 (Jekyll
strips it) and shipping it would create a *new* public URL — a regression v1 listed as
"unchanged". `0004` asserts the API `cname` value instead.

The contributor rule: **if it is not under `site/`, it is not on the website.** Stated in a new
root `README.md`, in `CONTRIBUTING.md`, and in the gate's failure message. v1 listed the README
in a table and specified it nowhere, making G3 unverifiable.

### 5.1 Reference resolution

References are **either document-relative or root-absolute**; both resolve identically because
the artifact root remains the domain root. v1 claimed "no absolute-path references" and labelled
it verified — false: `404.html` has 12 and `site.webmanifest` has 3. The property that actually
needs guarding is the absence of `../` traversal (currently zero), which `0008` checks.

Note for future pages: `site-data.js:12` and `outbreak-map.js:41` fetch
`assets/data/outbreak-data.json` document-relative, which is safe only while every page sits at
root depth.

### 5.2 Path constants

All eight constants across the three scripts change — v1 listed five and never named
`refresh-outbreak-data.py` at all:

| File | Constants |
|---|---|
| `rank_projects.py` | `REPO_ROOT`, `TRACKER_FILE`, `RANKINGS_FILE`, `RANKINGS_HISTORY_FILE` |
| `refresh-outbreak-data.py` | `REPO_ROOT`, `DATA_FILE` |
| `scrape_outbreak_data.py` | `REPO_ROOT`, `OUTBREAK_DATA_FILE`, `OUTBREAK_HISTORY_FILE`, `PUBLICATIONS_FILE`, `SCRATCH_DIR` |

`REPO_ROOT = Path(__file__).resolve().parents[2]`, then `SITE_ROOT = REPO_ROOT/"site"`,
`INTERNAL_ROOT = REPO_ROOT/"internal"`. `SCRATCH_DIR` stays at `REPO_ROOT/"scratch"` — matches
the daily workflow's `body-path: scratch/pr-body.md` and `.gitignore`.

Rewrites are anchored to the constant-assignment lines and the two YAML path blocks. **No blind
`sed`** — `weekly-project-rankings.yml` has `reference/...` paths in English prose in the PR
body, and `scrape_outbreak_data.py:52` has a docstring containing quotes.

Also updated, and omitted from v1: `ci.yml`'s `py_compile scripts/*.py` and
`pip install -r tests/requirements.txt`; `daily-outbreak-data.yml`'s
`git diff --quiet -- assets/data reference` and its three `add-paths:` entries;
`weekly-project-rankings.yml`'s `git diff` filter and `add-paths:`.

**Silent-data-loss hazard:** if a `git diff` path filter is missed, it matches nothing,
`changed=false`, no PR opens, scraped data is discarded, **and the job is green**. §11 therefore
asserts a seeded change produces a PR touching exact paths — not merely "runs green".

**Expected first-run diff:** `rank_projects.py:134,194` and `scrape_outbreak_data.py:326,346`
write `relative_to(REPO_ROOT)` strings into generated file *content*. After the move those
become `internal/reference/...`. Pre-declared here so it does not read as a byte-identity
violation.

### 5.3 Container

`COPY site/ /usr/share/nginx/html` replaces the `rm -f` denylist. `Dockerfile:3` also changes to
`COPY internal/container/nginx.conf`. `docker-compose.yml` needs **both** `context: ../..` **and**
`dockerfile: internal/container/Dockerfile` — v1 specified only the first, so `docker compose up`
would have broken while §11's `docker build` criterion still passed. A `.dockerignore` is added;
none exists today, so the whole repo including `.git` currently ships as build context.

**Correction to v1:** `0007` is shared by CI and `publish.yml` only. A Dockerfile `COPY` cannot
invoke a shell script, so the image reproduces the *directory* boundary but not the gate. v1's
"the three consumers cannot disagree" was false in exactly the case the gate exists for. §11
verifies the image tree equals `site/` instead.

## 6. The gate

**Layer 1 — the directory.** `site/` is the artifact. Everything else is absent, not excluded.

**Layer 2 — content checks over `site/`,** run in PR CI and again at publish:

1. **Extension allowlist** (v1 used a denylist — internally contradictory, since v1 §5.3
   indicted the Dockerfile denylist as "the same class of bug", and v1 §8.1 then called its own
   denylist an allowlist). Allowed: `.html .css .js .json .svg .xml .png .jpg .webp .ico
   .webmanifest`, plus `robots.txt` **by exact name** — allowlisting `.txt` would leave the hole
   v1 accepted as residual risk.
2. **Symlink rejection.** `find site/ -type l` must be empty. `upload-pages-artifact` runs
   `tar --dereference --hard-dereference` (verified in its `action.yml:33-38`), so
   `ln -s ../internal site/docs` would publish the entire internal tree — defeating **both**
   layers. Neither v1 layer caught this.
3. **Placeholder tiers** (§7).
4. **Same-origin asset resolution** — every URL in HTML, JSON-LD and the webmanifest must
   resolve to a file in `site/`. Currently fails: 5 referenced images do not exist.
5. **Orphan pages** — every `site/*.html` must be in `sitemap.xml`, or reachable from
   `index.html`, or `noindex` **and** in an explicit `unlinked-pages` allowlist.
6. **Sitemap ↔ robots consistency** — every `<loc>` absolute, resolving to a real file, no
   `noindex` page listed.
7. **No `../` traversal; no `http://` subresources.**

Failure messages name the path, the rule, and the remedy ("move it to `internal/`").

## 7. Placeholders

v1 said 215. Three reviewers measured 229, 234 and 235 with different regexes over different
file sets. **That spread is the finding**: any scalar count is an artefact of its pattern, and
v1's pattern silently missed five token forms. A count is therefore not usable as a baseline.

**Tier A — hard fail, no baseline.** Placeholders in machine-consumed URL contexts:
`rel="canonical"`, `og:url`, `og:image`, `twitter:*`, any `<loc>`, `robots.txt`'s `Sitemap:`,
any `href`/`src`/`action`, any JSON-LD `url`/`logo`/`mainEntityOfPage`. Empty after PR-0 and
empty by construction thereafter.

**Tier B — keyed inventory, may not grow.** A checked-in sorted file of
`(file, normalised-token, count)`. Diffed against the generated inventory. Fix-one-add-one now
fails (new key). Reformatting is immune (no line numbers). Scanned over
`site/**/*.{html,xml,txt,webmanifest,json}` **only** — never CSS or JS, which contain 16
legitimate `[...]` attribute selectors and array literals that would otherwise be false
positives.

Detection: `\[[^\]\n]{2,80}\]` minus an explicit allowlist. Broad by default, because the
narrow pattern is how v1 got it wrong.

## 8. Security

### 8.1 Improvements
1. Publish-everything → publish-one-directory.
2. Container denylist → same directory boundary; `.dockerignore` added.
3. **Enforce HTTPS enabled.** `https_enforced: false` today; `curl -sI http://comeandscrewit.com/`
   returns 200 with no `Location`.
4. Publish job: `contents: read`, `pages: write`, `id-token: write`, `persist-credentials: false`,
   `concurrency: {group: pages, cancel-in-progress: false}`.
5. `github-pages` environment branch policy narrowed — it currently permits `gh-pages`, which
   does not exist.
6. Untrusted HTML parsing (the scraper) runs only in `daily-outbreak-data.yml`, which has no
   `pages:`/`id-token:` scope.
7. SHA-pinning preserved; `sha_pinning_required: true` attempted (best-effort — availability on
   a Free-plan org is unverified, so it is **not** a blocking criterion, unlike in v1).

### 8.2 Corrected claim
v1 said "the credential count after this change is zero." False, and self-contradictory:
`id-token: write` mints a signed OIDC JWT, and `pages: write` is a scope no workflow holds
today. The accurate statement: **no new long-lived secret is introduced; `actions/secrets`
remains 0.**

### 8.3 The accurate guarantee
Not "structurally impossible". **Publishing internal content is impossible by accident, and
impossible at all without editing `publish.yml` or the gate.**

### 8.4 Residual risks
| Risk | Note |
|---|---|
| `publish.yml` / gate editable in one unreviewed commit | `main` has no branch protection and no rulesets. Branch protection was recommended and **declined** (D3). ADR 0001's "no direct commits to `main`" remains unenforced. |
| Workflows can now approve PRs | Consequence of D3 without protection. |
| `.html` carries arbitrary content | `site/internal-notes.html` passes the gate. Accident-resistant, not adversary-resistant. |
| Pages revertible to `legacy` in one API call | `0010` re-runs as a drift check. |
| Content readable at `internal/` after the rewrite | Accepted under D4. |

### 8.5 Observability — v1's biggest omission
v1 rejected the `site`-branch design because "the site goes stale silently", then adopted a
design with the identical failure mode and no alerting. Worse, that failure mode **was already
live and unnoticed for three days** (§4). Added: `publish.yml` and both scheduled workflows get
an `on: failure` notification step, and `0010` is scheduled weekly as a drift check with a named
owner.

## 9. Execution

| PR / step | Contents |
|---|---|
| **PR-0** | Delete 5 internal editorial notes; mechanical `[DOMAIN]` → `comeandscrewit.com` (110 sites); delete `sitemap.xml:2`'s authoring comment. Repairs 14 canonicals, every `og:url`, the sitemap, `robots.txt`. |
| **0003** | Enable Actions PR creation (§4); create `automated-data-refresh` label; narrow the `gh-pages` env policy; fix the stale `homepage` field. |
| **PR-1** | `publish.yml` (+`workflow_dispatch`), gate script, `ci.yml` gate job. Build rule is **pattern-based** (`site/`-equivalent globs), not a per-file manifest — v1's transitional manifest was the exact control v1 §4.1 rejected, and would have silently 404'd any page added during the window. |
| **0004** | Snapshot every public URL + sha256 **(before cutover)**. |
| **0005** | Cutover: `PUT {build_type, cname}` → poll to `status:"built"` → `gh workflow run publish.yml` → `gh run watch` → verify → separate `PUT {https_enforced:true}`. Auto-rollback if the run fails. |
| **PR-2** | `git mv` per §5; path rewrites; Dockerfile/compose; `.dockerignore`; `CONTRIBUTING.md`. |
| **0009** | History rewrite (§10). |
| **post** | New root `README.md` — added *after* the rewrite, so the retroactive rename of the old `README.md` cannot catch it. |

**Ordering is the safety property.** PR-1 + `0005` close the exposure *before* any file moves, so
PR-2 is a refactor with no live-cutover risk. Merging the move under `legacy` would leave `main`
with no root `index.html` and 404 the entire site until cutover.

v1's cutover **produced no deployment at all**: `deploy-pages` hard-fails while Pages is still
`legacy`, and nothing re-triggered the workflow after the API flip. Hence dispatch-and-watch.

`0005 --rollback` **refuses** if `main:site/index.html` exists, printing the `git revert`
instruction — otherwise it would set `legacy`/`main`/`/` on a tree with no root `index.html`.
The `PUT` always sends `cname` explicitly: losing the custom domain means DNS re-verification
and certificate reissue ("up to 24 hours"), not the "~1 min" v1 claimed.

## 10. History rewrite (D4)

Preconditions verified: **0 forks, 0 open PRs**, 2 stale branches
(`automation/outbreak-data-refresh`, `feature/data-source-stability-investigation`).

**Method: full-history `--path-rename`, not deletion.** Deleting the old paths and re-adding at
`internal/` cannot work — git dedupes by content, so the blob at `reference/x.md` and
`internal/reference/x.md` is one object; stripping it would delete the copy being kept. A
retroactive rename makes every commit look as though the file always lived at `internal/`, so
`blob/<old-sha>/reference/...` and the six Jekyll twins' source paths cease to exist.

Constraints:
- Renames are **per-file** for `scripts/*.py`, so the new numbered `scripts/*.sh` are untouched.
- `README.md → internal/docs/deployment.md` is applied to all history; the new root `README.md`
  is therefore committed **after** the rewrite.
- PR-2's pure-rename commit collapses to empty and is pruned; its content edits survive.
- Full mirror backup to `artifacts/` before touching anything; both stale branches re-pointed;
  `--force-with-lease`.

## 11. Acceptance

Run by `0010`. Every criterion is executable.

**Exposure**
- [ ] **No path outside `site/` returns 200** — enumerated from `git ls-files`, probing each path
      and its `.html` twin. Not a prose list; v1's hardcoded 13 could pass with 12 files exposed.
- [ ] `http://comeandscrewit.com/` redirects to `https://`.
- [ ] `pages` API: `build_type: workflow`, `cname: comeandscrewit.com`, `https_enforced: true`,
      `status: built`.
- [ ] Tier-A placeholder count is 0.
- [ ] No commit reachable from `main` contains any purged path.

**No regression**
- [ ] Every URL in the `0004` snapshot returns the same status and **identical sha256**, with
      `/CNAME` declared as a deliberate 404→404.
- [ ] Snapshot URL list = (pre-cutover crawl) ∪ (`find site/ -type f`), so additions are caught.
- [ ] Unknown path → 404 with the custom body.

**Migration**
- [ ] Every moved file byte-identical to its pre-move blob, except the **six** with declared path
      edits: the 3 `.py`, the test, `Dockerfile`, `docker-compose.yml`. (The 3 workflows are
      edited but not moved.)
- [ ] `python3 -m unittest discover -s internal/tests` → 5 tests OK; `git diff` on the test file
      touches only its `sys.path` line.
- [ ] CI green on the **PR-2 head commit** — not "on `main`"; `ci.yml` triggers only on
      `pull_request`.
- [ ] `git log --follow internal/automation/scrape_outbreak_data.py` (and 2 others) resolves.

**Boundary proven**
- [ ] Gate **fails** on a scratch tree containing `site/LEAK-TEST.md`.
- [ ] Gate **fails** on `ln -s ../internal site/docs`.
- [ ] Artifact manifest == `find site/ -type f`.
- [ ] Image tree == `site/` tree.

**Automation**
- [ ] Daily workflow, dispatched against a seeded change, opens a PR touching exactly
      `site/assets/data/*.json` and `internal/reference/screwworm-gov-research-publications.md`.
- [ ] Weekly workflow likewise for `internal/reference/nws-grand-challenge-*`.
- [ ] Both labelled `automated-data-refresh`.

**Known-deferred, must be reported not silently dropped:** WCAG contrast failures
(1.94:1 on `404.html`; `styles.css:12`'s comment asserts a 2.83:1 colour "passes as TEXT"),
`role="img"` on the Leaflet map hiding zoom controls, 17 markers and the OSM attribution,
5 missing image assets, `www.comeandscrewit.com` TLS mismatch, `Article.dateModified` drift,
remaining Tier-B placeholders.
