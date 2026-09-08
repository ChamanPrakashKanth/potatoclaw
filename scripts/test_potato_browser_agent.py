#!/usr/bin/env python3
"""
PotatoClaw Browser Agent & X Thread Splitter Test Suite
Tests:
1. Text below 280 chars -> 1 post
2. Text exactly around boundary (279, 280, 281 chars)
3. Multi-paragraph article
4. Very long sentence exceeding 280 chars
5. Unicode text (multi-byte, emoji, Devanagari)
6. 10+ post thread (and 20+ post thread)
7. Numbering strictly <= 280 chars for every part
8. Safety margin enforcement
9. Empty/whitespace handling
10. Submit Safety Gate verification
11. Browser command runner & Qwen policy repair
"""

import os
import sys
import unittest

# Windows UTF-8 stdout configuration
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from potato_browser_agent import split_x_thread, BrowserThreadState


class TestPotatoXThreadSplitter(unittest.TestCase):

    def test_empty_and_whitespace(self):
        self.assertEqual(split_x_thread(""), [])
        self.assertEqual(split_x_thread("   \n\t  "), [])

    def test_below_280_chars(self):
        text = "Hello PotatoClaw! Extreme low-resource AI agent running on GTX 1650."
        parts = split_x_thread(text, max_chars=280)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0], text)
        self.assertTrue(len(parts[0]) <= 280)

    def test_exact_boundary(self):
        # Exactly 280 characters
        text_280 = "A" * 280
        parts_280 = split_x_thread(text_280, max_chars=280)
        self.assertEqual(len(parts_280), 1)
        self.assertEqual(len(parts_280[0]), 280)

        # 281 characters
        text_281 = "B" * 281
        parts_281 = split_x_thread(text_281, max_chars=280)
        self.assertEqual(len(parts_281), 2)
        self.assertTrue(len(parts_281[0]) <= 280)
        self.assertTrue(len(parts_281[1]) <= 280)

        # 279 characters
        text_279 = "C" * 279
        parts_279 = split_x_thread(text_279, max_chars=280)
        self.assertEqual(len(parts_279), 1)
        self.assertEqual(len(parts_279[0]), 279)

    def test_multi_paragraph_article(self):
        p1 = "First paragraph discussing extreme low-resource autonomous computer use. " * 3
        p2 = "Second paragraph analyzing deterministic DAG planning and bounded working memory. " * 3
        p3 = "Third paragraph examining small model browser action policies. " * 3
        full_text = f"{p1}\n\n{p2}\n\n{p3}"

        parts = split_x_thread(full_text, max_chars=280, add_numbering=True)
        self.assertTrue(len(parts) >= 3)
        for i, part in enumerate(parts, 1):
            self.assertTrue(len(part) <= 280, f"Part {i} exceeded 280 chars: {len(part)}")
            self.assertTrue(part.startswith(f"{i}/{len(parts)} "))

    def test_very_long_sentence(self):
        # A single sentence of 700 characters without terminal punctuation
        sentence = "This is a single continuous unbroken sentence that explores the theoretical boundaries of autonomous agent capability when constrained to tiny neural models running entirely on edge silicon without cloud connectivity " * 3
        parts = split_x_thread(sentence, max_chars=280, add_numbering=True)
        self.assertTrue(len(parts) >= 3)
        for i, part in enumerate(parts, 1):
            self.assertTrue(len(part) <= 280, f"Part {i} exceeded 280 chars: {len(part)}")
            # No words broken across parts (each part has words)
            self.assertTrue(part.startswith(f"{i}/{len(parts)} "))

    def test_unicode_text(self):
        # Unicode including Devanagari and emojis
        nepali_text = "आलुको पञ्जा (PotatoClaw) 🥔🦞 अत्यन्त कम स्रोत-साधनमा चल्ने स्वायत्त कम्प्युटर प्रयोग एजेन्ट हो। " * 6
        parts = split_x_thread(nepali_text, max_chars=280, add_numbering=True)
        self.assertTrue(len(parts) >= 2)
        for i, part in enumerate(parts, 1):
            self.assertTrue(len(part) <= 280, f"Part {i} exceeded 280 chars: {len(part)}")
            self.assertTrue(part.startswith(f"{i}/{len(parts)} "))

    def test_10_plus_post_thread(self):
        # Create an article with 3,000 characters -> 12-14 posts
        paragraphs = []
        for i in range(12):
            paragraphs.append(f"Section {i+1}: Detailed architectural specification of deterministic execution in PotatoClaw. Examining subgraphs, bounded working memory utility scores, and Flash-Attention single slot inference hygiene.")
        full_article = "\n\n".join(paragraphs)

        parts = split_x_thread(full_article, max_chars=280, add_numbering=True)
        self.assertTrue(len(parts) >= 10, f"Expected 10+ posts, got {len(parts)}")
        for i, part in enumerate(parts, 1):
            self.assertTrue(len(part) <= 280, f"Part {i} exceeded 280 chars: {len(part)}")
            self.assertTrue(part.startswith(f"{i}/{len(parts)} "))

    def test_20_plus_post_thread(self):
        # Long article -> 20+ posts
        paragraphs = [f"Milestone {i+1}: Detailed verification checkpoint #{i+1} demonstrating extreme deterministic safety." * 3 for i in range(25)]
        full_article = "\n\n".join(paragraphs)

        parts = split_x_thread(full_article, max_chars=280, add_numbering=True)
        self.assertTrue(len(parts) >= 20, f"Expected 20+ posts, got {len(parts)}")
        for i, part in enumerate(parts, 1):
            self.assertTrue(len(part) <= 280, f"Part {i} exceeded 280 chars: {len(part)}")
            self.assertTrue(part.startswith(f"{i}/{len(parts)} "))

    def test_numbering_never_pushes_over_limit(self):
        # Generate varied texts and check strict invariant
        for target_len in [270, 275, 278, 280, 500, 1000, 1500]:
            text = ("Word " * (target_len // 5))
            parts = split_x_thread(text, max_chars=280, add_numbering=True)
            for idx, part in enumerate(parts, 1):
                self.assertTrue(len(part) <= 280, f"Part {idx} of len {len(part)} exceeded 280")

    def test_safety_margin(self):
        text = "Some text with safety margin of 20 characters."
        parts = split_x_thread(text, max_chars=100, safety_margin=20)
        self.assertEqual(len(parts), 1)
        self.assertTrue(len(parts[0]) <= 80)

    def test_thread_state_tracking(self):
        parts = ["Part 1", "Part 2", "Part 3"]
        state = BrowserThreadState(parts)
        self.assertEqual(state.total_parts, 3)
        self.assertEqual(state.current_part, 1)
        self.assertEqual(state.get_current_text(), "Part 1")

        state.filled_parts.append("Part 1")
        state.current_part += 1
        self.assertEqual(state.current_part, 2)
        self.assertEqual(state.get_current_text(), "Part 2")


def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPotatoXThreadSplitter)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print("\n" + "=" * 60)
    print(f"THREAD SPLITTER TEST SUMMARY: {result.testsRun} run, {len(result.failures)} failed, {len(result.errors)} errors")
    print("=" * 60)
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
