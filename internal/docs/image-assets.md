# Image assets — placeholders

Drop real, owned/licensed images here. **Do not** use scraped USDA or news photos.
Every `<img>` in the site must keep descriptive, keyword-aware `alt` text and
explicit `width`/`height` (to prevent layout shift) and `loading="lazy"`.

Files referenced by the build (add these):

| File | Used by | Notes |
|------|---------|-------|
| `og-default.png` | all pages (Open Graph / Twitter) | 1200×630. Social share image. |
| `logo.png` | JSON-LD `Organization.logo` | Square PNG of the wordmark/logo. |
| `outbreak-map.png` | `outbreak-status.html` | Static map of TX/NM cases if no live embed. |
| `icon-192.png`, `icon-512.png` | `site.webmanifest` | PWA / favicon fallbacks. |

Until real images exist, the site ships text/SVG lockups and visible
`[IMAGE: …]` placeholders — nothing broken, nothing fake.
