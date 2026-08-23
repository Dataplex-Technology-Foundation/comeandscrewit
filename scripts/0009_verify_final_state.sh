#!/usr/bin/env bash
#
# 0009_verify_final_state.sh
#
# The acceptance criteria for the publish boundary, as an executable check.
# Re-runnable indefinitely: run it on a schedule to detect drift, because every
# control here is revertible by someone who does not know why it exists.
#
# Checks, in order of what they protect:
#   1. Nothing outside site/ is reachable on the domain
#   2. Pages is configured the way the boundary requires
#   3. Every published file is byte-identical to what is committed
#   4. The gate still rejects its known bypasses
#   5. The container reproduces the same boundary
#   6. Automation still resolves its paths
#
# Exit 0 if every check passes, 1 otherwise. No mutations, no network writes.
#
# Usage: scripts/0009_verify_final_state.sh [--skip-docker]

set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1
REPO="${REPO:-Dataplex-Technology-Foundation/comeandscrewit}"
SITE="${SITE:-https://comeandscrewit.com}"
SKIP_DOCKER=0
[ "${1:-}" = "--skip-docker" ] && SKIP_DOCKER=1

pass=0 fail=0
ok()   { printf '  PASS  %s\n' "$*"; pass=$((pass+1)); }
no()   { printf '  FAIL  %s\n' "$*"; fail=$((fail+1)); }
sec()  { printf '\n== %s\n' "$*"; }

# ------------------------------------------------------------------ 1. exposure
sec "Exposure"
exposed=$(./scripts/0002_exposure_inventory.sh --exposure --quiet 2>/dev/null | grep -c '^200 ')
[ "$exposed" -eq 0 ] && ok "no path outside site/ is reachable" \
                     || no "$exposed internal URL(s) still served"

# ------------------------------------------------------------- 2. pages config
sec "Pages configuration"
cfg=$(gh api "repos/$REPO/pages" 2>/dev/null)
get() { printf '%s' "$cfg" | python3 -c "import json,sys;print(json.load(sys.stdin).get('$1',''))" 2>/dev/null; }
[ "$(get build_type)" = "workflow" ] \
  && ok "build_type=workflow (the artifact is the boundary)" \
  || no "build_type=$(get build_type) -- reverting to legacy republishes the whole branch"
[ "$(get cname)" = "comeandscrewit.com" ] && ok "cname preserved" || no "cname=$(get cname)"
[ "$(get https_enforced)" = "True" ] && ok "https_enforced" || no "https_enforced=$(get https_enforced)"
[ "$(get status)" = "built" ] && ok "status=built" || no "status=$(get status)"
redir=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "http://comeandscrewit.com/")
[ "$redir" = "301" ] || [ "$redir" = "308" ] && ok "http:// redirects ($redir)" || no "http:// returns $redir"

# ------------------------------------------------------------ 3. served == repo
sec "Served bytes match the repository"
n=0; bad=0
while read -r f; do
  [ "$f" = "CNAME" ] && continue   # excluded from the artifact by design
  n=$((n+1))
  live=$(curl -sS --max-time 20 "$SITE/$f" | sha256sum | cut -d' ' -f1)
  repo=$(sha256sum "site/$f" | cut -d' ' -f1)
  [ "$live" = "$repo" ] || { printf '        differs: /%s\n' "$f"; bad=$((bad+1)); }
done < <(cd site && git ls-files)
[ "$bad" -eq 0 ] && ok "$n published file(s) byte-identical to the repo" \
                 || no "$bad of $n file(s) differ"

# --------------------------------------------------------------- 4. gate proofs
sec "The gate still rejects its bypasses"
tmp=$(mktemp -d); git clone -q . "$tmp/repo" 2>/dev/null
cp scripts/0005_build_site_artifact.py "$tmp/repo/scripts/" 2>/dev/null
(
  cd "$tmp/repo" || exit 1
  PUB=site; [ -d site ] || PUB=.
  try() {  # try <description> ; expects the gate to FAIL
    if python3 scripts/0005_build_site_artifact.py --check >/dev/null 2>&1; then
      echo "ACCEPTED:$1"
    else
      echo "rejected:$1"
    fi
  }
  echo x > "$PUB/LEAK.md";                        try "unpublishable .md in the publish root"; rm -f "$PUB/LEAK.md"
  mkdir -p tgt && echo s > tgt/x.md
  ln -s ../../tgt "$PUB/assets/esc";              try "symlink escaping the publish root";     rm -f "$PUB/assets/esc"
  if [ "$PUB" = site ]; then
    mv site site_r && ln -s site_r site;          try "publish root itself a symlink";         rm -f site && mv site_r site
  fi
  sed -i 's|href="https://comeandscrewit.com/faq.html">|href="https://[DOMAIN]/faq.html">|' "$PUB/faq.html"
                                                  try "[DOMAIN] in rel=canonical"
) > "$tmp/out" 2>/dev/null
while IFS=: read -r verdict what; do
  [ "$verdict" = "rejected" ] && ok "gate rejects: $what" || no "gate ACCEPTED: $what"
done < "$tmp/out"
rm -rf "$tmp"

# ----------------------------------------------------------------- 5. container
sec "Container reproduces the boundary"
if [ "$SKIP_DOCKER" = 1 ] || ! command -v docker >/dev/null 2>&1; then
  printf '  SKIP  docker unavailable\n'
else
  if docker build -q -f internal/container/Dockerfile -t screwworm-site:verify . >/dev/null 2>&1; then
    leaked=$(docker run --rm --entrypoint sh screwworm-site:verify -c \
      'find /usr/share/nginx/html \( -name "*.md" -o -name "*.py" -o -name "*.sh" -o -name "*.yml" \) | wc -l')
    [ "$leaked" -eq 0 ] && ok "image contains no internal file types" \
                        || no "$leaked internal file(s) in the image"
    docker rmi -f screwworm-site:verify >/dev/null 2>&1
  else
    no "container build failed"
  fi
fi

# ---------------------------------------------------------------- 6. automation
sec "Automation"
python3 -m unittest discover -s internal/tests >/dev/null 2>&1 \
  && ok "unit tests pass" || no "unit tests fail"
for f in internal/automation/*.py; do
  python3 -m py_compile "$f" 2>/dev/null || no "does not compile: $f"
done
ok "automation scripts compile"

prs=$(gh api "repos/$REPO/actions/permissions/workflow" --jq '.can_approve_pull_request_reviews' 2>/dev/null)
if [ "$prs" = "true" ]; then
  ok "Actions may open pull requests (data-refresh pipeline can land changes)"
else
  printf '  BLOCKED  Actions cannot open pull requests -- the daily outbreak refresh\n'
  printf '           scrapes successfully and then discards the result. Needs an org\n'
  printf '           owner to allow it in organisation Actions settings.\n'
fi

# -------------------------------------------------------------------- summary
sec "Summary"
printf '  %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ] && echo "  Boundary holds." || echo "  DRIFT DETECTED."
exit $([ "$fail" -eq 0 ] && echo 0 || echo 1)
