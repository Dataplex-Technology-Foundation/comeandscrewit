#!/usr/bin/env bash
#
# 0007_cutover_pages.sh
#
# Switches comeandscrewit.com from the Jekyll branch build to the Actions build
# that publishes only the gated artifact, then verifies the result against the
# baseline captured by scripts/0006_capture_site_snapshot.sh.
#
# Ordering matters, and not in the obvious way:
#
#   1. PUT build_type=workflow, ALWAYS sending cname explicitly. cname is
#      optional in the schema and omitting it *should* preserve the domain, but
#      "should" is not adequate for the one field whose loss is not a quick
#      rollback: re-adding a custom domain re-triggers DNS verification and
#      certificate provisioning, which GitHub documents as taking up to 24 hours.
#   2. Poll until the Pages site reports a settled state.
#   3. Dispatch publish.yml and WAIT for it. Nothing else re-triggers it, so
#      without this the site ends up in workflow mode with zero successful
#      deployments -- Pages pointing at a workflow that has never run.
#   4. Verify, then set https_enforced in a SEPARATE call. Combining it with
#      step 1 risks 409 Conflict while a build is in flight.
#
# --rollback restores the branch build, and REFUSES once the layout has moved:
# setting legacy/main// on a tree whose index.html lives under site/ would take
# the whole site down. It prints the git revert instruction instead.
#
# Usage:
#   scripts/0007_cutover_pages.sh [--dry-run]
#   scripts/0007_cutover_pages.sh --rollback

set -uo pipefail

REPO="${REPO:-Dataplex-Technology-Foundation/comeandscrewit}"
SITE="${SITE:-https://comeandscrewit.com}"
DOMAIN="comeandscrewit.com"
SNAP="${SNAP:-artifacts}"
MODE="${1:-}"

# --verify-only re-runs just the baseline comparison, for when the cutover
# itself succeeded but verification needs repeating.

say() { printf '\n== %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

pages_json() { gh api "repos/$REPO/pages" 2>/dev/null; }
build_type() { pages_json | python3 -c 'import json,sys;print(json.load(sys.stdin).get("build_type",""))' 2>/dev/null; }
pages_field() { pages_json | python3 -c "import json,sys;print(json.load(sys.stdin).get('$1',''))" 2>/dev/null; }

# ------------------------------------------------------------------- rollback
if [ "$MODE" = "--rollback" ]; then
  say "Rollback guard"
  if git cat-file -e main:site/index.html 2>/dev/null; then
    cat >&2 <<'EOF'
REFUSING to roll back.

main:site/index.html exists, so the layout reorganisation has already merged.
Restoring the branch build would point Pages at a tree whose root has no
index.html -- the entire site would 404, and the custom domain would no longer
be backed by a root CNAME file.

Roll back the layout instead:
    git revert -m 1 <merge-commit-of-the-layout-PR>
then re-run this script once main:index.html exists again.
EOF
    exit 1
  fi
  say "Restoring build_type=legacy on $REPO"
  gh api -X PUT "repos/$REPO/pages" \
    -f build_type=legacy -f "cname=$DOMAIN" \
    -f 'source[branch]=main' -f 'source[path]=/' >/dev/null \
    || die "rollback PUT failed"
  echo "   build_type is now: $(build_type)"
  echo "   cname is now:      $(pages_field cname)"
  exit 0
fi

if [ "$MODE" = "--verify-only" ]; then
  verify_only=1
else
  verify_only=0
fi

# -------------------------------------------------------------- preconditions
say "Preconditions"
current="$(build_type)"
echo "   build_type:      $current"
echo "   cname:           $(pages_field cname)"
echo "   https_enforced:  $(pages_field https_enforced)"
[ -z "$current" ] && die "cannot read Pages config for $REPO"

[ -f "$SNAP/expected-200.tsv" ] || die "no baseline at $SNAP/expected-200.tsv -- run scripts/0006 first"
[ -f "$SNAP/expected-404.tsv" ] || die "no baseline at $SNAP/expected-404.tsv -- run scripts/0006 first"
echo "   baseline:        $(wc -l < "$SNAP/expected-200.tsv") must-serve, $(wc -l < "$SNAP/expected-404.tsv") must-404"

grep -q 'workflow_dispatch' .github/workflows/publish.yml 2>/dev/null \
  || die "publish.yml has no workflow_dispatch trigger; this script cannot drive it"

if [ "$MODE" = "--dry-run" ]; then
  echo
  echo "--dry-run: would PUT {build_type: workflow, cname: $DOMAIN}, dispatch publish.yml,"
  echo "           wait for it, verify both baseline sets, then PUT {https_enforced: true}."
  exit 0
fi

if [ "$verify_only" = 1 ]; then
  say "Verify-only: skipping flip, settle and dispatch"
fi

# ------------------------------------------------------------------- 1. flip
if [ "$verify_only" = 1 ]; then
  :
elif [ "$current" = "workflow" ]; then
  say "build_type is already 'workflow' -- skipping the flip"
else
  say "Switching build_type to workflow (sending cname explicitly)"
  gh api -X PUT "repos/$REPO/pages" -f build_type=workflow -f "cname=$DOMAIN" >/dev/null \
    || die "PUT failed; Pages is unchanged"
  # 204 No Content, so re-read rather than trusting the response.
  now_type="$(build_type)"; now_cname="$(pages_field cname)"
  echo "   build_type: $now_type"
  echo "   cname:      $now_cname"
  [ "$now_type" = "workflow" ] || die "build_type did not change (got '$now_type')"
  [ "$now_cname" = "$DOMAIN" ] || die "CNAME LOST (got '$now_cname') -- re-add it immediately"
fi

# ------------------------------------------------------------------- 2. settle
say "Waiting for Pages to settle"
for i in $(seq 1 20); do
  [ "$verify_only" = 1 ] && break
  st="$(pages_field status)"
  echo "   [$i] status=$st"
  case "$st" in built|"") break ;; esac
  sleep 10
done

# ---------------------------------------------------------------- 3. dispatch
say "Dispatching publish.yml and waiting for it"
if [ "$verify_only" = 1 ]; then
  echo "   skipped (--verify-only)"
else
gh workflow run publish.yml --ref main || die "could not dispatch publish.yml"
sleep 8
run_id=$(gh run list --workflow=publish.yml --limit 1 --json databaseId --jq '.[0].databaseId')
[ -n "$run_id" ] || die "no publish.yml run appeared"
echo "   run: $run_id"
if ! gh run watch "$run_id" --exit-status >/dev/null 2>&1; then
  echo "   publish.yml FAILED -- rolling back automatically" >&2
  gh run view "$run_id" --log-failed 2>&1 | tail -20 >&2
  "$0" --rollback
  die "cutover aborted; Pages restored to the branch build"
fi
echo "   publish.yml succeeded"
fi

# ------------------------------------------------------------------ 4. verify
say "Verifying against the baseline"
sleep 15
fail=0

while IFS=$'\t' read -r path want; do
  [ "$path" = "/" ] && path=""          # the site root, recorded as a literal "/"
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$SITE/$path")
  got=$(curl -sS --max-time 20 "$SITE/$path" | sha256sum | cut -d' ' -f1)
  if [ "$code" != "200" ]; then
    printf '   REGRESSION  /%-42s %s (was 200)\n' "$path" "$code"; fail=1
  elif [ "$got" != "$want" ]; then
    printf '   CHANGED     /%-42s body differs from baseline\n' "$path"; fail=1
  fi
done < "$SNAP/expected-200.tsv"

while IFS= read -r path; do
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$SITE/$path")
  [ "$code" = "404" ] || { printf '   STILL EXPOSED  /%-39s %s\n' "$path" "$code"; fail=1; }
done < "$SNAP/expected-404.tsv"

if [ "$fail" -ne 0 ]; then
  echo
  echo "Verification failed. Pages is in workflow mode with a successful deploy," >&2
  echo "so the site is being served -- inspect before deciding to roll back." >&2
  exit 1
fi
echo "   every must-serve URL is byte-identical; every must-404 URL returns 404"

# ---------------------------------------------------------- 5. enforce https
say "Enforcing HTTPS (separate call, after the build has settled)"
if [ "$(pages_field https_enforced)" = "True" ]; then
  echo "   already enforced"
else
  gh api -X PUT "repos/$REPO/pages" -F https_enforced=true >/dev/null 2>&1 \
    && echo "   https_enforced: $(pages_field https_enforced)" \
    || echo "   could not set https_enforced (may need the cert to settle; re-run later)"
fi
redirect=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "http://$DOMAIN/")
echo "   http://$DOMAIN/ -> $redirect (301/308 expected once enforced)"

say "Cutover complete"
echo "   build_type=$(build_type) cname=$(pages_field cname) https_enforced=$(pages_field https_enforced)"
echo "   Next: add the push: trigger to publish.yml, then delete _config.yml."
