"""
Unit and regression tests for PotatoClaw X (Twitter) News Engine:
- Chain-of-Thought (CoT) and meta-reasoning suppression
- Anti-prompt leakage sanitization
- Strict 280-character limit enforcement with t.co URL weighting
- Deterministic fallback verification
"""

import io
import json
import unittest
from unittest.mock import patch

from x_news_engine import (
    clean_x_tweet_output,
    format_fallback_single_post,
    generate_single_story_x_post,
    X_FREE_CHAR_LIMIT,
)


class XNewsEngineTests(unittest.TestCase):

    def test_pure_cot_and_constraint_leakage_is_rejected(self):
        """Tests that pure meta-deliberation and constraint regurgitation are rejected."""
        contaminated_outputs = [
            'We are asked to create a viral tweet text for the given headline: "DRDO invites Bids for S-Band High Power Microwave Development". The constraints:\n\n- Strict Twitter limit <= 280 characters (but also rule 1 says under 210 characters text plus...',
            'The constraints: Strict Twitter limit <= 280 characters. Output ONLY the tweet text.',
            'Rules: 1. Under 210 characters text. 2. Start with an emoji hook. Headline: Quantum Leap in Silicon.',
            'Task State: Category DEFENCE. Goal: Create ONE viral tweet.',
            '<think>Let\'s see what constraints we have. Under 280 chars.</think>',
            'Here is the tweet: ',
        ]
        for raw in contaminated_outputs:
            with self.subTest(raw=raw[:50]):
                cleaned = clean_x_tweet_output(raw, "defence", "https://idrw.org/drdo-bids")
                self.assertIsNone(cleaned)

    def test_meta_reasoning_preceding_valid_tweet_is_scrubbed(self):
        """Tests that if a model outputs thoughts before the tweet, the tweet is cleanly extracted."""
        raw = (
            "We are asked to create a viral tweet text for the given headline.\n"
            "The constraints: - Strict Twitter limit <= 280 characters.\n"
            "🛡️ DRDO issues tender for high-power microwave systems to strengthen electronic defense capabilities. #DefenseTech #DRDO"
        )
        link = "https://idrw.org/drdo-bids"
        cleaned = clean_x_tweet_output(raw, "defence", link)
        self.assertIsNotNone(cleaned)
        self.assertNotIn("We are asked", cleaned)
        self.assertNotIn("constraints", cleaned)
        self.assertNotIn("280", cleaned)
        self.assertTrue(cleaned.startswith("DRDO"))
        self.assertNotIn("#", cleaned)
        self.assertIn(link, cleaned)

    def test_think_tags_and_fences_are_removed(self):
        """Tests that <think> tags, markdown fences, and quotes are cleanly stripped."""
        raw = '<think>I need to write an impactful physics tweet.</think>\n```text\n⚛️ Quantum researchers achieve millisecond coherence time in silicon spin qubits. #Physics #Quantum\n```'
        cleaned = clean_x_tweet_output(raw, "physics", "https://phys.org/quantum-123")
        self.assertIsNotNone(cleaned)
        self.assertNotIn("<think>", cleaned)
        self.assertNotIn("```", cleaned)
        self.assertTrue(cleaned.startswith("Quantum"))
        self.assertIn("https://phys.org/quantum-123", cleaned)

    def test_tweet_length_strictly_enforced_with_tco_weighting(self):
        """Tests that effective character length is strictly <= 280 with URL counting as 23 chars."""
        link = "https://example.com/very/long/url/that/would/otherwise/consume/tons/of/characters/in/raw/string/format"
        long_text = "🚀 " + "A" * 250 + " #Tech #AI"
        cleaned = clean_x_tweet_output(long_text, "tech", link)
        self.assertIsNotNone(cleaned)
        
        import re
        effective_len = len(re.sub(r'https?://\S+', 'X'*23, cleaned))
        self.assertLessEqual(effective_len, X_FREE_CHAR_LIMIT)

    def test_fallback_generates_valid_posts_for_all_categories(self):
        """Tests deterministic fallback for tech, defence, indian_defence, physics."""
        article = {
            "title": "DRDO invites Bids for S-Band High Power Microwave Development",
            "source": "IDRW (Indian Defence)",
            "link": "https://idrw.org/drdo-invites-bids-for-s-band-high-power-microwave-development/",
            "desc": "Defence Research and Development Organisation has invited expressions of interest."
        }
        for cat in ["tech", "defence", "indian_defence", "physics"]:
            with self.subTest(category=cat):
                post = format_fallback_single_post(cat, article)
                self.assertIsNotNone(post)
                self.assertIn("DRDO", post)
                self.assertIn(article["link"], post)
                self.assertNotIn("#", post)
                
                import re
                effective_len = len(re.sub(r'https?://\S+', 'X'*23, post))
                self.assertLessEqual(effective_len, X_FREE_CHAR_LIMIT)

    def test_generate_single_story_falls_back_cleanly_on_bad_llm_response(self):
        """Tests that generate_single_story_x_post falls back to template if LLM gives pure CoT."""
        article = {
            "title": "DRDO invites Bids for S-Band High Power Microwave Development",
            "source": "IDRW (Indian Defence)",
            "link": "https://idrw.org/drdo-invites-bids-for-s-band-high-power-microwave-development/",
            "desc": "Defence Research and Development Organisation has invited expressions of interest."
        }
        
        bad_response = {
            "choices": [{
                "message": {
                    "content": 'We are asked to create a viral tweet text for the given headline... The constraints: - Strict Twitter limit <= 280 characters...'
                }
            }]
        }
        
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(bad_response).encode('utf-8'))):
            post = generate_single_story_x_post("defence", article)
            self.assertIsNotNone(post)
            # The contaminated text must NOT appear in the final post
            self.assertNotIn("We are asked", post)
            self.assertNotIn("The constraints", post)
            self.assertNotIn("280", post)
            self.assertTrue(post.startswith("DRDO"))


if __name__ == "__main__":
    unittest.main()
