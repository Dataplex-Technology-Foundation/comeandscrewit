#!/usr/bin/env python3
"""
0005_build_site_artifact.py

Assembles the directory that becomes comeandscrewit.com, and refuses to produce
one that violates the publish boundary. Called by .github/workflows/publish.yml
(at deploy time) and by ci.yml (at PR time), so a violation fails review rather
than the deploy. Also runnable by hand.

Two layers, in order:

  Layer 1 -- the directory. Only the publish root is copied. Everything else in
  the repo is absent from the artifact, not excluded from it by a rule that
  could be edited. This is the control.

  Layer 2 -- the checks below. They exist for the one thing layer 1 cannot
  catch: internal content misfiled INTO the publish root.

Transitional mode: until the layout reorganisation lands, there is no site/
directory and the publish root is the repo root, selected by pattern. The mode
is chosen automatically and reported. Patterns, not a per-file manifest -- a
per-file list drifts, and a page added during the transition would 404 silently.

Exit codes: 0 clean, 1 gate violation, 2 usage error.

Usage:
  scripts/0005_build_site_artifact.py [--out _site] [--root .] [--check]
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ALLOWED_SUFFIXES = {
    ".html", ".css", ".js", ".json", ".svg", ".xml",
    ".png", ".jpg", ".jpeg", ".webp", ".ico", ".webmanifest",
}
# robots.txt is allowlisted by exact name, never by extension. Allowlisting
# ".txt" would readmit the whole class of notes-in-a-text-file.
ALLOWED_NAMES = {"robots.txt", "CNAME"}

# Excluded from the uploaded artifact even though it lives in the publish root.
# Under build_type: workflow the custom domain comes from the Pages API setting
# and a CNAME file is ignored; shipping it would create a public /CNAME URL that
# does not exist today.
ARTIFACT_EXCLUDE = {"CNAME"}

ROOT_MODE_PATTERNS = ["*.html", "robots.txt", "sitemap.xml", "site.webmanifest",
                      "favicon.svg", "CNAME"]
ROOT_MODE_DIRS = ["assets"]

PLACEHOLDER_RE = re.compile(r"\[[^\]\n]{2,80}\]")

# Machine-consumed URL contexts. A placeholder here is never defensible, so
# these fail with no baseline and no exception. Deliberately EXCLUDES generic
# href/src/action: 42 href="[SOCIAL LINK]" and one action="[FORM ENDPOINT]"
# remain and are blocked on the site owner. Putting them here would make the
# gate unsatisfiable, which is the defect two earlier drafts of the plan shipped.
TIER_A_PATTERNS = [
    (r'<link[^>]+rel=["\']canonical["\'][^>]*>', "rel=canonical"),
    (r'<meta[^>]+property=["\']og:(url|image)["\'][^>]*>', "og:url / og:image"),
    (r'<meta[^>]+name=["\']twitter:[^"\']*["\'][^>]*>', "twitter:*"),
    (r"<loc>[^<]*</loc>", "sitemap <loc>"),
    (r"^Sitemap:.*$", "robots.txt Sitemap:"),
]
TIER_A_JSONLD_KEYS = ("url", "logo", "mainEntityOfPage")

TIER_B_SCAN_SUFFIXES = {".html", ".xml", ".txt", ".webmanifest", ".json"}
BASELINE = "internal/publish/placeholder-baseline.txt"
# Same-origin references that do not resolve. Ratcheted rather than hard-failing:
# four referenced images have never existed (og-default.png, logo.png,
# icon-192.png, icon-512.png), and supplying them needs owned artwork. Blocking
# the publish on them would make the gate unsatisfiable -- the defect two earlier
# plan drafts shipped. New breakage fails; the known set is recorded and reported.
REFS_BASELINE = "internal/publish/unresolved-refs-baseline.txt"

unresolved: set[str] = set()

problems: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    problems.append(msg)


def detect_root(repo: Path) -> tuple[Path, bool]:
    """Return (publish_root, is_transitional)."""
    site = repo / "site"
    if site.is_dir():
        return site, False
    return repo, True


def collect(repo: Path, root: Path, transitional: bool) -> list[Path]:
    if not transitional:
        return [p for p in root.rglob("*") if p.is_file() or p.is_symlink()]
    out: list[Path] = []
    for pat in ROOT_MODE_PATTERNS:
        out += sorted(root.glob(pat))
    for d in ROOT_MODE_DIRS:
        if (root / d).is_dir():
            out += [p for p in (root / d).rglob("*") if p.is_file() or p.is_symlink()]
    return out


# --------------------------------------------------------------------- layer 2

def check_symlinks(root: Path, transitional: bool) -> None:
    """No symlink may enter the publish root.

    upload-pages-artifact archives with `tar --dereference --hard-dereference`,
    so a symlink out of the publish root uploads whatever it points at --
    `ln -s ../internal site/docs` would publish the entire internal tree, past
    both layers: layer 1 sees a path inside the root, and the extension
    allowlist sees an extensionless name.

    Note the root itself is tested separately. `find site/ -type l` (with the
    trailing slash) dereferences its own start point, so a `site` that IS a
    symlink slips through silently.
    """
    if not transitional and root.is_symlink():
        fail(f"publish root {root.name!r} is itself a symlink -- refusing to build")
        return
    for p in root.rglob("*"):
        if p.is_symlink():
            fail(f"symlink in publish root: {p.relative_to(root)} -> {os.readlink(p)}")


def check_jekyll_exclusions(repo: Path, transitional: bool) -> None:
    """While Pages still builds with Jekyll, _config.yml must exclude everything
    outside the publish set.

    Until the cutover, `build_type: legacy` publishes every non-dot-prefixed path
    on the branch -- verbatim, and for markdown also as a themed HTML page with a
    rel=canonical tag. So adding any internal file to the repo publishes it.

    That is not hypothetical. The PR that removed internal editorial notes from
    the live site also added an inventory recording those notes verbatim, plus
    the script whose docstring quotes them; under `legacy` all of them would have
    been published, one at a canonical-tagged URL -- restoring the exact
    disclosure the PR removed, better indexed than the original.

    This check exists so that cannot recur silently. It is retired with the
    cutover, when the directory boundary makes it redundant.
    """
    if not transitional:
        return
    config = repo / "_config.yml"
    if not config.exists():
        fail("_config.yml is missing. Pages still builds with Jekyll, so every "
             "non-dot-prefixed path is published. See scripts/0005 docstring.")
        return
    text = config.read_text(encoding="utf-8")
    excluded = {
        line.strip().lstrip("-").strip().strip("\"'").rstrip("/")
        for line in text.splitlines()
        if line.strip().startswith("- ")
    }
    publish_set = set(ROOT_MODE_DIRS) | {
        p.name for pat in ROOT_MODE_PATTERNS for p in repo.glob(pat)
    } | {"_config.yml"}
    # Only git-tracked entries can reach the branch Pages builds from, so an
    # untracked or gitignored working-tree directory is not a finding.
    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        capture_output=True, text=True, check=False,
    )
    tracked = [t for t in proc.stdout.split("\0") if t]
    # Fail closed. If git is unavailable or reports nothing, this check has no
    # basis to pass on -- and passing would mean asserting the Jekyll build is
    # safe without having looked. An empty tracked set is never legitimate here.
    if proc.returncode != 0 or not tracked:
        fail(
            "cannot enumerate tracked files "
            f"(git exit {proc.returncode}, {len(tracked)} paths); refusing to "
            "assert that _config.yml excludes everything internal"
        )
        return
    top_level = sorted({t.split("/", 1)[0] for t in tracked})
    for name in top_level:
        if name.startswith(".") or name in publish_set or name in excluded:
            continue
        fail(
            f"{name}: present at the repo root, not in the publish set, and not "
            f"listed in _config.yml `exclude`. Under the current Jekyll build it "
            f"would be published at /{name}"
            + (f" and /{Path(name).stem}.html" if name.endswith(".md") else "")
            + ". Add it to _config.yml `exclude`, or move it under internal/."
        )


def check_extensions(files: list[Path], root: Path) -> None:
    for p in files:
        if p.is_symlink():
            continue
        rel = p.relative_to(root)
        if p.name in ALLOWED_NAMES or p.suffix.lower() in ALLOWED_SUFFIXES:
            continue
        fail(
            f"{rel}: '{p.suffix or p.name}' is not publishable. "
            f"If this is internal, move it to internal/. "
            f"If it belongs on the website, add its extension to ALLOWED_SUFFIXES "
            f"in {Path(__file__).name} and say why in the PR."
        )


def strip_jsonld(text: str) -> list[str]:
    out = []
    for m in re.finditer(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', text):
        out.append(m.group(1))
    return out


def check_tier_a(files: list[Path], root: Path) -> None:
    for p in files:
        if p.is_symlink() or p.suffix not in {".html", ".xml", ".txt"}:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(root)
        for pattern, label in TIER_A_PATTERNS:
            flags = re.IGNORECASE | (re.MULTILINE if label.startswith("robots") else 0)
            for m in re.finditer(pattern, text, flags):
                if PLACEHOLDER_RE.search(m.group(0)):
                    fail(f"{rel}: unreplaced placeholder in {label}: {m.group(0)[:100]}")
        for block in strip_jsonld(text):
            try:
                data = json.loads(block)
            except json.JSONDecodeError as exc:
                fail(f"{rel}: JSON-LD does not parse: {exc}")
                continue
            for key, value in walk_json(data):
                if key in TIER_A_JSONLD_KEYS and isinstance(value, str) \
                        and PLACEHOLDER_RE.search(value):
                    fail(f"{rel}: unreplaced placeholder in JSON-LD {key}: {value[:80]}")


def walk_json(node, key=None):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk_json(v, k)
    elif isinstance(node, list):
        for v in node:
            yield from walk_json(v, key)
    else:
        yield key, node


def tier_b_inventory(files: list[Path], root: Path) -> dict[tuple[str, str], int]:
    """Keyed (file, token) -> count.

    A scalar total is not usable as a baseline: three independent reviewers
    measured 229, 234 and 235 for the same site using different patterns, and a
    count cannot distinguish "fixed one, added one" from "no change". A keyed
    inventory makes the added key a new entry, so that case fails.

    CSS and JS are never scanned -- they hold 17 legitimate attribute selectors
    and array literals. One real placeholder does live in a JS comment
    (main.js:77), so this exclusion is slightly lossy by choice.
    """
    inv: dict[tuple[str, str], int] = {}
    for p in files:
        if p.is_symlink() or p.suffix not in TIER_B_SCAN_SUFFIXES:
            continue
        rel = str(p.relative_to(root))
        for m in PLACEHOLDER_RE.finditer(p.read_text(encoding="utf-8", errors="replace")):
            token = re.sub(r"\s+", " ", m.group(0)).strip()
            inv[(rel, token)] = inv.get((rel, token), 0) + 1
    return inv


def check_tier_b(inv: dict, repo: Path) -> None:
    path = repo / BASELINE
    lines = sorted(f"{f}\t{t}\t{n}" for (f, t), n in inv.items())
    if not path.exists():
        notes.append(f"no {BASELINE} yet -- writing it with {len(inv)} entries")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    base = set(path.read_text(encoding="utf-8").splitlines())
    added = [l for l in lines if l not in base]
    if added:
        fail(
            f"placeholder inventory grew ({len(added)} new). Fix them, or update "
            f"{BASELINE} in this PR so the change is reviewed:\n    "
            + "\n    ".join(added[:10])
        )
    removed = [l for l in base if l and l not in set(lines)]
    if removed:
        notes.append(f"{len(removed)} placeholder(s) resolved -- update {BASELINE}")


def check_references(files: list[Path], root: Path) -> None:
    """Every same-origin reference must resolve to a file in the artifact."""
    present = {str(p.relative_to(root)) for p in files if not p.is_symlink()}
    ref_re = re.compile(r'(?:href|src)=["\']([^"\'#?]+)["\']')
    # content= is only a URL on the handful of meta tags that carry one. Matching
    # it everywhere treats every meta description and title as a file path.
    meta_url_re = re.compile(
        r'<meta[^>]+(?:property|name)=["\'](?:og:(?:image|url)|twitter:image)["\']'
        r'[^>]*content=["\']([^"\'#?]+)["\']',
        re.IGNORECASE,
    )
    for p in files:
        if p.is_symlink() or p.suffix not in {".html", ".webmanifest"}:
            continue
        rel = p.relative_to(root)
        text = p.read_text(encoding="utf-8", errors="replace")
        refs = set(ref_re.findall(text)) | set(meta_url_re.findall(text))
        if p.suffix == ".webmanifest":
            try:
                data = json.loads(text)
                refs |= {v for k, v in walk_json(data) if k in ("src", "start_url")
                         and isinstance(v, str)}
            except json.JSONDecodeError:
                fail(f"{rel}: webmanifest does not parse")
        for ref in refs:
            if ref.startswith("http://"):
                fail(f"{rel}: insecure subresource {ref}")
                continue
            if PLACEHOLDER_RE.search(ref):
                continue  # Tier B, tracked in the inventory
            # An absolute URL on our own domain is still a same-origin reference
            # and must resolve. og:image and the JSON-LD logo are written this
            # way, so skipping all absolute URLs would miss exactly the four
            # broken image references this check exists to catch.
            m_own = re.match(r"^https://comeandscrewit\.com/(.*)$", ref)
            if m_own:
                ref = "/" + m_own.group(1)
            elif re.match(r"^(https?:)?//|^mailto:|^tel:|^data:|^$", ref):
                continue
            if ".." in ref:
                fail(f"{rel}: path traversal in reference: {ref}")
                continue
            target = ref.lstrip("/") if ref.startswith("/") else str((rel.parent / ref))
            target = os.path.normpath(target).rstrip("/")
            if not target or target == ".":
                continue  # site root
            if target not in present and f"{target}.html" not in present:
                unresolved.add(f"{rel}\t{ref}")


def check_unresolved_refs(repo: Path) -> None:
    path = repo / REFS_BASELINE
    lines = sorted(unresolved)
    if not path.exists():
        notes.append(f"no {REFS_BASELINE} yet -- writing it with {len(lines)} entry(ies)")
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    else:
        base = {l for l in path.read_text(encoding="utf-8").splitlines() if l}
        added = [l for l in lines if l not in base]
        if added:
            fail("new unresolved same-origin reference(s):\n    " + "\n    ".join(added))
        gone = [l for l in base if l not in set(lines)]
        if gone:
            notes.append(f"{len(gone)} reference(s) now resolve -- update {REFS_BASELINE}")
    if lines:
        notes.append(
            f"{len(lines)} known-unresolved reference(s) (see {REFS_BASELINE}); "
            "these render as broken images / unfetchable logos to crawlers")


def check_sitemap_and_robots(root: Path, files: list[Path]) -> None:
    sm, rb = root / "sitemap.xml", root / "robots.txt"
    if not sm.exists():
        return
    text = sm.read_text(encoding="utf-8")
    locs = re.findall(r"<loc>([^<]*)</loc>", text)
    present = {str(p.relative_to(root)) for p in files if not p.is_symlink()}
    for loc in locs:
        if not loc.startswith("https://"):
            fail(f"sitemap.xml: <loc> is not an absolute https URL: {loc}")
            continue
        rel = loc.split("/", 3)[3] if loc.count("/") >= 3 else ""
        if rel and rel not in present:
            fail(f"sitemap.xml: <loc> does not resolve to a published file: {loc}")
    listed = {loc.rsplit("/", 1)[-1] for loc in locs}
    for p in files:
        if p.suffix != ".html" or p.is_symlink() or p.parent != root:
            continue
        text_p = p.read_text(encoding="utf-8", errors="replace")
        noindex = re.search(r'name=["\']robots["\'][^>]*noindex', text_p, re.I)
        if noindex and p.name in listed:
            fail(f"sitemap.xml lists {p.name}, which is noindex")
    if rb.exists():
        for line in rb.read_text(encoding="utf-8").splitlines():
            if line.startswith("Sitemap:") and PLACEHOLDER_RE.search(line):
                fail(f"robots.txt: unreplaced placeholder in {line}")


# ------------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", type=Path)
    ap.add_argument("--out", default="_site", type=Path)
    ap.add_argument("--check", action="store_true", help="run the gate, build nothing")
    args = ap.parse_args()

    repo = args.root.resolve()
    root, transitional = detect_root(repo)
    print(f"publish root: {root.relative_to(repo) if root != repo else '.'}"
          f"{'  (transitional: pattern-selected from repo root)' if transitional else ''}")

    check_symlinks(root, transitional)
    if problems:
        return report()

    files = collect(repo, root, transitional)
    if not files:
        fail("publish root contains no files")
        return report()

    check_jekyll_exclusions(repo, transitional)
    check_extensions(files, root)
    check_tier_a(files, root)
    check_tier_b(tier_b_inventory(files, root), repo)
    check_references(files, root)
    check_unresolved_refs(repo)
    check_sitemap_and_robots(root, files)

    if problems:
        return report()

    print(f"gate: {len(files)} file(s) pass all checks")
    if args.check:
        return report()

    out = (repo / args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    copied = 0
    for p in files:
        rel = p.relative_to(root)
        if str(rel) in ARTIFACT_EXCLUDE:
            notes.append(f"excluded from artifact: {rel} (domain comes from the Pages API)")
            continue
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
        copied += 1
    print(f"built {args.out}/ with {copied} file(s)")
    return report()


def report() -> int:
    for n in notes:
        print(f"  note: {n}")
    if problems:
        print(f"\nGATE FAILED -- {len(problems)} violation(s):", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
