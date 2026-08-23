# Review record — Plan 0001 v1

Date: 2026-08-23
Reviewers: three independent, no shared context
- **R-ARCH** — deployment architecture
- **R-CONTENT** — web content, SEO, accessibility
- **R-CLAIMS** — specification and claims audit

## Verdict: **FAILED.** v1 must not be executed.

The architecture survived. The document did not. Between them the reviewers found
**6 blocking defects in the mechanism**, **9 verified-false factual claims**, **3 internal
contradictions**, **1 acceptance criterion the plan forbids itself from meeting**, and
**1 live disclosure more severe than the one the plan was written to fix**.

Every finding below was re-verified against live state before acceptance. Findings the
reviewers got wrong are recorded in §5.

---

## 1. Independent convergence — strongest signal

Nine findings were reached by more than one reviewer working blind. These carry the most
weight.

| # | Finding | Reached by |
|---|---|---|
| C1 | §1's exposure inventory is badly undercounted | ARCH, CONTENT, CLAIMS |
| C2 | §5.1's "Verified precondition" is false — `404.html`/`site.webmanifest` use root-absolute paths | ARCH, CONTENT, CLAIMS |
| C3 | The placeholder count (215) is wrong, and it was to be the ratchet baseline | ARCH, CONTENT, CLAIMS |
| C4 | §9.3 misdiagnoses the automation failure; the real cause is a policy block | ARCH, CLAIMS |
| C5 | Live internal build notes naming a person and counsel — plan neither sees nor fixes | CONTENT, CLAIMS |
| C6 | §9.4 reports a *deliberate* decision as a defect and would reverse it | CONTENT, CLAIMS |
| C7 | §11 "CI green on `main`" is unachievable — `ci.yml` runs only on `pull_request` | ARCH, CLAIMS |
| C8 | `docker-compose.yml` spec omits `dockerfile:`, so the build breaks | ARCH, CLAIMS |
| C9 | The count-based placeholder ratchet is structurally unsound | CONTENT, CLAIMS |

---

## 2. Blocking defects in the mechanism

### B1 — The cutover produces no deployment at all *(R-ARCH)*

§7 claimed "at this moment all thirteen URLs return 404". Nothing in the plan causes a
successful deployment. Trace: PR-1 merges → `publish.yml` fires while `build_type` is still
`legacy` → `actions/deploy-pages` hard-fails (`Failed to create deployment (status: 404)...
Ensure GitHub Pages has been enabled`) → `0004` flips the API → **nothing re-triggers the
workflow**. Pages ends in `workflow` mode with zero successful deployments and `main` red.

**Accepted.** Fix: `publish.yml` gains `workflow_dispatch`; the cutover script becomes
`PUT` → poll `GET /pages` to `status:"built"` → `gh workflow run` → `gh run watch` → verify,
with automatic rollback if the run fails.

### B2 — The plan forbids its own acceptance criterion *(R-ARCH, R-CLAIMS)*

The daily workflow has failed **every run since 2026-08-21**:
```
##[error]GitHub Actions is not permitted to create or approve pull requests.
```
The scraper succeeds and detects changes; PR creation is refused by policy
(`can_approve_pull_request_reviews: false`). So **fresh outbreak data is fetched and
discarded daily** on a tracker whose sitemap declares `changefreq: daily`.

v1 §9.3 blamed a missing label — creating it fixes nothing, because labelling is never
reached. v1 §8.2 then pinned the actual cause under "Deliberately unchanged", while v1 §11
required those workflows to run green. Unsatisfiable by construction.

R-CLAIMS added that **no automated PR has ever existed** (all 8 issues/PRs are human), so
"every automated PR failed to be labelled" was vacuous.

**Accepted.** This is now a separate, higher-priority workstream (PR-0), not a footnote.
Requires a decision from the requester — see §4 R4.

### B3 — Jekyll is the build step, and it renders internal docs into indexable pages *(R-ARCH)*

v1 §1 asserted `legacy` "publishes every file on `main` verbatim. There is no build step."
Both halves are false. `legacy` runs Jekyll, which:
- **excludes** dotfiles — `/.gitignore`, `/.github/workflows/ci.yml`, `/CNAME` are all 404;
- **transforms** markdown — six internal documents have full HTML twins with themed layout,
  `<title>`, `og:site_name`, and `<link rel="canonical">`.

```
https://comeandscrewit.com/reference/nws-grand-challenge-tracker.html   → 200
<title>USDA APHIS New World Screwworm (NWS) Grand Challenge — Project Tracker | comeandscrewit</title>
<meta name="generator" content="Jekyll v3.10.0" />
<link rel="canonical" href="http://comeandscrewit.com/reference/nws-grand-challenge-tracker.html" />
```

**True exposure: 19 raw paths + 6 rendered twins = 25 URLs, not 13.** The twins are strictly
worse than raw `.md`: they carry canonical tags, so they are presented to crawlers as
first-class site content.

**Accepted.** §1's table is now generated, never hand-written, and §11 asserts
"no path outside `site/` returns 200" enumerated from `git ls-files`, not a prose list.

### B4 — `--rollback` becomes site-destroying after PR-2 *(R-ARCH)*

`0004 --rollback` sets `legacy`/`main`/`/`. After PR-2 there is no root `index.html` and no
root `CNAME`, so the flag an operator reaches for under pressure causes a total outage.

**Accepted.** `--rollback` now refuses and exits non-zero if `main:site/index.html` exists,
printing the `git revert` instruction instead.

### B5 — The `PUT` must send `cname` explicitly *(R-ARCH)*

`cname` is optional in the PUT schema; omission *should* preserve it. "Should" is not
adequate for the one field whose loss is unrecoverable inside the claimed window — losing
the custom domain re-triggers DNS verification and certificate provisioning, and GitHub
documents "up to 24 hours" before Enforce HTTPS becomes available again. v1's "~1 min"
rollback and "under two minutes" cutover estimates do not survive that.

**Accepted.** The cutover sends `{"build_type":"workflow","cname":"comeandscrewit.com"}` and
re-`GET`s to assert `cname` before proceeding. `https_enforced` becomes a separate later PUT
(a combined call risks `409 Conflict` while a build is in flight).

### B6 — The snapshot script was numbered after the cutover it baselines *(R-ARCH)*

v1 ordered `0004 cutover` then `0005 capture snapshot`, while §11's strongest criterion
required comparing against "the pre-cutover snapshot captured by `0005`". No baseline exists.

**Accepted.** Scripts renumbered so the snapshot precedes the cutover.

### B7 — Symlink bypass defeats *both* layers *(R-CLAIMS)*

Independently verified against `actions/upload-pages-artifact` `action.yml:33-38`:

```yaml
tar \
  --dereference --hard-dereference \
  --directory "$INPUT_PATH" \
  -cvf "$RUNNER_TEMP/artifact.tar" \
  --exclude=.git --exclude=.github \
  --exclude=.[^/]* \
  .
```

`--dereference` follows symlinks. `ln -s ../internal site/docs` uploads and serves the
**entire internal tree**. Layer 1 does not stop it (the link is inside `site/`). Layer 2 does
not stop it either — the extension check sees an extensionless symlink, and `find site/
-type f` does not descend into it.

**Accepted.** The gate now fails on any `find site/ -type l` match. This finding alone
retires the phrase "structurally impossible".

Corollary also accepted: `--exclude=.[^/]*` means dotfiles under `site/` are excluded by the
transport, so v1's `.gitkeep` reasoning was wrong (harmlessly — the empty directory simply
will not exist in the artifact).

---

## 3. Verified-false claims in v1

| v1 claim | Reality | Source |
|---|---|---|
| "publishes every file on `main` verbatim… no build step" | Jekyll build; dotfiles excluded; markdown transformed | ARCH |
| Exposure = 13 URLs | 19 raw + 6 rendered = 25 | ARCH, CONTENT, CLAIMS |
| "Confirmed live by `0001_...sh`" | That script probes 11 paths; the table has 13 rows. The cited evidence does not produce the cited table. | CLAIMS |
| "every `href`/`src` … no absolute-path references" (labelled *Verified*) | 12 root-absolute in `404.html`, 3 in `site.webmanifest`. Conclusion unaffected; the verification never happened. | ARCH, CONTENT, CLAIMS |
| 215 placeholders | 229–235 depending on regex. v1's pattern silently missed 5 token forms. | ARCH, CONTENT, CLAIMS |
| `[DOMAIN]` = 96 "in … sitemap.xml (13), robots.txt (1)" | 96 is HTML-only; 96+13+1 = 110. Row contradicts its own prose. | CONTENT, CLAIMS |
| "on all 15 pages" | 14 — `404.html` has no canonical and no OG tags | CONTENT, CLAIMS |
| "All 13 `<loc>` values" | 12. The 13th `[DOMAIN]` is in a **shipped authoring comment** at `sitemap.xml:2`. | CONTENT, CLAIMS |
| "eight merged PRs" | 7. #6 is an issue. Verified: `has("pull_request")` → false. | CLAIMS |
| "publicly served for weeks" | Repo created 2026-08-14 = **9 days**; `reference/` landed 2026-08-20 = **3 days**. | CLAIMS |
| "credential count … zero, the same as before" | Contradicted 22 lines earlier by `id-token: write`, which mints a signed OIDC JWT. | CLAIMS |
| "the ten GitHub defaults" | Correct — all ten are flagged `default: true`. **Reviewer was wrong, author right.** | CLAIMS |

The "weeks" error deserves separate note: it appeared inside the argument for *not*
remediating history. Inflating exposure duration made "already too late" more persuasive than
the evidence supports. The corrected figure (3 days for the sensitive material) materially
weakens v1's own recommendation, which is why R1 in §4 is now a genuine question rather than
a rubber stamp.

---

## 4. Overclaimed guarantees

v1 said **"structurally impossible"** and **"cannot be bypassed by a bad commit."** Both false.
Four counterexamples, each reachable in one commit:

1. **The control is a file in the repo.** Layer 1 is `path: site/` in `publish.yml`. One
   commit changing it to `path: .` publishes everything — and `main` has **no branch
   protection and no rulesets**, so no review is required. ADR 0001 asserts "No direct
   commits to `main`" with zero enforcement.
2. **Symlink** (B7).
3. **Allowlisted extensions carry arbitrary content** — `site/internal-notes.html` passes.
4. **Reverting the Pages setting** — one `gh api` call. v1's own §8.4 offered "ADR 0002
   records the constraint", a *procedural* mitigation for the exact failure class G2 declares
   must be structural.

**The accurate claim, adopted in v2:** *publishing internal content is no longer possible by
accident, and no longer possible at all without editing the publish workflow itself.* True,
valuable, defensible.

Consequence: **branch protection on `main` is now part of the plan**, not omitted. It is the
cheapest available structural control, v1's own recon script queried it and got "Branch not
protected", and v1 never mentioned the result.

---

## 5. Where reviewers were wrong or disagreed

Recorded so the record is not smoothed over.

- **Exposure count: 18 (ARCH) vs 19 (CLAIMS) vs 25 (my measurement).** Not a contradiction —
  different denominators. CLAIMS counted raw paths; ARCH counted raw + rendered twins.
  Reconciled: **19 raw + 6 twins = 25 URLs.**
- **Placeholder count: 229 (ARCH) vs 234 (CONTENT) vs 235 (CLAIMS).** All three used different
  regexes over different file sets. This *is the finding*: any scalar baseline is an artefact
  of its pattern. v2 replaces the count with a keyed `(file, token, count)` inventory.
- **R-CONTENT claimed 9 GitHub default labels and that `accessibility` is custom.** Wrong.
  R-CLAIMS checked the API: all ten report `default: true`. v1 was right.
- **R-CONTENT called the sitemap omission of `donate.html`/`partners-and-investors.html` a
  finding against v1 §9.4** while also correctly noting both are `noindex`. R-CLAIMS resolved
  it with git history (`cfdb748`): the removal was deliberate and documented. **v1 §9.4 is
  deleted, not amended** — following it would have put `noindex`, pre-legal-review investor
  copy into the sitemap.
- **R-CLAIMS could not settle** whether `peter-evans/create-pull-request` errors or silently
  creates an unknown label, and declined to guess or to litter the production repo to find
  out. Correct call; moot either way, since labelling is never reached (B2).
- **R-ARCH's §10 concern** that `sha_pinning_required` may not be settable on a Free-plan org
  is unresolved. v2 demotes it from a blocking acceptance criterion to best-effort with a
  recorded outcome.

---

## 6. The finding that changes the plan's scope

Both R-CONTENT and R-CLAIMS independently identified this, and I verified it on the wire.

Internal editorial notes are rendering as **visible body text** on the live site:

| Live URL | Rendered |
|---|---|
| `/partners-and-investors.html:130` | "**[PLACEHOLDER]** No financial figures, projections, or securities language until Luc / counsel supply them. Do not fabricate traction, funding, or metrics." |
| `/donate.html:82` | "**[PAYMENT PROCESSOR EMBED]** — … Do not hardcode a real payment link until Luc supplies the account." |
| `/about.html:71` | "**[FOUNDER STORY PLACEHOLDER — Luc supplies.]**" |
| `/our-approach.html:4` | "[CONFIRM CAPABILITY CLAIMS] — BUILD NOTE FOR LUC" |
| `/take-action.html` | "[Optional: link to a find-your-rep tool. Keep factual, no partisan framing.]" |

`about.html` and `our-approach.html` carry **no `noindex`** — fully crawlable.

R-CONTENT's argument, which I accept: **v1 scoped by mechanism (publishing config vs. site
copy) when the goal it wrote down was scoped by outcome (no internal content reachable).**
Under G1 as written, an internal note about securities language and counsel on a live
investor-solicitation page is more in scope than `nginx.conf`, not less. v1 filed it under
NG2 and then declared "Exposure: closed" — which would have converted an open problem into a
signed-off one.

The distinction v1 missed: *needs an input* ≠ *needs a decision*. Deleting a note that says
"do not fabricate traction" replaces it with nothing and requires no answer from anyone.
`[DOMAIN]` → `comeandscrewit.com` is mechanical. Only `[SOCIAL LINK]`, `[COMPANY NAME]`,
`[ANALYTICS ID]`, and the donate/contact endpoints genuinely need the requester.

**v2 adds PR-0 ahead of everything else**, covering the zero-input subset.

---

## 7. Adopted design changes

| Change | Driver |
|---|---|
| PR-0 added: delete internal editorial notes + mechanical `[DOMAIN]` pass | §6 |
| Gate inverted from extension **denylist** to extension **allowlist** | ARCH §4 — v1 was internally contradictory, indicting the Dockerfile denylist while specifying one, and calling it an allowlist in §8.1 |
| Gate adds explicit symlink rejection | B7 |
| Gate adds same-origin asset resolution, orphan-page, and sitemap↔robots checks | CONTENT §4 |
| Placeholder ratchet: scalar count → keyed `(file, token, count)` inventory, plus a no-baseline hard tier for URL-critical contexts | C9 |
| §1 exposure table generated, not hand-written; §11 asserts against `git ls-files` | B3, C1 |
| Branch protection on `main` added to scope | §4 |
| Automation-permissions fix promoted to its own workstream | B2 |
| "structurally impossible" → the accurate guarantee | §4 |
| §9.4 deleted | C6 |
| Cutover rewritten: explicit `cname`, staged `https_enforced`, dispatch-and-watch, guarded rollback | B1, B4, B5 |
| Scripts renumbered so snapshot precedes cutover | B6 |
| "single source of truth" claim corrected — a Dockerfile `COPY` cannot invoke the gate | ARCH §6 |
| `www.comeandscrewit.com` TLS failure added to scope | CONTENT §4 |
| Missing sections added: approvers, observability/alerting, partial-failure, ownership, cost | CLAIMS §6 |

## 8. Deferred, with reasons

- **Full placeholder remediation** beyond the zero-input subset — genuinely blocked on the
  requester.
- **WCAG contrast failures** (1.94:1 on `404.html`, and `styles.css:12`'s comment asserting a
  2.83:1 colour "passes as TEXT") — real, verified, but a design change. Reported, gate ships
  in warn mode.
- **`role="img"` on the Leaflet map** hiding zoom controls, 17 markers and the OSM attribution
  from assistive tech — real, and the attribution is a licence obligation. Separate PR.
- **Missing `og-default.png` / `logo.png` / manifest icons** — fixing `[DOMAIN]` converts
  invalid URLs into *valid URLs that 404*. Must ship art or strip the properties; needs owned
  assets.
- **`Article.dateModified` drift** (2026-08-11 vs. data's 2026-08-20) — fold into the daily
  refresh script.
- **pip hash-pinning**, **history rewrite** (pending R1).
