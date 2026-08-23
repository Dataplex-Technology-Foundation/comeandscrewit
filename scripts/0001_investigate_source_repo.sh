#!/usr/bin/env bash
# 0001_investigate_source_repo.sh
#
# Read-only reconnaissance of the existing comeandscrewit site repository and
# its GitHub configuration. Establishes the baseline that the split plan
# (docs/plan/) is built on. Makes no changes to any repo, local or remote.
#
# Usage: scripts/0001_investigate_source_repo.sh [path-to-comeandscrewit-checkout]
# Output: human-readable report on stdout. Redirect to capture a snapshot.

set -uo pipefail

SRC="${1:-$HOME/source/comeandscrewit}"
REPO="Dataplex-Technology-Foundation/comeandscrewit"
SITE="https://comeandscrewit.com"

hdr() { printf '\n=== %s ===\n' "$*"; }

hdr "Local checkout: $SRC"
git -C "$SRC" remote -v
git -C "$SRC" branch -a
git -C "$SRC" log --oneline -15

hdr "Working tree (excluding .git)"
find "$SRC" -path "$SRC/.git" -prune -o -print | sed "s|^$SRC|.|" | sort

hdr "GitHub Pages configuration"
# build_type=legacy + source.path=/ means EVERY file on the source branch is
# published verbatim. This is the root cause of README.md being reachable.
gh api "repos/$REPO/pages"

hdr "Repository metadata"
gh api "repos/$REPO" --jq '{name,visibility,default_branch,has_pages,homepage,archived}'

hdr "Collaborators (to be replicated on the deploy repo)"
gh api "repos/$REPO/collaborators?affiliation=all&per_page=100" --jq '.[] | "\(.login)\t\(.role_name)"'

hdr "Teams / pending invitations"
gh api "repos/$REPO/teams" --jq '.[] | "\(.slug)\t\(.permission)"'
gh api "repos/$REPO/invitations" --jq '.[] | "\(.invitee.login)\t\(.permissions)"'

hdr "Branch protection / rulesets"
gh api "repos/$REPO/branches/main/protection" 2>&1 | head -5
gh api "repos/$REPO/rulesets"

hdr "Actions configuration"
gh api "repos/$REPO/actions/permissions"
gh api "repos/$REPO/actions/permissions/workflow"
echo "secrets:";   gh api "repos/$REPO/actions/secrets"   --jq '.secrets[].name'
echo "variables:"; gh api "repos/$REPO/actions/variables" --jq '.variables[].name'
echo "environments:"; gh api "repos/$REPO/environments" --jq '.environments[]?.name'

hdr "Labels (workflows reference 'automated-data-refresh')"
gh api "repos/$REPO/labels" --jq '.[].name'

hdr "Organization"
gh api orgs/Dataplex-Technology-Foundation \
  --jq '{login,plan:.plan.name,default_repository_permission}'

hdr "Live exposure probe — non-site paths that must stop resolving"
for p in README.md \
         Dockerfile \
         docker-compose.yml \
         nginx.conf \
         docs/adr/0001-branch-pr-and-issue-workflow.md \
         reference/nws-grand-challenge-tracker.md \
         reference/ops-workflow-grant-tracking.md \
         scripts/rank_projects.py \
         scripts/scrape_outbreak_data.py \
         tests/test_scrape_outbreak_data.py \
         assets/img/README.md; do
  printf '%-55s -> %s\n' "$p" "$(curl -sS -o /dev/null -w '%{http_code}' "$SITE/$p")"
done

hdr "Live exposure probe — site paths that must keep resolving"
for p in "" index.html faq.html contact.html outbreak-status.html \
         robots.txt sitemap.xml site.webmanifest favicon.svg \
         assets/css/styles.css assets/js/main.js \
         assets/data/outbreak-data.json 404.html; do
  printf '%-55s -> %s\n' "/$p" "$(curl -sS -o /dev/null -w '%{http_code}' "$SITE/$p")"
done

hdr "Coupling check — does any shipped site file reference non-site paths?"
grep -rnE 'reference/|docs/|scripts/|tests/|README' \
  --include='*.html' --include='*.js' --include='*.xml' \
  --include='*.json' --include='*.webmanifest' "$SRC" \
  | grep -v "$SRC/reference/" || echo "none (site and non-site content are cleanly separable)"

hdr "Coupling check — filesystem paths the automation scripts depend on"
grep -nE 'REPO_ROOT|_FILE = |SCRATCH_DIR' "$SRC"/scripts/*.py
