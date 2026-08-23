# Contributing

## The publish boundary

**If it is not under `site/`, it is not on the website.**

`site/` is uploaded verbatim as the GitHub Pages artifact. Nothing outside it is
in that artifact at all.

| Adding… | Goes in |
|---|---|
| a page, stylesheet, script, image, or site data file | `site/` |
| research, notes, meeting records, plans | `internal/` |
| a scraper or other automation | `internal/automation/` |
| a test | `internal/tests/` |
| a one-off operational script | `scripts/`, numbered `nnnn_name.ext` |

Check before you push:

```sh
python3 scripts/0005_build_site_artifact.py --check
```

It fails on anything unpublishable under `site/`, on symlinks escaping it, on
placeholders in machine-consumed URLs (`rel=canonical`, `og:url`, `<loc>`,
`Sitemap:`), on references that do not resolve, and on `http://` subresources.
CI runs the same check, and additionally proves on every pull request that the
gate still rejects its known bypasses.

## Workflow

Per [ADR 0001](internal/docs/adr/0001-branch-pr-and-issue-workflow.md): no direct
commits to `main`. Branch as `<type>/<short-description>`, open a pull request,
reference the issue that motivated it, and let CI pass before merging.

## Editing pages

- Update `<lastmod>` in `site/sitemap.xml` for any page you change.
- Do not leave `[BRACKETED]` placeholders in a canonical URL, `og:url`,
  `og:image`, `twitter:*`, a sitemap `<loc>`, or `robots.txt` — the gate rejects
  those outright. Prose placeholders are tracked in
  `internal/publish/placeholder-baseline.txt` and may not increase.
- Every same-origin reference must resolve to a real file in `site/`.
