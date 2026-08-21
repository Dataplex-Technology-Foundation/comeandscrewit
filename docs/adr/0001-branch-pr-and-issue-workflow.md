# ADR 0001: All changes via feature branch + PR, referencing an issue/ticket

## Status

Accepted — 2026-08-21

## Context

Work on this repository (outbreak data tracker, scraper hardening, CI checks,
Docker/nginx containerization, VERIFY-placeholder cleanup) has so far been
done on short-lived feature branches merged via pull request, which has
worked well: it gives every change a review point and a CI gate before it
lands on `main`. What's been missing is a consistent link back to a tracked
issue explaining *why* a change was made, which makes it harder to
reconstruct intent later from `git log` alone.

## Decision

- No direct commits to `main`. Every change — code, content, config, or docs
  — is made on a feature branch and lands via a pull request.
- Pull requests should typically reference the issue/ticket that motivated
  the change (e.g. `Closes #6`, or a mention in the PR description). A PR
  that isn't tied to a tracked issue should say why (e.g. a trivial typo fix)
  rather than silently omitting the reference.
- Branch names keep the existing convention: `<type>/<short-description>`
  (e.g. `content/...`, `fix/...`, `infra/...`, `docs/...`).
- CI (`.github/workflows/ci.yml`) must pass before merging.

## Consequences

- Every merged change is traceable to an issue describing intent, not just a
  commit message.
- Slightly more overhead for small changes (open an issue first, or note in
  the PR why one wasn't needed), in exchange for a clearer project history.
- This applies to human and agent-driven changes alike.
