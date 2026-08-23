# comeandscrewit.com

Public-awareness site for the New World Screwworm outbreak, served by GitHub
Pages at [comeandscrewit.com](https://comeandscrewit.com).

## The one rule

**If it is not under `site/`, it is not on the website.**

`site/` *is* the published artifact. `.github/workflows/publish.yml` uploads that
directory and nothing else, so everything outside it is absent from what gets
deployed — not excluded from it by a rule someone could edit.

```
site/        the website. This directory becomes comeandscrewit.com.
internal/    automation, tests, research, container config, docs. Never published.
scripts/     numbered operational scripts (0001…). Never published.
```

## Adding a page

Put it in `site/`, link it from somewhere, and add it to `site/sitemap.xml`.
Nothing else — there is no manifest to update and no build step to configure.

CI will reject the pull request if the page pulls in something that cannot be
published. Run the same check locally first:

```sh
python3 scripts/0005_build_site_artifact.py --check
```

## Adding notes, research, or tooling

Put it under `internal/`. If you put a `.md`, `.py`, `.sh` or `.yml` inside
`site/`, the gate fails with the path, the rule, and the fix.

## Why it works this way

The site used to be published straight from the branch by Jekyll, which meant
every file in the repository was live — `README.md`, `nginx.conf`, the scrapers,
and internal research notes, the last of these also rendered as search-optimised
pages with canonical tags. 25 URLs in total.

Deleting those files would have fixed that day and nothing after it. The
boundary is the fix: publication now requires being in `site/`.

See `internal/docs/plan/` for the full design and `internal/docs/adr/` for
decisions.

## Local preview

```sh
docker compose -f internal/container/docker-compose.yml up --build
# http://localhost:8093
```

The image copies `site/` and nothing else, so what you see locally is what
publishes.
