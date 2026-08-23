# Removed content inventory — PR-0

Everything `scripts/0003_fix_live_internal_notes.py` removed from the live site, verbatim, so
any of it can be rebuilt. Nothing here was lost: it is all recoverable from this file, and the
script's `content_loss()` check proves no visitor-facing prose disappeared beyond what is listed.

**Two headings were removed. Both are in `about.html`, and both are worth rebuilding** — they
mark real sections the site should eventually have. Everything else removed was an instruction
addressed to the site's owner, not content.

---

## 1. Removed headings (2)

Both were removed only because the placeholder note was their *entire* body, leaving an empty
section. A heading followed by `</div>` is not treated as orphaned — that shape is a legitimate
hero heading — so no other heading on the site was touched.

### `about.html` — `<h2>Team</h2>`

```html
        <h2>Team</h2>
        <div class="placeholder"><strong>[TEAM / BIOS PLACEHOLDER]</strong> — add founder and team bios.</div>
```

**Intent:** founder and team bios.
**Rebuild when:** you have at least one bio. Reinsert after the `<h2>Our mission</h2>` block and
before the closing `<hr>`.

### `about.html` — `<h2>Company</h2>`

```html
        <h2>Company</h2>
        <div class="placeholder"><strong>[COMPANY NAME / ENTITY PLACEHOLDER]</strong> — the campaign is the public face; the company is the operator.</div>
```

**Intent:** name the operating entity and distinguish it from the campaign. Note this is the same
information `[COMPANY NAME]` needs in all 15 page footers — currently still rendering literally as
`© 2026 [COMPANY NAME].`, which is a Tier-B placeholder tracked separately.
**Rebuild when:** the entity name is settled. Reinsert directly after the Team section.

**Restoration snippet for both** — paste into `site/about.html` after the mission paragraph:

```html
        <h2>Team</h2>
        <p>…bios…</p>

        <h2>Company</h2>
        <p>…entity name and its relationship to the campaign…</p>
```

---

## 2. Removed internal notes (7)

These addressed the owner, not visitors. Each is recorded with what it was asking for, so it
doubles as a to-do list.

| # | Page | Note | What it was asking for |
|---|---|---|---|
| 1 | `about.html` | `[FOUNDER STORY PLACEHOLDER — Luc supplies.]` "Draft scaffold below — replace with the real story." | Replace the two scaffold paragraphs with the real founder story. **The scaffold paragraphs were kept** — they read as finished prose and are still live. |
| 2 | `about.html` | `[TEAM / BIOS PLACEHOLDER]` | See §1 |
| 3 | `about.html` | `[COMPANY NAME / ENTITY PLACEHOLDER]` | See §1 |
| 4 | `donate.html` | `[PAYMENT PROCESSOR EMBED]` — "Stripe / Donorbox / etc. Drop the donation widget here. Suggested amounts: $25 / $100 / $500 / custom." | A donation widget. The suggested-amount chips above it are still live, so the page currently shows amounts with no way to pay. Worth either finishing or hiding the section. |
| 5 | `our-approach.html` | `[Describe real capability once defined]` — "keep claims honest for a pre-launch venture." | Concrete capability text under the **Detect** pillar. The pillar's own description was kept. |
| 6 | `partners-and-investors.html` | `[PLACEHOLDER]` — "No financial figures, projections, or securities language until Luc / counsel supply them. Do not fabricate traction, funding, or metrics." | A standing constraint, not content. Recorded here so the constraint survives; it must not go back on the page. |
| 7 | `take-action.html` | `[Optional: link to a find-your-rep tool. Keep factual, no partisan framing.]` | Optional "find your representative" link under *2. Push for a faster response*. Explicitly optional. |

---

## 3. Removed comments (2) and one normalised (1)

**`our-approach.html`** — banner comment, removed in full:

```html
<!--
  ============================================================================
  [CONFIRM CAPABILITY CLAIMS]  — BUILD NOTE FOR LUC
  This is a pre-launch venture. Every capability statement on this page must be
  something you can honestly back up. Review the "Detect / Map / Support"
  sections and soften or firm up wording to match real, current capability
  before publishing. Do not imply deployed technology that does not yet exist.
  ============================================================================
-->
```

A standing editorial constraint. Preserved here; it should not return to a served file.

**`sitemap.xml`** — removed authoring instruction, which was being served publicly:

```xml
<!-- Update <lastmod> on any page you edit. Replace [DOMAIN] site-wide before publish. -->
```

The `[DOMAIN]` half is now done. The `<lastmod>` reminder is worth keeping as a repo convention —
better placed in `CONTRIBUTING.md` than in a file search engines fetch.

**`index.html`** — normalised, not removed:

```
-  <!-- [ANALYTICS ID] — paste Plausible/GA4 snippet here once Luc supplies an ID. No tracking without it. -->
+  <!-- [ANALYTICS ID] -->
```

The bare marker is what the other 13 pages already use. The "no tracking without it" intent is
preserved by the marker itself plus this entry.

---

## 4. Still outstanding — not touched by PR-0

These need input only you can give, and are tracked as Tier-B placeholders by the publish gate:

| Token | Count | Where |
|---|---|---|
| `[SOCIAL LINK]` | 70 | 3 footer anchors + 2 JSON-LD `sameAs` entries × 14 pages |
| `[COMPANY NAME]` | 15 | footer copyright, all 15 pages — **visible to visitors** |
| `[OG IMAGE]` | 14 | marker beside `og:image` |
| `[ANALYTICS ID]` | 14 | marker where the analytics snippet goes |
| `[FORM ENDPOINT]` | 2 | `partners-and-investors.html` form `action` |
| `[PARTNER EMAIL]`, `[PARTNERS]` | 2 | `partners-and-investors.html` |

Also outstanding, and now slightly more visible than before: `og:image`, `twitter:image` and the
JSON-LD `logo` all point at five image files that do not exist
(`og-default.png`, `logo.png`, `outbreak-map.png`, `icon-192.png`, `icon-512.png`). Before PR-0
those URLs were malformed and crawlers discarded them; now they are well-formed and return 404.
No visitor-facing change either way, but Search Console will begin reporting an unfetchable logo
until artwork is supplied or the properties are stripped. The original spec for these files is in
`internal/docs/image-assets.md`.
