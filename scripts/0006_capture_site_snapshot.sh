#!/usr/bin/env bash
#
# 0006_capture_site_snapshot.sh
#
# Records what the live site serves, so the Pages cutover can be proved to have
# changed nothing a visitor sees. Must run BEFORE scripts/0007_cutover_pages.sh.
#
# Writes two DISJOINT sets, which is the point:
#
#   expected-200.tsv   URL <tab> sha256 of the response body.
#                      Derived from the publish set -- `find site -type f` after
#                      the reorg, or the publish-set patterns before it.
#                      NEVER from a live crawl: a crawl also returns Jekyll's own
#                      generated URLs (e.g. /assets/css/style.css from the
#                      default theme) which have no tracked source and correctly
#                      disappear at cutover. Putting those in the 200 set would
#                      make the no-regression check unsatisfiable.
#
#   expected-404.tsv   Everything that must NOT be served afterwards: every
#                      tracked non-published path, its Jekyll .html twin, README
#                      directory indexes, and /CNAME.
#
# An earlier draft snapshotted "every public URL" and then required the exposed
# ones to 404 -- two criteria that could not both pass. Hence two sets.
#
# Usage: scripts/0006_capture_site_snapshot.sh [outdir]   (default artifacts/)

set -uo pipefail

SITE="${SITE:-https://comeandscrewit.com}"
OUT="${1:-artifacts}"
mkdir -p "$OUT"

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root" || exit 1

is_published() {
  case "$1" in
    *.html|assets/*|CNAME|favicon.svg|robots.txt|site.webmanifest|sitemap.xml) return 0 ;;
    *) return 1 ;;
  esac
}

# ---------------------------------------------------------------- expected 200
: > "$OUT/expected-200.tsv"
if [ -d site ]; then
  mapfile -t published < <(find site -type f | sed 's|^site/||' | sort)
else
  mapfile -t published < <(git ls-files | while read -r f; do is_published "$f" && echo "$f"; done | sort)
fi

echo "Capturing $SITE  (${#published[@]} published paths)"
for f in "${published[@]}"; do
  # CNAME is excluded from the artifact and is 404 today; it belongs to the
  # other set, not this one.
  [ "$f" = "CNAME" ] && continue
  body=$(curl -sS --max-time 20 "$SITE/$f")
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$SITE/$f")
  if [ "$code" != "200" ]; then
    printf '  WARNING %-44s %s (not 200 before cutover)\n' "/$f" "$code" >&2
    continue
  fi
  printf '%s\t%s\n' "$f" "$(printf '%s' "$body" | sha256sum | cut -d' ' -f1)" >> "$OUT/expected-200.tsv"
done
# The bare root is served from index.html and must be checked in its own right.
printf '%s\t%s\n' "" "$(curl -sS --max-time 20 "$SITE/" | sha256sum | cut -d' ' -f1)" >> "$OUT/expected-200.tsv"

# ---------------------------------------------------------------- expected 404
{
  echo "CNAME"
  git ls-files | while read -r f; do
    is_published "$f" && continue
    case "$f" in .*|*/.*) continue ;; esac
    echo "$f"
    case "$f" in
      *.md)
        echo "${f%.md}.html"
        if [ "$(basename "$f")" = "README.md" ] && [ "$(dirname "$f")" != "." ]; then
          echo "$(dirname "$f")/"
          echo "$(dirname "$f")/index.html"
        fi
      ;;
    esac
  done
} | sort -u > "$OUT/expected-404.tsv"

echo
echo "wrote $OUT/expected-200.tsv  ($(wc -l < "$OUT/expected-200.tsv") URLs with checksums)"
echo "wrote $OUT/expected-404.tsv  ($(wc -l < "$OUT/expected-404.tsv") URLs that must not be served)"

# Disjointness is the property the earlier draft violated, so assert it here
# rather than trusting the derivations above.
overlap=$(comm -12 <(cut -f1 "$OUT/expected-200.tsv" | sort -u) <(sort -u "$OUT/expected-404.tsv"))
if [ -n "$overlap" ]; then
  echo "ERROR: the two sets overlap, so no cutover can satisfy both:" >&2
  echo "$overlap" >&2
  exit 1
fi
echo "sets are disjoint"
