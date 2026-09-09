#!/usr/bin/env python3
"""
Unit tests for PotatoClaw Browser Agent:
- Qwen Browser Policy Guardrails & Action Normalization
- Irreversible Submit Gate Protection
- Deterministic Non-Premium X Thread Splitter
- Sentence/Paragraph & Word Boundary Preservation
- Post Numbering and Safety Margin Accounting
"""

import unittest
import sys
from unittest.mock import patch
import potato_browser_agent as browser
from potato_browser_agent import split_x_thread, BrowserThreadState


class BrowserPolicyTests(unittest.TestCase):
    def test_thread_uses_cdp_launcher_and_preserves_failure(self):
        for status in ("PREPARED_SAFE", "SUBMIT_UNVERIFIED", "CDP_NOT_AVAILABLE"):
            with self.subTest(status=status), patch.object(
                browser, "compose_x_thread_cdp", return_value={"status": status}
            ) as compose, patch.object(browser, "open_url_direct") as intent:
                result = browser.run_browser_agent(
                    "Post this on X as a non-Premium thread: First update.\n\nSecond update.",
                    allow_submit=True,
                )
                self.assertEqual(result["status"], status)
                compose.assert_called_once_with(
                    ["1/2 First update.", "2/2 Second update."], allow_submit=True
                )
                intent.assert_not_called()

    def test_extracts_json_from_fence(self):
        obj = browser._extract_object('```json\n{"action":"click","ref":"e12"}\n```')
        self.assertEqual(obj, {"action": "click", "ref": "e12"})

    def test_normalizes_small_model_aliases(self):
        self.assertEqual(
            browser.normalize_action({"action": "goto", "url": "https://x.com"}),
            {"action": "navigate", "url": "https://x.com"},
        )
        self.assertEqual(
            browser.normalize_action({"action": "post", "ref": "e9"}),
            {"action": "submit", "ref": "e9"},
        )

    def test_normalizes_wait_and_rejects_invalid_seconds(self):
        self.assertEqual(
            browser.normalize_action({"action": "wait", "seconds": 2}),
            {"action": "wait", "seconds": "2"},
        )
        with self.assertRaises(browser.BrowserPolicyError):
            browser.normalize_action({"action": "wait", "seconds": "not-a-number"})

    def test_rejects_missing_required_field(self):
        with self.assertRaises(browser.BrowserPolicyError):
            browser.normalize_action({"action": "click"})

    def test_submit_ref_detection_allows_add_post(self):
        snap = '- button "Add post" [ref=e20]'
        self.assertFalse(browser.ref_looks_irreversible(snap, "e20"))

    def test_submit_ref_detection_blocks_post_all(self):
        snap = '- button "Post all" [ref=e30]'
        self.assertTrue(browser.ref_looks_irreversible(snap, "e30"))

    def test_submit_ref_detection_does_not_mix_adjacent_controls(self):
        snap = '- button "Add post" [ref=e20]\n- button "Post all" [ref=e30]'
        self.assertFalse(browser.ref_looks_irreversible(snap, "e20"))
        self.assertTrue(browser.ref_looks_irreversible(snap, "e30"))

    def test_submit_requires_approval(self):
        ok, message, approval = browser.execute_action(
            {"action": "submit", "ref": "e30"},
            '- button "Post all" [ref=e30]',
            allow_submit=False,
        )
        self.assertFalse(ok)
        self.assertTrue(approval)
        self.assertIn("APPROVAL_REQUIRED", message)

    def test_resolved_openclaw_cli_executes_browser_command(self):
        script = "import sys; print(' '.join(sys.argv[1:]))"
        with patch.object(browser, "_OPENCLAW_CLI_CHECKED", True), patch.object(
            browser, "_OPENCLAW_CLI", [sys.executable, "-c", script]
        ):
            code, stdout, stderr = browser.run_browser_cmd(["status"])

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "browser status")
        self.assertEqual(stderr, "")

    def test_native_navigation_is_reported_unverified_without_cli(self):
        with patch.object(browser, "_OPENCLAW_CLI_CHECKED", True), patch.object(
            browser, "_OPENCLAW_CLI", None
        ), patch.object(browser, "_OPENCLAW_CLI_ERROR", "CLI unavailable"), patch.object(
            browser, "open_url_direct", return_value=True
        ):
            result = browser.run_browser_agent("Open https://x.com and navigate to the home page")

        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertIn("verification is unavailable", result["message"])


class TestPotatoXThreadSplitter(unittest.TestCase):
    def test_below_280_chars(self):
        text = "This is a short post well under 280 characters."
        parts = split_x_thread(text, max_chars=280)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0], text)

    def test_exact_boundary(self):
        exact_text = "a" * 280
        parts = split_x_thread(exact_text, max_chars=280)
        self.assertEqual(len(parts), 1)
        self.assertEqual(len(parts[0]), 280)

    def test_multi_paragraph_article(self):
        p1 = "First paragraph discussing the initial breakthrough in autonomous edge AI and small language models."
        p2 = "Second paragraph examining the architectural constraints of running on consumer hardware with 4GB VRAM."
        p3 = "Third paragraph detailing the empirical benchmark results on the GTX 1650 reference testbed."
        full_article = f"{p1}\n\n{p2}\n\n{p3}"
        
        parts = split_x_thread(full_article, max_chars=120)
        self.assertGreaterEqual(len(parts), 3)
        for p in parts:
            self.assertLessEqual(len(p), 120)

    def test_numbered_thread_preserves_short_explicit_paragraphs(self):
        text = "First update.\n\nSecond update.\n\nThird update."
        parts = split_x_thread(text, max_chars=280, add_numbering=True, preserve_paragraphs=True)
        self.assertEqual(parts, ["1/3 First update.", "2/3 Second update.", "3/3 Third update."])

    def test_very_long_sentence(self):
        long_sentence = (
            "This is an exceptionally long and continuous sentence engineered to test how the deterministic "
            "thread splitter gracefully falls back to splitting across whitespace boundaries rather than breaking "
            "words or sentences mid-character when an individual unit exceeds standard Twitter post limits."
        )
        parts = split_x_thread(long_sentence, max_chars=100)
        self.assertGreater(len(parts), 1)
        for p in parts:
            self.assertLessEqual(len(p), 100)
            self.assertFalse(p.startswith(" "))
            self.assertFalse(p.endswith(" "))

    def test_unicode_text(self):
        unicode_article = (
            "आर्टिफिसियल इन्टेलिजेन्सको नयाँ युगमा सानो मोडेलले पनि ठूलो काम गर्न सक्छ। "
            "पोटाटोल (PotatoClaw) ले ४ जिबी भिडियो र्‍याम भएको कम्प्युटरमा पनि कुशलतापूर्वक काम गर्छ। "
            "यसले स्वायत्त एजेन्टको क्षमता बढाउन DAG योजना र बाउन्डेड वर्किङ मेमोरी प्रयोग गर्दछ।"
        )
        parts = split_x_thread(unicode_article, max_chars=140)
        for p in parts:
            self.assertLessEqual(len(p), 140)

    def test_10_plus_post_thread(self):
        paragraphs = [
            f"Section {i}: Extensive discourse on modular small-model architecture and deterministic execution step {i}. "
            f"Testing that 10+ post threads can be created and sequenced deterministically without losing information."
            for i in range(1, 13)
        ]
        full_text = "\n\n".join(paragraphs)
        parts = split_x_thread(full_text, max_chars=180, add_numbering=True)
        self.assertGreaterEqual(len(parts), 10)
        for idx, p in enumerate(parts, 1):
            self.assertLessEqual(len(p), 180)
            self.assertTrue(p.startswith(f"{idx}/"))

    def test_20_plus_post_thread(self):
        paragraphs = [
            f"Chapter {i}: Detailed architectural analysis of autonomous systems invariant #{i}. "
            f"Ensuring robust multi-part partitioning across extended 20+ thread posts."
            for i in range(1, 25)
        ]
        full_text = "\n\n".join(paragraphs)
        parts = split_x_thread(full_text, max_chars=180, add_numbering=True)
        self.assertGreaterEqual(len(parts), 20)
        for p in parts:
            self.assertLessEqual(len(p), 180)

    def test_numbering_never_pushes_over_limit(self):
        text = "word " * 150
        parts = split_x_thread(text, max_chars=280, add_numbering=True)
        for p in parts:
            self.assertLessEqual(len(p), 280)

    def test_safety_margin(self):
        text = "This is a test post that includes an uncertain link or character count weighting."
        parts = split_x_thread(text, max_chars=100, safety_margin=25)
        self.assertEqual(len(parts), 2)
        for p in parts:
            self.assertLessEqual(len(p), 75)

    def test_zero_word_cutoff(self):
        lead = "Short lead. "
        s = "This is a single sentence whose length is ninety-eight characters long and contains important words"
        parts = split_x_thread(lead + s, max_chars=100, add_numbering=True)
        for p in parts:
            words = p.split()[1:]  # skip numbering tag
            for w in words:
                self.assertIn(w, (lead + s).split())
        self.assertTrue(any("important" in p for p in parts))
        self.assertTrue(any("words" in p for p in parts))

    def test_empty_and_whitespace(self):
        self.assertEqual(split_x_thread(""), [])
        self.assertEqual(split_x_thread("   \n\n  \t "), [])

    def test_thread_state_tracking(self):
        parts = ["Part 1 text", "Part 2 text", "Part 3 text"]
        state = BrowserThreadState(parts)
        self.assertEqual(state.total_parts, 3)
        self.assertEqual(state.current_part, 1)
        self.assertEqual(state.get_current_text(), "Part 1 text")
        
        state.filled_parts.append(state.get_current_text())
        state.current_part += 1
        self.assertEqual(state.current_part, 2)
        self.assertEqual(state.get_current_text(), "Part 2 text")


if __name__ == "__main__":
    unittest.main()
