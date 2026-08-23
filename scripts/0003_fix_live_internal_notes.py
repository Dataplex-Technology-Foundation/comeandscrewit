#!/usr/bin/env python3
"""
0003_fix_live_internal_notes.py

PR-0. Removes internal editorial material currently rendered on the live site,
and replaces the unsubstituted [DOMAIN] token with the real domain.

Both changes are mechanical and need no editorial input:

  1. Every element carrying class="placeholder" is an internal build note. All 7
     address the site's owner, not a visitor -- the investor page currently
     renders "No financial figures, projections, or securities language until
     Luc / counsel supply them. Do not fabricate traction, funding, or metrics."
     Removing such a note replaces it with nothing; there is no copy decision.

  2. A heading whose entire body was one of those notes is removed with it.
     about.html's "Team" and "Company" sections are the only two in this state.
     An empty section renders worse than an absent one.

  3. Two build-note comments: the "BUILD NOTE FOR LUC" block atop
     our-approach.html, and the authoring instruction in sitemap.xml. The bare
     "<!-- [ANALYTICS ID] -->" markers elsewhere are left alone (they name no one
     and carry no instruction); index.html's longer variant is normalised to
     match them.

  4. [DOMAIN] -> comeandscrewit.com, 110 occurrences. Repairs 14 canonical tags,
     every og:url, all 12 sitemap <loc> values, and robots.txt's Sitemap: line,
     which are currently invalid URLs -- "[" and "]" are reserved for IPv6
     literals, so https://[DOMAIN]/ fails URI parsing and the sitemap is unusable.

Deliberately NOT done (plan 0002 section 11, "known-deferred"): og:image /
twitter:image / JSON-LD logo reference five image files that do not exist.
Substituting the domain turns an invalid URL into a valid one that 404s. Visitor
outcome is unchanged -- no preview image either way -- but Search Console will
start reporting an unfetchable logo. Fixing it needs artwork or a decision to
strip the properties; neither is mechanical.

Idempotent. Run with --check to preview.

Usage:
  scripts/0003_fix_live_internal_notes.py [--check] [--root PATH]
"""

import argparse
import re
import sys
from pathlib import Path

DOMAIN = "comeandscrewit.com"

PLACEHOLDER_OPEN_RE = re.compile(r'^[ \t]*<(div|p)\b[^>]*class="placeholder"')
HEADING_RE = re.compile(r'^[ \t]*<h([1-6])\b[^>]*>.*?</h\1>[ \t]*$')
BOUNDARY_RE = re.compile(r'^\s*(?:<hr\b|</div>|</article>|</section>)')
BUILD_NOTE_RE = re.compile(r'^<!--\s*\n(?:.*\n)*?.*BUILD NOTE FOR LUC(?:.*\n)*?-->\n', re.MULTILINE)
SITEMAP_COMMENT_RE = re.compile(r'^<!--\s*Update <lastmod>.*?-->\n', re.MULTILINE | re.DOTALL)
ANALYTICS_RE = re.compile(r'<!--\s*\[ANALYTICS ID\][^>]*?-->')
ANALYTICS_BARE = "<!-- [ANALYTICS ID] -->"


def find_element_end(lines: list[str], start: int) -> int:
    """Index of the line closing the element opened at `start` (inclusive).

    Counts opening and closing tags of the element's own tag name. Deliberately
    NOT a regex over the whole document: a pattern like <h(\\d)>.*?</h\\1> plus a
    lookahead is unsafe, because when the minimal body fails the lookahead the
    engine grows the lazy quantifier until it succeeds -- which on the first
    attempt at this script swallowed the homepage hero and feature sections.
    """
    tag = PLACEHOLDER_OPEN_RE.match(lines[start]).group(1)
    depth = 0
    for i in range(start, len(lines)):
        depth += len(re.findall(rf"<{tag}\b", lines[i]))
        depth -= len(re.findall(rf"</{tag}>", lines[i]))
        if depth <= 0:
            return i
    raise ValueError(f"unterminated <{tag} class=\"placeholder\"> at line {start + 1}")


def next_content_line(lines: list[str], after: int) -> str:
    return next((l for l in lines[after + 1:] if l.strip()), "")


def prev_content_index(lines: list[str], before: int) -> int | None:
    for i in range(before - 1, -1, -1):
        if lines[i].strip():
            return i
    return None


def strip_internal_notes(text: str) -> tuple[str, list[str], list[str]]:
    """Remove placeholder elements and any heading they alone occupied.

    Returns (new_text, notes, removed_source_lines).
    """
    lines = text.split("\n")
    notes: list[str] = []
    removed: list[str] = []

    while True:
        for i, line in enumerate(lines):
            if not PLACEHOLDER_OPEN_RE.match(line):
                continue
            end = find_element_end(lines, i)
            block = lines[i:end + 1]
            label = re.search(r"\[[^\]]*\]", " ".join(block))
            notes.append(f"removed placeholder element: {label.group(0) if label else '?'}")

            # Was a heading's entire body just this note? Only then is it orphaned.
            # A heading followed by </div> is NOT generally orphaned -- a hero <h1>
            # inside <div class="wrap"> is exactly that shape and must be kept.
            drop_from = i
            hi = prev_content_index(lines, i)
            if hi is not None:
                hm = HEADING_RE.match(lines[hi])
                if hm:
                    after = next_content_line(lines, end)
                    am = HEADING_RE.match(after)
                    if (am and int(am.group(1)) <= int(hm.group(1))) or BOUNDARY_RE.match(after):
                        notes.append(
                            "removed heading whose only content was that note: "
                            f"{re.sub(r'<[^>]+>', '', lines[hi]).strip()!r}"
                        )
                        drop_from = hi

            removed += lines[drop_from:end + 1]
            del lines[drop_from:end + 1]
            break
        else:
            return "\n".join(lines), notes, removed


def visible_text(text: str) -> list[str]:
    """Prose a visitor would read, one entry per source line, tags stripped."""
    # Comments, <script> (JSON-LD included) and <style> are not visitor prose.
    text = re.sub(r"(?s)<!--.*?-->", "", text)
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", text)
    out = []
    for line in text.split("\n"):
        s = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", line)).strip()
        if s:
            out.append(s)
    return out


def process(path: Path) -> tuple[str, list[str], list[str]]:
    text = path.read_text(encoding="utf-8")
    notes: list[str] = []
    removed: list[str] = []

    if path.suffix == ".html":
        text, n, r = strip_internal_notes(text)
        notes += n
        removed += r

        if BUILD_NOTE_RE.search(text):
            notes.append("removed BUILD NOTE FOR LUC comment block")
            removed += BUILD_NOTE_RE.search(text).group(0).split("\n")
            text = BUILD_NOTE_RE.sub("", text)

        new_text, count = ANALYTICS_RE.subn(ANALYTICS_BARE, text)
        if new_text != text:
            notes.append(f"normalised {count} analytics comment(s)")
            text = new_text

    if path.name == "sitemap.xml" and SITEMAP_COMMENT_RE.search(text):
        notes.append("removed shipped authoring instruction")
        text = SITEMAP_COMMENT_RE.sub("", text)

    n_domain = text.count("[DOMAIN]")
    if n_domain:
        notes.append(f"substituted {n_domain} [DOMAIN] -> {DOMAIN}")
        text = text.replace("[DOMAIN]", DOMAIN)

    return text, notes, removed


def content_loss(path: Path, before: str, after: str, removed: list[str]) -> list[str]:
    """Every line of visitor prose that vanished must come from a removed block.

    This is the check that was missing when an earlier revision silently deleted
    the homepage hero while still passing tag-balance and token-absence
    assertions. Balance and absence say nothing about whether real content
    survived; this does.
    """
    # Compare post-substitution on both sides, so replacing [DOMAIN] in visible
    # prose does not register as a line disappearing.
    kept = set(visible_text(after))
    removed_prose = set(visible_text("\n".join(removed).replace("[DOMAIN]", DOMAIN)))
    return [
        f"{path.name}: unaccounted content loss: {line[:90]!r}"
        for line in visible_text(before.replace("[DOMAIN]", DOMAIN))
        if line not in kept and line not in removed_prose
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report without writing")
    ap.add_argument("--root", default=".", type=Path)
    args = ap.parse_args()

    root: Path = args.root.resolve()
    targets = [p for p in sorted(root.glob("*.html")) + [root / "sitemap.xml", root / "robots.txt"]
               if p.exists()]
    if not targets:
        print(f"error: no site files found under {root}", file=sys.stderr)
        return 2

    results, problems, changed = [], [], 0
    for path in targets:
        before = path.read_text(encoding="utf-8")
        after, notes, removed = process(path)
        if not notes:
            continue
        changed += 1
        print(path.relative_to(root))
        for note in notes:
            print(f"    {note}")
        if path.suffix == ".html":
            problems += content_loss(path, before, after, removed)
            for tag in ("div", "p", "section", "article"):
                o, c = len(re.findall(rf"<{tag}\b", after)), len(re.findall(rf"</{tag}>", after))
                if o != c:
                    problems.append(f"{path.name}: <{tag}> {o} open vs {c} close")
        results.append((path, after))

    if problems:
        print("\nABORTED - nothing written:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    if args.check:
        print(f"\n--check: {changed} file(s) would change, no content loss detected")
        return 0

    for path, after in results:
        path.write_text(after, encoding="utf-8")

    residual = [f"{p.name}: {tok}" for p in targets for tok in ("[DOMAIN]", 'class="placeholder"', "Luc")
                if tok in p.read_text(encoding="utf-8")]
    if residual:
        print("\nPOST-CONDITION FAILURES:", file=sys.stderr)
        for r in residual:
            print(f"  {r}", file=sys.stderr)
        return 1

    print(f"\n{changed} file(s) changed; no content loss, markup balanced, no residual tokens")
    return 0


if __name__ == "__main__":
    sys.exit(main())
