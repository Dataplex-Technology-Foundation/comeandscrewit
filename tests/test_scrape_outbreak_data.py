"""
Regression tests for scripts/scrape_outbreak_data.py.

Deliberately narrow: these lock in two specific bugs found during manual
testing (DTS-806 follow-up) so they can't silently regress. Not a general
test suite for the scraper -- there's no live-network coverage here, only
the pure-function HTML parsing.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import scrape_outbreak_data as m  # noqa: E402


class ParseConfirmedCasesTests(unittest.TestCase):
    def test_county_requires_state_adjacency_not_bare_mention(self):
        """A bare "<Name> County" mention with no confirmed-state adjacency
        must NOT be picked up (regression: previously matched any county
        name anywhere on the page, e.g. nav links or unrelated extension
        office references)."""
        html = """<html><body>
        <p>Texas Animal Health Commission NWS Website</p>
        <p>See also Orange County extension office for unrelated info.</p>
        </body></html>"""
        parsed = m.parse_confirmed_cases(html)
        self.assertNotIn("Orange", parsed.get("affectedCounties", []))

    def test_county_with_state_adjacency_is_captured(self):
        """A county paired with a confirmed state ("<Name> County, <State>")
        should be captured, including two-word county names."""
        html = """<html><body>
        <p>Texas Animal Health Commission NWS Website</p>
        <p>Zavala County, Texas reported new activity.</p>
        <p>La Salle County, Texas also confirmed.</p>
        </body></html>"""
        parsed = m.parse_confirmed_cases(html)
        self.assertEqual(parsed.get("affectedCounties"), ["Zavala", "La Salle"])

    def test_adjacent_element_text_does_not_bleed_into_county_name(self):
        """Regression: BeautifulSoup.get_text(" ") joined separate elements
        with a plain space, so unrelated capitalized text immediately
        preceding a county mention in the next element (e.g. "...NWS
        Website" followed by "Zavala County, Texas") could be captured as
        a false two-word county name ("Website Zavala"). Elements must now
        be joined with a newline, which the regex's literal-space internal
        gap correctly refuses to cross."""
        html = """<html><body>
        <p>Texas Animal Health Commission NWS Website</p><p>Zavala County, Texas reported new activity.</p>
        </body></html>"""
        parsed = m.parse_confirmed_cases(html)
        self.assertEqual(parsed.get("affectedCounties"), ["Zavala"])

    def test_degraded_parse_flag_when_fetch_succeeds_but_nothing_matches(self):
        """Regression: a successful fetch (non-empty HTML) that yields zero
        parsed fields must be distinguishable from "nothing changed today"
        so the workflow can fail loudly instead of looking like a quiet
        no-diff run."""
        html = "<html><body><p>Nothing relevant on this page.</p></body></html>"
        parsed = m.parse_confirmed_cases(html)
        cases_page_degraded = html is not None and not parsed
        self.assertEqual(parsed, {})
        self.assertTrue(cases_page_degraded)

    def test_normal_successful_parse_is_not_flagged_degraded(self):
        """A run that parses at least one field (even if not all of them,
        e.g. case count is JS-rendered and unavailable) must NOT be
        flagged degraded."""
        html = """<html><body>
        <p>Texas Animal Health Commission NWS Website</p>
        </body></html>"""
        parsed = m.parse_confirmed_cases(html)
        cases_page_degraded = html is not None and not parsed
        self.assertFalse(cases_page_degraded)
        self.assertEqual(parsed.get("usStates"), ["Texas"])


if __name__ == "__main__":
    unittest.main()
