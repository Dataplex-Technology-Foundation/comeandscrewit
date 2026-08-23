#!/usr/bin/env bash
#
# 0002_exposure_inventory.sh
#
# Generates, never hand-maintains, the two lists the plan depends on:
#
#   --exposure     every URL currently reachable on comeandscrewit.com that
#                  should not be, probed live
#   --disposition  every tracked path mapped to its destination under the
#                  site/ + internal/ layout, and whether it is published
#
# Both are derived from `git ls-files`. Three successive drafts of the plan
# carried a hand-written version of one or the other, and all three were wrong:
# v1 listed 13 of 25 exposed URLs and its acceptance criterion inherited the
# undercount; v2 deleted the disposition table, which is how a .md inside the
# asset tree became a site-down risk; v3 restored the table and still omitted a
# tracked file whose publication would have restored the worst disclosure the
# work exists to remove. The lists are not the kind of thing a human keeps
# correct, so nothing downstream reads a prose list any more.
#
# Exit status is always 0 -- this reports, it does not gate. scripts/0005 gates.
#
# Usage:
#   scripts/0002_exposure_inventory.sh --exposure [--quiet]
#   scripts/0002_exposure_inventory.sh --disposition

set -uo pipefail

SITE="${SITE:-https://comeandscrewit.com}"
MODE="${1:---exposure}"
QUIET="${2:-}"

# Everything that legitimately reaches the domain. Kept in sync with
# ROOT_MODE_PATTERNS / ROOT_MODE_DIRS in scripts/0005_build_site_artifact.py.
is_published() {
  case "$1" in
    *.html|assets/*|CNAME|favicon.svg|robots.txt|site.webmanifest|sitemap.xml) return 0 ;;
    *) return 1 ;;
  esac
}

# Where each non-published path goes in the target layout.
destination() {
  case "$1" in
    README.md)                     echo "internal/docs/deployment.md" ;;
    docs/adr/*)                    echo "internal/${1}" ;;
    reference/*)                   echo "internal/${1}" ;;
    scripts/[0-9][0-9][0-9][0-9]_*)
                                   echo "${1}  (numbered ops script, stays)" ;;
    scripts/*.py|scripts/requirements.txt)
                                   echo "internal/automation/${1#scripts/}" ;;
    tests/*)                       echo "internal/${1}" ;;
    Dockerfile|nginx.conf|docker-compose.yml)
                                   echo "internal/container/${1}" ;;
    internal/*)                    echo "${1}  (already in place)" ;;
    .github/*|.gitignore)          echo "${1}  (unchanged)" ;;
    _config.yml)                   echo "DELETED after cutover (transitional)" ;;
    *)                             echo "*** NO DESTINATION DEFINED ***" ;;
  esac
}

case "$MODE" in
--disposition)
  printf '%-52s  %-8s  %s\n' "TRACKED PATH" "PUBLISH" "DESTINATION"
  printf '%-52s  %-8s  %s\n' "$(printf '%.0s-' {1..52})" "--------" "-----------"
  undefined=0
  while IFS= read -r f; do
    if is_published "$f"; then
      printf '%-52s  %-8s  %s\n' "$f" "yes" "site/${f}"
    else
      dest="$(destination "$f")"
      printf '%-52s  %-8s  %s\n' "$f" "no" "$dest"
      case "$dest" in *"NO DESTINATION"*) undefined=$((undefined+1)) ;; esac
    fi
  done < <(git ls-files)
  echo
  echo "tracked paths: $(git ls-files | wc -l)"
  if [ "$undefined" -gt 0 ]; then
    echo "WARNING: $undefined path(s) have no destination defined -- add a case to destination()"
  else
    echo "every tracked path has a destination"
  fi
  ;;

--exposure)
  probe() {
    local url="$1" label="${2:-}"
    local code
    code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$SITE/$1" 2>/dev/null)
    if [ "$code" = "200" ]; then
      printf '200  /%s%s\n' "$url" "$label"
      return 0
    fi
    [ -n "$QUIET" ] || printf '%s  /%s\n' "$code" "$url" >&2
    return 1
  }

  echo "Probing $SITE for paths that should not be published."
  echo "Derived from git ls-files, not from a hand-written list."
  echo
  count=0
  seen_dirs=""
  while IFS= read -r f; do
    is_published "$f" && continue
    case "$f" in .*|*/.*) continue ;; esac   # Jekyll excludes dot-prefixed paths

    probe "$f" && count=$((count+1))

    # Markdown is published twice: raw, and as a themed HTML page with a
    # rel=canonical tag. The rendered twin is the worse half -- it is presented
    # to crawlers as first-class site content.
    case "$f" in
      *.md)
        probe "${f%.md}.html" "   <-- Jekyll-rendered, canonical-tagged" && count=$((count+1))
        # A README also becomes its directory's index. This is the case a
        # "tracked path + .html twin" enumeration cannot see, and it is how
        # /assets/img/ stayed hidden from an earlier draft's inventory.
        case "$(basename "$f")" in
          README.md)
            d="$(dirname "$f")"
            # A root-level README's directory is the site root itself, whose
            # index is the homepage -- not exposure.
            [ "$d" = "." ] && continue
            case " $seen_dirs " in *" $d "*) ;; *)
              seen_dirs="$seen_dirs $d"
              probe "$d/" "   <-- directory index" && count=$((count+1))
              probe "$d/index.html" "   <-- directory index (explicit)" && count=$((count+1))
            ;; esac
          ;;
        esac
      ;;
    esac
  done < <(git ls-files)

  echo
  echo "EXPOSED URLS: $count"
  [ "$count" -eq 0 ] && echo "Boundary holds: nothing outside the publish set is reachable."
  ;;

*)
  echo "usage: $0 [--exposure|--disposition]" >&2
  exit 2
  ;;
esac
exit 0
