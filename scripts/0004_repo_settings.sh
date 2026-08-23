#!/usr/bin/env bash
#
# 0004_repo_settings.sh
#
# Repository-level settings required by plan 0002. Idempotent: every change is
# checked before it is applied, and re-running is a no-op that reports drift.
#
#   1. Allow Actions to create pull requests. THIS IS THE FIX for the daily
#      outbreak-data pipeline, which has failed every scheduled run since
#      2026-08-21 with "GitHub Actions is not permitted to create or approve
#      pull requests". The scraper succeeds and detects changes; only PR
#      creation is refused, so fresh outbreak data is fetched and discarded
#      daily on a tracker whose sitemap declares changefreq: daily.
#
#      Note GitHub bundles "create" and "approve" behind this single flag --
#      they cannot be separated. Branch protection was recommended alongside it
#      and declined (plan 0002, D3), so a workflow can now also approve a PR on
#      a branch with no required review. Recorded in plan 0002 section 8.4.
#
#   2. Create the automated-data-refresh label. Both scheduled workflows pass it
#      to peter-evans/create-pull-request. It has never existed -- but note this
#      was NOT why automation was broken (see 1); no automated PR has ever been
#      created, so labelling was never reached.
#
#   3. Narrow the github-pages environment branch policy, which currently
#      permits a gh-pages branch that does not exist.
#
#   4. Point the repo homepage at the custom domain instead of the stale
#      github.io URL.
#
#   5. Best-effort: require SHA-pinned actions. The repo already pins every
#      "uses:" by convention; this asks the platform to enforce it. Availability
#      on a Free-plan org is unverified, so a failure here is reported and does
#      not fail the script.
#
# Usage: scripts/0004_repo_settings.sh [--check]

set -uo pipefail

REPO="${REPO:-Dataplex-Technology-Foundation/comeandscrewit}"
CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

changed=0 failed=0

say()  { printf '\n== %s\n' "$*"; }
skip() { printf '   already correct: %s\n' "$*"; }
did()  { printf '   CHANGED: %s\n' "$*"; changed=$((changed+1)); }
warn() { printf '   FAILED (non-fatal): %s\n' "$*"; failed=$((failed+1)); }
plan() { printf '   would change: %s\n' "$*"; changed=$((changed+1)); }

# ---------------------------------------------------------------- 1. Actions PRs
say "Actions permitted to create pull requests"
current=$(gh api "repos/$REPO/actions/permissions/workflow" --jq '.can_approve_pull_request_reviews')
if [ "$current" = "true" ]; then
  skip "can_approve_pull_request_reviews=true"
elif [ "$CHECK" = 1 ]; then
  plan "can_approve_pull_request_reviews false -> true"
else
  # Must resend default_workflow_permissions; the endpoint replaces the object.
  perms=$(gh api "repos/$REPO/actions/permissions/workflow" --jq '.default_workflow_permissions')
  if gh api -X PUT "repos/$REPO/actions/permissions/workflow" \
       -f "default_workflow_permissions=$perms" \
       -F "can_approve_pull_request_reviews=true" >/dev/null 2>&1; then
    now=$(gh api "repos/$REPO/actions/permissions/workflow" --jq '.can_approve_pull_request_reviews')
    if [ "$now" = "true" ]; then
      did "can_approve_pull_request_reviews=true (default_workflow_permissions kept at '$perms')"
    else
      warn "PUT reported success but the flag is still '$now' -- likely enforced by an
        organisation-level policy. An org owner must allow it at
        https://github.com/organizations/Dataplex-Technology-Foundation/settings/actions"
    fi
  else
    warn "could not set can_approve_pull_request_reviews -- probably an org-level policy;
        an org owner must change it. The repo token has no admin:org scope, so this
        script cannot read or write the org setting to confirm."
  fi
fi

# ------------------------------------------------------------------- 2. Label
say "automated-data-refresh label"
if gh api "repos/$REPO/labels/automated-data-refresh" >/dev/null 2>&1; then
  skip "label exists"
elif [ "$CHECK" = 1 ]; then
  plan "create label automated-data-refresh"
else
  if gh api -X POST "repos/$REPO/labels" \
       -f name=automated-data-refresh -f color=0E8A16 \
       -f description="Opened by a scheduled data-refresh workflow" >/dev/null 2>&1; then
    did "created label"
  else
    warn "could not create label"
  fi
fi

# --------------------------------------------------- 3. Pages env branch policy
say "github-pages environment branch policy"
policies=$(gh api "repos/$REPO/environments/github-pages/deployment-branch-policies" \
             --jq '.branch_policies[] | "\(.id) \(.name)"' 2>/dev/null)
if [ -z "$policies" ]; then
  skip "no branch policies to narrow"
else
  while read -r id name; do
    [ -z "${id:-}" ] && continue
    if [ "$name" = "main" ]; then
      skip "keeping policy for 'main'"
    elif [ "$CHECK" = 1 ]; then
      plan "remove branch policy '$name' (branch does not exist)"
    elif git ls-remote --exit-code --heads "https://github.com/$REPO.git" "$name" >/dev/null 2>&1; then
      skip "policy '$name' refers to a real branch; leaving it"
    elif gh api -X DELETE \
           "repos/$REPO/environments/github-pages/deployment-branch-policies/$id" >/dev/null 2>&1; then
      did "removed branch policy '$name' (no such branch)"
    else
      warn "could not remove branch policy '$name'"
    fi
  done <<<"$policies"
fi

# ---------------------------------------------------------------- 4. Homepage
say "repository homepage"
want="https://comeandscrewit.com"
have=$(gh api "repos/$REPO" --jq '.homepage // ""')
if [ "$have" = "$want" ]; then
  skip "$want"
elif [ "$CHECK" = 1 ]; then
  plan "homepage '$have' -> '$want'"
elif gh api -X PATCH "repos/$REPO" -f "homepage=$want" >/dev/null 2>&1; then
  did "homepage '$have' -> '$want'"
else
  warn "could not set homepage"
fi

# ------------------------------------------------------- 5. SHA pinning (soft)
say "require SHA-pinned actions (best-effort)"
pinned=$(gh api "repos/$REPO/actions/permissions" --jq '.sha_pinning_required // false')
if [ "$pinned" = "true" ]; then
  skip "sha_pinning_required=true"
elif [ "$CHECK" = 1 ]; then
  plan "attempt sha_pinning_required=true"
else
  allowed=$(gh api "repos/$REPO/actions/permissions" --jq '.allowed_actions')
  if gh api -X PUT "repos/$REPO/actions/permissions" \
       -F enabled=true -f "allowed_actions=$allowed" -F sha_pinning_required=true \
       >/dev/null 2>&1 \
     && [ "$(gh api "repos/$REPO/actions/permissions" --jq '.sha_pinning_required')" = "true" ]; then
    did "sha_pinning_required=true"
  else
    warn "sha_pinning_required not settable here (plan 0002 records this as
        best-effort, not an acceptance criterion). Every 'uses:' in this repo is
        already SHA-pinned by convention; this would only have enforced it."
  fi
fi

# ------------------------------------------------------------------- Summary
say "Summary"
if [ "$CHECK" = 1 ]; then
  printf '   --check: %d change(s) pending\n' "$changed"
else
  printf '   %d change(s) applied, %d non-fatal failure(s)\n' "$changed" "$failed"
  [ "$failed" -gt 0 ] && printf '   Review the FAILED lines above -- some need an org owner.\n'
fi
exit 0
