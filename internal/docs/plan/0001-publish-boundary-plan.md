# Plan 0001 — Establish a hard publish boundary for comeandscrewit.com

Status: **DRAFT — pending critical content + critical architecture review**
Date: 2026-08-23
Repository: `Dataplex-Technology-Foundation/comeandscrewit` (single repo)
Supersedes: an earlier two-repository draft, withdrawn — see §4.

---

## 1. Problem

`comeandscrewit.com` is served by GitHub Pages configured as:

```json
{"build_type": "legacy", "source": {"branch": "main", "path": "/"}, "cname": "comeandscrewit.com"}
```

`build_type: legacy` with `path: /` publishes **every file on `main` verbatim**. There is no build
step, no allowlist, and no exclusion. Confirmed live by `scripts/0001_investigate_source_repo.sh`
(baseline captured 2026-08-23):

| Live URL | Status | What it discloses |
|---|---|---|
| `/README.md` | 200 | Deployment runbook, host topology, TLS-termination notes |
| `/Dockerfile` | 200 | Container build |
| `/docker-compose.yml` | 200 | Port mapping, container naming |
| `/nginx.conf` | 200 | Full server routing, cache policy, `server_name` |
| `/docs/adr/0001-branch-pr-and-issue-workflow.md` | 200 | Internal process |
| `/reference/nws-grand-challenge-tracker.md` | 200 | 583 lines of funding-opportunity research |
| `/reference/nws-grand-challenge-rankings.md` | 200 | Derived competitor rankings |
| `/reference/ops-workflow-grant-tracking.md` | 200 | Internal operating procedure |
| `/reference/ops-workflow-nws-reporting.md` | 200 | Internal operating procedure |
| `/scripts/rank_projects.py` | 200 | Scoring heuristics |
| `/scripts/scrape_outbreak_data.py` | 200 | Upstream endpoints, parse-failure detection |
| `/tests/test_scrape_outbreak_data.py` | 200 | Known-bug regressions, internal ticket ref `DTS-806` |
| `/assets/img/README.md` | 200 | Asset guidance |

Nothing here is a credential — the repo has zero Actions secrets and zero variables. What leaks is
internal operating material and deployment topology.

**Deleting these files fixes today's thirteen URLs and nothing else.** Under `legacy` build, the next
`.md` or `.py` committed to `main` is published the instant it lands. The publishing mechanism is the
defect; the files are only its current symptom.

## 2. Goals

- **G1** — No file that is not deliberately part of the website is reachable on `comeandscrewit.com`.
- **G2** — That guarantee is **structural**, not procedural: a contributor must not be able to publish
  internal content by accident, and must not have to remember a rule to avoid it.
- **G3** — The repository's own layout makes the published/internal boundary obvious on sight.
- **G4** — Workflows, automation, tests, and container config live on the internal side of that
  boundary and continue to work unchanged in behaviour.
- **G5** — The build/publish path is no less secure after the change, and preferably more.
- **G6** — Zero downtime and zero content regression on `comeandscrewit.com`.
- **G7** — Every investigative, migratory, and verification action is a re-runnable numbered script in
  `scripts/nnnn_name.ext`.

## 3. Non-goals

- **NG1** — Rewriting git history. See §9.1.
- **NG2** — Changing site copy, design, or markup. Three live content defects were found during
  investigation; they are reported in §9.2–§9.3 as scoped follow-ups, not folded in here.
- **NG3** — Moving off GitHub Pages, or introducing a static-site generator, bundler, or any
  build-time dependency. The site stays hand-written static HTML.
- **NG4** — Making the repository private. Not possible: the org is on the Free plan, and GitHub Pages
  requires a public repository below Pro/Team/Enterprise.

## 4. Architecture decision, and why the two-repo split was withdrawn

The request began as "split into a second repository." That draft was written, then withdrawn after
the requester asked whether a single repository could achieve the same thing. It can, and better.

The decisive facts:

1. **The site repo must stay public regardless** (NG4). A private repo cannot serve Pages on this plan.
2. **A second repo would not have hidden the existing content anyway.** Deleting files from `main`
   leaves them fetchable at `github.com/.../blob/<old-sha>/...` for the life of the public repo. Only
   a history rewrite changes that, and that is NG1.
3. **The two-repo design cost real security surface to buy that non-benefit**: a GitHub App private
   key held as a long-lived secret, a cross-repo installation token with `Contents: write` on the
   public site repo, a two-job split of the daily scraper to keep that token away from untrusted HTML
   parsing, permission mirroring, four collaborator invitations, and a `SITE_ROOT` refactor of three
   scripts.

Single-repo with a publish boundary achieves G1 and G2 in full while **eliminating every credential
the split would have introduced**. Fewer moving parts is the security argument here, not just the
convenience one.

### 4.1 Why a directory boundary, not a file manifest

Two single-repo shapes were considered:

| Shape | Assessment |
|---|---|
| Pages source → a generated `site` branch | Works, but is strictly more machinery for the same guarantee: a generated branch to keep in sync, a force-push, and branch protection on `site` so nobody hand-commits to it. If the sync workflow breaks, the site goes stale silently rather than loudly. Rejected. |
| Pages source → GitHub Actions, publishing the `site/` **directory** | Chosen. One branch, no generated commits, nothing to keep in sync. |
| Pages source → GitHub Actions, publishing a **file manifest** | Rejected as the primary control: a per-file list drifts. Add a page, forget the manifest, get a silent 404. A directory boundary needs no maintenance — new pages just work. |

**The directory is the control.** `site/` is the publish root; the workflow uploads it as the Pages
artifact. Everything outside `site/` is unpublishable because it is not in the artifact at all — not
excluded by a rule that could be edited, simply absent.

### 4.2 The second layer: a content gate inside `site/`

A directory boundary alone still allows a stray `site/NOTES.md` to publish. So the publish workflow
runs a gate over `site/` before upload, and fails the build on:

- **Extension denylist** — `.md`, `.py`, `.sh`, `.yml`, `.yaml`, `.toml`, `.ini`, `.env`, `.pem`,
  `.key`, `.sql`, `.log`, `.bak`, `Dockerfile`, `*.conf`, dotfiles other than an explicit allowlist.
- **Placeholder ratchet** — unreplaced `[TOKEN]` placeholders (see §9.2) may not increase against a
  committed baseline.

Layer 1 (directory) is structural and cannot be bypassed by a bad commit. Layer 2 (gate) catches the
one thing layer 1 cannot: internal content misfiled *into* `site/`. Both run in PR CI too, so the
failure is visible at review time rather than at deploy time.

## 5. Target layout

```
comeandscrewit/
├── site/                        ◀── THE PUBLISH ROOT. This directory, and only this
│   ├── index.html                   directory, becomes comeandscrewit.com.
│   ├── 404.html  about.html  contact.html  donate.html  faq.html
│   ├── for-ranchers.html  new-world-screwworm.html  our-approach.html
│   ├── outbreak-status.html  partners-and-investors.html
│   ├── screwworm-in-cattle.html  screwworm-in-pets-and-humans.html
│   ├── sterile-insect-technique.html  take-action.html
│   ├── CNAME  favicon.svg  robots.txt  site.webmanifest  sitemap.xml
│   └── assets/{css,js,data,img}/
│
├── internal/                    ◀── Never published. Not in the artifact.
│   ├── automation/              (was scripts/*.py)
│   ├── tests/                   (was tests/)
│   ├── reference/               (was reference/)
│   ├── container/               (was Dockerfile, nginx.conf, docker-compose.yml)
│   └── docs/
│       ├── adr/                 (0001 migrated, 0002 new)
│       ├── plan/                (this document)
│       ├── deployment.md        (was README.md)
│       └── image-assets.md      (was assets/img/README.md)
│
├── scripts/                     ◀── Numbered operational scripts (G7). Never published.
├── .github/workflows/           ◀── publish, ci, daily-outbreak-data, weekly-project-rankings
├── README.md                    ◀── new: repo orientation. Never published.
└── .gitignore
```

The rule a contributor has to learn is one sentence: **if it is not under `site/`, it is not on the
website.** That is G3.

### 5.1 URL stability

Under Actions-based publishing the artifact root becomes the site root, so `site/index.html` serves at
`/index.html`, `site/assets/css/styles.css` at `/assets/css/styles.css`, and so on. **Every public URL
is unchanged.** Verified precondition: every `href`/`src` in the site is repo-relative
(`assets/css/styles.css`, `faq.html`) with no absolute-path or cross-directory references, so moving
the tree wholesale cannot break a link.

### 5.2 Path changes in migrated code

`internal/automation/*.py` currently derive paths from
`REPO_ROOT = Path(__file__).resolve().parent.parent`. At the new depth that resolves to `internal/`,
not the repo root, so it must become explicit:

```python
REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = REPO_ROOT / "site"
INTERNAL_ROOT = REPO_ROOT / "internal"

OUTBREAK_DATA_FILE    = SITE_ROOT / "assets" / "data" / "outbreak-data.json"
OUTBREAK_HISTORY_FILE = SITE_ROOT / "assets" / "data" / "outbreak-history.json"
PUBLICATIONS_FILE     = INTERNAL_ROOT / "reference" / "screwworm-gov-research-publications.md"
RANKINGS_FILE         = INTERNAL_ROOT / "reference" / "nws-grand-challenge-rankings.md"
SCRATCH_DIR           = REPO_ROOT / "scratch"
```

`internal/tests/` adjusts its `sys.path` insert from `parent.parent / "scripts"` to
`parent.parent / "automation"`. No test logic changes — the tests exercise pure HTML-parsing
functions and must keep passing byte-identically, which is the migration's correctness check.

The three workflows update their path references: `scripts/` → `internal/automation/`, `tests/` →
`internal/tests/`, `assets/data` → `site/assets/data`, `reference` → `internal/reference`. Their
triggers, permissions, concurrency groups, and SHA-pinned action versions are unchanged.

### 5.3 The container build is rebuilt, not moved

`Dockerfile` currently does `COPY . /usr/share/nginx/html` and then `rm -f` four known files. That is
a **denylist, and it has the same bug as the Pages config** — it shipped `README.md`, `docs/`,
`reference/`, `scripts/`, and `tests/` into the image. Anyone who ran `docker compose up` was serving
the internal material on `localhost:8093`. This is a second, previously unnoticed instance of the
exposure, and it is fixed by the same boundary:

```dockerfile
COPY site/ /usr/share/nginx/html
```

No `rm` list, nothing to keep in sync. `nginx.conf` is unchanged. `docker-compose.yml` moves to
`internal/container/` and sets `context: ../..` so the build context is the repo root.

## 6. Disposition of every existing path

| Current | Becomes | Published after? |
|---|---|---|
| 15 × `*.html` | `site/*.html` | **yes** (unchanged URLs) |
| `assets/{css,js,data}/*` | `site/assets/...` | **yes** (unchanged URLs) |
| `assets/img/` | `site/assets/img/` | **yes** (empty; see below) |
| `CNAME`, `favicon.svg`, `robots.txt`, `site.webmanifest`, `sitemap.xml` | `site/...` | **yes** |
| `README.md` | `internal/docs/deployment.md` | no |
| `assets/img/README.md` | `internal/docs/image-assets.md` | no |
| `docs/adr/0001-*.md` | `internal/docs/adr/0001-*.md` | no |
| `reference/*` (6 files) | `internal/reference/*` | no |
| `scripts/*.py`, `scripts/requirements.txt` | `internal/automation/*` | no |
| `tests/*` | `internal/tests/*` | no |
| `Dockerfile`, `nginx.conf`, `docker-compose.yml` | `internal/container/*` | no |
| `.github/workflows/{ci,daily-outbreak-data,weekly-project-rankings}.yml` | same path, paths inside updated | no |
| `.gitignore` | unchanged | no |
| — | `README.md` (new, repo orientation) | no |
| — | `.github/workflows/publish.yml` (new) | no |
| — | `scripts/00NN_*.sh` (new) | no |
| — | `internal/docs/adr/0002-*.md`, `internal/docs/plan/0001-*.md` (new) | no |

Nothing is deleted. Every file is moved or kept; all moves use `git mv` so history and `--follow`
blame survive.

`assets/img/` holds only its README today, so after the move it is empty. Git cannot track an empty
directory; `site/assets/img/.gitkeep` preserves it, and `.gitkeep` is on the gate's dotfile allowlist.

## 7. Execution

Two pull requests. **The ordering is the safety property**, and it is the opposite of the obvious one.

### PR-1 — Publish boundary (closes the exposure)

Adds `.github/workflows/publish.yml`, the gate script, and the docs. `publish.yml` at this stage
builds `_site/` from an explicit list of the **current, un-moved** root paths. Nothing moves yet.

After merge, `scripts/0004_cutover_pages.sh` flips Pages to `build_type: workflow` and enables
Enforce HTTPS.

**At this moment all thirteen URLs in §1 return 404**, with the repository layout still exactly as it
is today.

### PR-2 — Layout reorganisation

`git mv` everything per §6, repoint `publish.yml` at `site/`, update the three workflows and three
scripts, rebuild the Dockerfile. Public output is byte-identical; §11 proves it.

### Why not one PR?

Because the two changes must not land together. If the move and the publish switch merged as one
commit, there would be a window between merge and cutover in which the still-`legacy` build published
the *new* root — no `index.html` at top level, so **the entire site 404s** until the cutover lands.
Splitting them means Pages is already publishing from a controlled artifact before any file moves, so
PR-2 is a no-risk refactor rather than a live cutover.

Every boundary is a working state:

| After | Site | Exposure | Automation |
|---|---|---|---|
| PR-1 merge | unchanged | unchanged | unchanged |
| 0004 cutover | unchanged | **closed** | unchanged |
| PR-2 merge | unchanged | closed | on new paths |

### Scripts

| # | Script | Does | Mutates |
|---|---|---|---|
| 0001 | `0001_investigate_source_repo.sh` | Baseline recon + live exposure probe | nothing ✅ done |
| 0002 | `0002_build_site_artifact.sh` | The build+gate itself. Called by CI, `publish.yml`, and humans. Single source of truth for what publishes. | nothing |
| 0003 | `0003_prepare_publish_pipeline.sh` | Compose PR-1, open it | GitHub |
| 0004 | `0004_cutover_pages.sh` | `build_type: workflow`, Enforce HTTPS, verify, `--rollback` flag | GitHub |
| 0005 | `0005_capture_site_snapshot.sh` | Fetch + checksum every public URL, for before/after diffing | nothing |
| 0006 | `0006_reorganize_layout.sh` | All `git mv`s + path rewrites, idempotent | local |
| 0007 | `0007_verify_migration.sh` | Byte-parity of moved files, test suite, gate, artifact tree | nothing |
| 0008 | `0008_prepare_layout_pr.sh` | Compose PR-2, open it | GitHub |
| 0009 | `0009_verify_final_state.sh` | Full §11 acceptance re-probe; re-runnable as a drift check | nothing |

`0002` being shared by CI, the deploy workflow, and the container build is deliberate: one
implementation of "what is publishable" means the three consumers cannot disagree.

### Rollback

| Fails at | Action | Blast radius |
|---|---|---|
| PR-1 | Close the PR | none — nothing reached `main` |
| 0004 | `0004_cutover_pages.sh --rollback` restores `legacy`/`main`/`/` in ~1 min | one deploy cycle; `main` is untouched because PR-2 has not run |
| PR-2 | Close the PR, or `git revert` after merge | none — layout only; `0004` already guarantees only `site/` publishes |
| 0006 | Re-runnable; `git reset --hard` the branch | local only |

## 8. Security

### 8.1 Improvements

1. **Publish-everything replaced by publish-one-directory.** Recurrence becomes structurally
   impossible rather than merely unlikely (G2).
2. **The container denylist is replaced by the same allowlist** (§5.3), closing a second live
   instance of the exposure that nobody had noticed.
3. **Enforce HTTPS turned on.** Pages currently reports `https_enforced: false`, so plain
   `http://comeandscrewit.com` is served without redirect. `0004` fixes this. *Independent live
   finding, unrelated to the split.*
4. **Least-privilege publish job.** `publish.yml` runs `contents: read`, `pages: write`,
   `id-token: write` and nothing else, with `persist-credentials: false` on checkout. It holds no
   secret and touches no untrusted input.
5. **Action pinning enforced by the platform.** The repo already pins every `uses:` to a commit SHA
   with the tag in a comment — good discipline that currently depends on reviewer attention.
   `0003` additionally sets `sha_pinning_required: true` on the repo so the platform enforces it.
   The three new Pages actions (`configure-pages`, `upload-pages-artifact`, `deploy-pages`) are
   pinned the same way.
6. **Untrusted input never meets the publish credential.** The scraper parses attacker-influenceable
   remote HTML, but it runs in `daily-outbreak-data.yml`, which cannot deploy. `publish.yml` is the
   only job that can reach Pages and it parses nothing external. This separation is free under
   single-repo; the two-repo design would have had to engineer it.

### 8.2 Deliberately unchanged

- Exact-pinned pip dependencies (`requests==2.32.5`, `beautifulsoup4==4.14.3`, `lxml==6.1.0`,
  `pyyaml==6.0.3`).
- `default_workflow_permissions: read`, `can_approve_pull_request_reviews: false`.
- The daily/weekly workflows keep `contents: write` + `pull-requests: write`, exactly as today.
- The site remains static HTML/CSS/JS with no build-time code execution.

### 8.3 Not introduced

No new secret, no new token, no new third-party action beyond the three first-party Pages actions, no
new external service. The credential count after this change is **zero**, the same as before.

### 8.4 Residual risks

| Risk | Severity | Mitigation |
|---|---|---|
| Internal file misfiled into `site/` | Low | Gate fails the build and the PR (§4.2) |
| Someone reverts Pages to `legacy` | Low | ADR 0002 records the constraint; `0009` re-runs as a drift check |
| Existing content remains in public git history | Accepted | §9.1 — requester decision |
| Gate denylist misses a novel internal file type | Low | Denylist is by extension; a `.txt` of notes under `site/` would pass. Accepted: the directory boundary means it has to be *deliberately* misfiled. |

## 9. Findings requiring a decision

### 9.1 Git history retains the exposed content — needs explicit accept

Removing the files from the published artifact stops them being served, and PR-2 moves them out of
the site tree, but they remain at `github.com/.../blob/<old-sha>/reference/...` and in every existing
clone, because the repo is and must remain public (NG4).

**Recommendation: accept, do not rewrite.** The material is internal-operational — grant-tracking
research, process docs, deployment topology, scraper heuristics. It contains no credentials, no
personal data, and nothing not reconstructible from public sources. A rewrite would break every
clone and every existing PR ref, and rewrite the merge commits of eight merged PRs, for a benefit
limited to content that has already been publicly served for weeks and is likely already crawled.

**If any of it is genuinely sensitive, say so and a rewrite is planned separately as script 0010.**

### 9.2 The live site ships 215 unreplaced placeholders — serious, and out of scope

Found while verifying that no site file references internal paths:

| Token | Occurrences | Impact |
|---|---|---|
| `[DOMAIN]` | 96 | In `<link rel="canonical">` and Open Graph `og:url` on all 15 pages, in `sitemap.xml` (13), and in `robots.txt` (1) |
| `[SOCIAL LINK]` | 70 | Dead `href="[SOCIAL LINK]"` anchors in every page footer |
| `[COMPANY NAME]` | 15 | Rendered as literal text to visitors |
| `[OG IMAGE]` | 14 | Broken social-share previews |
| `[ANALYTICS ID]` | 14 | Analytics non-functional |
| `[PAYMENT PROCESSOR EMBED]`, `[FORM ENDPOINT]`, `[PARTNER EMAIL]`, `[PARTNERS]`, `[PLACEHOLDER]`, `[CONFIRM CAPABILITY CLAIMS]` | 6 | Donate and contact paths visibly incomplete |

Two consequences worth stating plainly:

- **`sitemap.xml` is entirely non-functional.** All 13 `<loc>` values read `https://[DOMAIN]/...`,
  which is not a valid URL, and `robots.txt` advertises that sitemap. Search engines cannot use it.
- **Every page declares a canonical URL of `https://[DOMAIN]/<page>.html`**, which actively harms
  indexing for a public-awareness site whose purpose is reach.

This is exactly the class of defect a pre-publishing gate exists to catch, which is why §4.2 includes
the placeholder ratchet. But the gate cannot start in blocking mode against 215 existing hits, so it
ships with a committed baseline and fails only on an **increase** — a ratchet, not a wall.

**Fixing the placeholders is deliberately not in this plan** (NG2): `[DOMAIN]` → `comeandscrewit.com`
is mechanical and safe, but `[COMPANY NAME]`, `[SOCIAL LINK]`, `[ANALYTICS ID]`, `[OG IMAGE]`, and the
donate/contact endpoints need answers only the requester has. Recommend a follow-up PR immediately
after; the mechanical `[DOMAIN]` pass alone would repair the sitemap and all canonicals and can ship
within the hour if wanted.

### 9.3 The `automated-data-refresh` label does not exist

Both scheduled workflows pass `labels: automated-data-refresh` to `peter-evans/create-pull-request`,
but the repo carries only the ten GitHub defaults. The label has never existed, so every automated PR
to date failed to be labelled. `0003` creates it. *Pre-existing bug, fixed in passing.*

### 9.4 `sitemap.xml` omits two published pages

`donate.html` and `partners-and-investors.html` are live but absent from the sitemap (`404.html`
correctly is). Worth folding into the §9.2 follow-up.

## 10. What is required from the requester

Materially less than the two-repo plan, which needed a GitHub App, a private key, and four
collaborator invitations. That is all gone.

| # | Action | Why I cannot do it | Effort |
|---|---|---|---|
| **R1** | **Confirm §9.1** — the migrated content is not sensitive enough to warrant a history rewrite. | Judgement about your material. | ~1 min |
| **R2** | **Confirm the cutover window.** `0004` flips the live domain's build type. Expect one deploy cycle, typically under two minutes, in which a request could hit a stale edge cache. Name a bad time if there is one. | Your call on timing. | ~1 min |
| **R3** | **Optional, recommended** — say whether to queue the §9.2 `[DOMAIN]` fix as an immediate follow-up PR. | Scope decision. | ~1 min |

Nothing else. Repo settings, both PRs, the cutover, and all verification run under the existing
`dts-dataplex` admin token. No new credential is created at any point.

Execution holds after `0002`/`0003` are written and before PR-1 is opened, pending R1 and R2.

## 11. Acceptance criteria

`scripts/0009_verify_final_state.sh` must show all of the following.

**Exposure closed**
- [ ] All 13 URLs in §1 return **404**.
- [ ] `http://comeandscrewit.com/` redirects to `https://`.
- [ ] `gh api repos/.../pages` reports `build_type: workflow`, `cname: comeandscrewit.com`,
      `https_enforced: true`, `status: built`.

**No regression** — the bar is byte-identity, not "looks fine"
- [ ] All 15 HTML pages, `robots.txt`, `sitemap.xml`, `site.webmanifest`, `favicon.svg`, all three JS
      files, `styles.css`, and both `assets/data/*.json` return **200**.
- [ ] An unknown path returns 404 with the custom `404.html` body.
- [ ] For every public URL, the `sha256` of the response body is **identical** to the pre-cutover
      snapshot captured by `0005`. Any difference must be explained, not waved through.

**Migration complete**
- [ ] Every moved file is **byte-identical** to its pre-move original (`sha256sum` comparison against
      the `main` blob), except the six files with declared path edits.
- [ ] `python3 -m unittest discover -s internal/tests` passes, unmodified in substance.
- [ ] CI green on `main`.
- [ ] `git log --follow` resolves history across the moves.

**Boundary proven, not asserted**
- [ ] `0002` run against a scratch tree containing `site/LEAK-TEST.md` **fails**, and the branch is
      discarded without merging.
- [ ] The uploaded Pages artifact's file list is exactly the `site/` tree — asserted by comparing the
      artifact manifest to `find site/ -type f`, not by inspection.
- [ ] `docker build` from `internal/container/Dockerfile` produces an image whose
      `/usr/share/nginx/html` contains no `.md` and no `.py`.

**Hygiene**
- [ ] `automated-data-refresh` label exists.
- [ ] `sha_pinning_required: true`; every `uses:` still SHA-pinned with its tag in a comment.
- [ ] `default_workflow_permissions: read` unchanged.
- [ ] Both scheduled workflows run green via `workflow_dispatch` on the new paths, and their PRs touch
      only the expected files.
