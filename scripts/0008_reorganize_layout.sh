#!/usr/bin/env bash
#
# 0008_reorganize_layout.sh
#
# Moves the repository to the site/ + internal/ layout, so the publish boundary
# is visible in the tree rather than only in a script. Every move uses `git mv`,
# so history and `git log --follow` survive.
#
# The rule this creates, in one sentence: if it is not under site/, it is not on
# the website.
#
# Idempotent -- each move is skipped if already done, so a partial run can be
# resumed. Makes no commit and no network call; inspect `git status` afterwards.
#
# Run AFTER the Pages cutover, never before. Under the old branch build this
# layout would leave main with no root index.html and 404 the entire site until
# the build type changed. The cutover is what makes this a safe refactor.
#
# Usage: scripts/0008_reorganize_layout.sh [--check]

set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1
CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

moved=0 skipped=0
say() { printf '\n== %s\n' "$*"; }

mv_path() {
  local from="$1" to="$2"
  if [ ! -e "$from" ]; then
    if [ -e "$to" ]; then skipped=$((skipped+1)); return 0; fi
    printf '   MISSING  %s\n' "$from"; return 1
  fi
  if [ "$CHECK" = 1 ]; then printf '   would move  %-46s -> %s\n' "$from" "$to"; moved=$((moved+1)); return 0; fi
  mkdir -p "$(dirname "$to")"
  git mv "$from" "$to" && { printf '   moved  %-46s -> %s\n' "$from" "$to"; moved=$((moved+1)); }
}

# ------------------------------------------------------------------ publish set
say "Publish set -> site/"
for f in $(git ls-files -- '*.html' 'assets/*' CNAME favicon.svg robots.txt site.webmanifest sitemap.xml | grep -v '^site/'); do
  mv_path "$f" "site/$f"
done

# --------------------------------------------------------------------- internal
say "Internal material -> internal/"
mv_path README.md                         internal/docs/deployment.md
for f in $(git ls-files -- 'docs/adr/*'); do mv_path "$f" "internal/$f"; done
for f in $(git ls-files -- 'reference/*'); do mv_path "$f" "internal/$f"; done
for f in $(git ls-files -- 'tests/*');     do mv_path "$f" "internal/$f"; done
mv_path scripts/rank_projects.py          internal/automation/rank_projects.py
mv_path scripts/refresh-outbreak-data.py  internal/automation/refresh-outbreak-data.py
mv_path scripts/scrape_outbreak_data.py   internal/automation/scrape_outbreak_data.py
mv_path scripts/requirements.txt          internal/automation/requirements.txt
mv_path Dockerfile                        internal/container/Dockerfile
mv_path nginx.conf                        internal/container/nginx.conf
mv_path docker-compose.yml                internal/container/docker-compose.yml

[ "$CHECK" = 1 ] && { printf '\n--check: %d move(s) pending, %d already done\n' "$moved" "$skipped"; exit 0; }

# ------------------------------------------------------- python path constants
# REPO_ROOT was `parent.parent`, which resolved to the repo root from scripts/.
# From internal/automation/ that is internal/, so it must become parents[2].
# Anchored to the constant-assignment lines: a blind sed would also rewrite the
# path strings that appear in docstrings and in PR-body prose.
say "Path constants in internal/automation/"
python3 - <<'PY'
import pathlib, re
root = pathlib.Path('.')
head = (
    'REPO_ROOT = Path(__file__).resolve().parents[2]\n'
    'SITE_ROOT = REPO_ROOT / "site"\n'
    'INTERNAL_ROOT = REPO_ROOT / "internal"\n'
)
subs = {
    'internal/automation/rank_projects.py': [
        (r'^REPO_ROOT = .*$', head.rstrip()),
        (r'^TRACKER_FILE = .*$',          'TRACKER_FILE = INTERNAL_ROOT / "reference" / "nws-grand-challenge-tracker.md"'),
        (r'^RANKINGS_FILE = .*$',         'RANKINGS_FILE = INTERNAL_ROOT / "reference" / "nws-grand-challenge-rankings.md"'),
        (r'^RANKINGS_HISTORY_FILE = .*$', 'RANKINGS_HISTORY_FILE = INTERNAL_ROOT / "reference" / "nws-grand-challenge-rankings-history.json"'),
    ],
    'internal/automation/refresh-outbreak-data.py': [
        (r'^REPO_ROOT = .*$', head.rstrip()),
        (r'^DATA_FILE = .*$', 'DATA_FILE = SITE_ROOT / "assets" / "data" / "outbreak-data.json"'),
    ],
    'internal/automation/scrape_outbreak_data.py': [
        (r'^REPO_ROOT = .*$', head.rstrip()),
        (r'^OUTBREAK_DATA_FILE = .*$',    'OUTBREAK_DATA_FILE = SITE_ROOT / "assets" / "data" / "outbreak-data.json"'),
        (r'^OUTBREAK_HISTORY_FILE = .*$', 'OUTBREAK_HISTORY_FILE = SITE_ROOT / "assets" / "data" / "outbreak-history.json"'),
        (r'^PUBLICATIONS_FILE = .*$',     'PUBLICATIONS_FILE = INTERNAL_ROOT / "reference" / "screwworm-gov-research-publications.md"'),
        (r'^SCRATCH_DIR = .*$',           'SCRATCH_DIR = REPO_ROOT / "scratch"'),
    ],
}
for path, rules in subs.items():
    f = root / path
    if not f.exists():
        print(f"   MISSING {path}"); continue
    text = f.read_text()
    for pat, rep in rules:
        text, n = re.subn(pat, rep, text, count=1, flags=re.MULTILINE)
        if not n:
            print(f"   WARNING no match in {path}: {pat}")
    f.write_text(text)
    print(f"   rewrote constants in {path}")

t = root / 'internal/tests/test_scrape_outbreak_data.py'
if t.exists():
    text = t.read_text()
    text = text.replace('parent.parent / "scripts"', 'parent.parent / "automation"')
    text = text.replace('scripts/scrape_outbreak_data.py', 'internal/automation/scrape_outbreak_data.py')
    t.write_text(text)
    print("   rewrote sys.path in internal/tests/test_scrape_outbreak_data.py")
PY

# ------------------------------------------------------------------- workflows
# Seven command-level references, not five. The two `run:` lines that actually
# invoke the scripts break hardest, and nothing else would catch them: ci.yml
# never executes the scheduled workflows.
say "Workflow paths"
python3 - <<'PY'
import pathlib
edits = {
    '.github/workflows/ci.yml': [
        ('pip install -r scripts/requirements.txt', 'pip install -r internal/automation/requirements.txt'),
        ('pip install -r tests/requirements.txt',   'pip install -r internal/tests/requirements.txt'),
        ('py_compile scripts/*.py',                 'py_compile internal/automation/*.py'),
        ('unittest discover -s tests -v',           'unittest discover -s internal/tests -v'),
    ],
    '.github/workflows/daily-outbreak-data.yml': [
        ('pip install -r scripts/requirements.txt', 'pip install -r internal/automation/requirements.txt'),
        ('python3 scripts/scrape_outbreak_data.py', 'python3 internal/automation/scrape_outbreak_data.py'),
        ('git diff --quiet -- assets/data reference',
         'git diff --quiet -- site/assets/data internal/reference'),
        ('assets/data/outbreak-data.json',    'site/assets/data/outbreak-data.json'),
        ('assets/data/outbreak-history.json', 'site/assets/data/outbreak-history.json'),
        ('reference/screwworm-gov-research-publications.md',
         'internal/reference/screwworm-gov-research-publications.md'),
        ('scripts/scrape_outbreak_data.py',   'internal/automation/scrape_outbreak_data.py'),
    ],
    '.github/workflows/weekly-project-rankings.yml': [
        ('python3 scripts/rank_projects.py', 'python3 internal/automation/rank_projects.py'),
        ('git diff --quiet -- reference/nws-grand-challenge-rankings.md reference/nws-grand-challenge-rankings-history.json',
         'git diff --quiet -- internal/reference/nws-grand-challenge-rankings.md internal/reference/nws-grand-challenge-rankings-history.json'),
        ('reference/nws-grand-challenge-rankings.md',         'internal/reference/nws-grand-challenge-rankings.md'),
        ('reference/nws-grand-challenge-rankings-history.json','internal/reference/nws-grand-challenge-rankings-history.json'),
        ('reference/nws-grand-challenge-tracker.md',          'internal/reference/nws-grand-challenge-tracker.md'),
    ],
}
for path, pairs in edits.items():
    f = pathlib.Path(path)
    text = f.read_text(); before = text
    # Longest `old` first. Otherwise a short pair re-matches inside text a long
    # pair already rewrote and prefixes it twice -- which is exactly how
    # weekly-project-rankings.yml ended up with a `git diff --` filter pointing
    # at internal/internal/reference/, matching nothing, so the job reported
    # success while discarding every regenerated ranking.
    for old, new in sorted(pairs, key=lambda pr: len(pr[0]), reverse=True):
        if new in text and old not in text:
            continue                      # already applied
        text = text.replace(old, new)
    if text != before:
        f.write_text(text); print(f"   rewrote {path}")
    else:
        print(f"   unchanged {path}")
PY

# ------------------------------------------------------------------- container
say "Container build"
if [ -f internal/container/Dockerfile ]; then
  cat > internal/container/Dockerfile <<'DOCKER'
FROM nginx:alpine

COPY internal/container/nginx.conf /etc/nginx/nginx.conf

# Copy only the publish root. The previous version copied the whole repo and
# then removed four known files by name -- a denylist, and the same defect as
# the old Pages configuration: it shipped README.md, docs/, reference/,
# scripts/ and tests/ into the image, so `docker compose up` served the internal
# material on localhost. An allowlist has nothing to keep in sync.
COPY site/ /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
DOCKER
  echo "   rewrote internal/container/Dockerfile (allowlist COPY)"
fi

if [ -f internal/container/docker-compose.yml ]; then
  cat > internal/container/docker-compose.yml <<'COMPOSE'
# Build context is the repo root, so the Dockerfile can COPY site/.
# Both `context:` and `dockerfile:` are required -- with only `context: ../..`,
# Compose looks for a Dockerfile at the context root, where there is none.
services:
  screwworm-site:
    build:
      context: ../..
      dockerfile: internal/container/Dockerfile
    image: screwworm-site:latest
    container_name: screwworm-site
    ports:
      - "8093:80"
    restart: unless-stopped
COMPOSE
  echo "   rewrote internal/container/docker-compose.yml (context + dockerfile)"
fi

cat > .dockerignore <<'IGNORE'
# The build context is the repo root so the Dockerfile can COPY site/.
# Without this, every build also ships .git and the whole internal tree as
# context. Only site/ and the nginx config are needed.
*
!site
!internal/container/nginx.conf
IGNORE
echo "   wrote .dockerignore"

# ------------------------------------------------------ retire the transitional
say "Transitional Jekyll denylist"
if [ -f _config.yml ]; then
  git rm -q _config.yml
  echo "   removed _config.yml -- Pages no longer runs Jekyll, and site/ is now"
  echo "   the artifact, so the boundary is structural rather than a denylist"
else
  echo "   already removed"
fi

printf '\n%d move(s), %d already in place. Nothing committed -- review `git status`.\n' "$moved" "$skipped"
