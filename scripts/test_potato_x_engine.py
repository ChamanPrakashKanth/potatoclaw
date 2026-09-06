"""
Unit and regression tests for PotatoClaw X (Twitter) News Engine:
- Chain-of-Thought (CoT) and meta-reasoning suppression
- Anti-prompt leakage sanitization
- Strict 280-character limit enforcement with t.co URL weighting
- Deterministic fallback verification
"""

import io
import json
import socket
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
        self.assertNotIn(link, cleaned)

    def test_think_tags_and_fences_are_removed(self):
        """Tests that <think> tags, markdown fences, and quotes are cleanly stripped."""
        raw = '<think>I need to write an impactful physics tweet.</think>\n```text\n⚛️ Quantum researchers achieve millisecond coherence time in silicon spin qubits. #Physics #Quantum\n```'
        cleaned = clean_x_tweet_output(raw, "physics", "https://phys.org/quantum-123")
        self.assertIsNotNone(cleaned)
        self.assertNotIn("<think>", cleaned)
        self.assertNotIn("```", cleaned)
        self.assertTrue(cleaned.startswith("Quantum"))
        self.assertNotIn("https://phys.org/quantum-123", cleaned)

    def test_tweet_length_strictly_enforced_with_tco_weighting(self):
        """Tests that effective character length is strictly <= 280 with URL counting as 23 chars."""
        link = "https://example.com/very/long/url/that/would/otherwise/consume/tons/of/characters/in/raw/string/format"
        long_text = "🚀 " + "A" * 250 + " #Tech #AI"
        cleaned = clean_x_tweet_output(long_text, "tech", link)
        self.assertIsNotNone(cleaned)
        
        import re
        effective_len = len(re.sub(r'https?://\S+', 'X'*23, cleaned))
        self.assertLessEqual(effective_len, X_FREE_CHAR_LIMIT)

    def test_fallback_does_not_copy_source_headlines(self):
        """Failed generation must not publish a verbatim headline."""
        article = {
            "title": "DRDO invites Bids for S-Band High Power Microwave Development",
            "source": "IDRW (Indian Defence)",
            "link": "https://idrw.org/drdo-invites-bids-for-s-band-high-power-microwave-development/",
            "desc": "Defence Research and Development Organisation has invited expressions of interest."
        }
        for cat in ["tech", "defence", "indian_defence", "physics"]:
            with self.subTest(category=cat):
                post = format_fallback_single_post(cat, article)
                self.assertIsNone(post)

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
        
        with patch("urllib.request.urlopen", side_effect=lambda *a, **kw: io.BytesIO(json.dumps(bad_response).encode('utf-8'))):
            post = generate_single_story_x_post("defence", article)
            self.assertIsNone(post)

    def test_generated_post_omits_source_and_rejects_copied_headline(self):
        article = {
            'title': 'DRDO invites bids for microwave evaluation system',
            'source': 'IDRW (Indian Defence)',
            'link': 'https://idrw.org/story',
        }
        for raw, expected in [
            ('DRDO is seeking proposals for a microwave evaluation system. https://idrw.org/story',
             'DRDO is seeking proposals for a microwave evaluation system.'),
            ('DRDO is seeking proposals for a microwave evaluation system. idrw.org',
             'DRDO is seeking proposals for a microwave evaluation system.'),
            ('IDRW reports that DRDO is seeking proposals for a microwave evaluation system.', None),
            (article['title'], None),
        ]:
            response = {'choices': [{'message': {'content': raw}}]}
            with self.subTest(raw=raw), patch('urllib.request.urlopen', side_effect=lambda *a, **kw: io.BytesIO(json.dumps(response).encode())):
                self.assertEqual(generate_single_story_x_post('defence', article), expected)

    def test_empty_model_output_retries_and_recovers(self):
        article = {'title': 'India Eyes Ex-French Mirage-2000 Jets', 'source': 'IDRW'}
        draft = 'India is considering former French Mirage-2000 aircraft to extend its fleet life.'
        responses = [
            {'choices': [{'message': {'content': '', 'reasoning_content': 'Internal deliberation'}}]},
            {'choices': [{'message': {'content': draft}}]},
        ]
        with patch('urllib.request.urlopen', side_effect=[io.BytesIO(json.dumps(r).encode()) for r in responses]):
            self.assertEqual(generate_single_story_x_post('defence', article), draft)

    def test_slow_generation_has_time_to_finish_and_timeout_is_identified(self):
        article = {'title': 'India Eyes Ex-French Mirage-2000 Jets', 'source': 'IDRW'}
        draft = 'India is considering former French Mirage-2000 aircraft.'

        def slow_response(request, timeout):
            if timeout < 120:
                raise socket.timeout('generation still running')
            return io.BytesIO(json.dumps({'choices': [{'message': {'content': draft}}]}).encode())

        with patch('urllib.request.urlopen', side_effect=slow_response):
            self.assertEqual(generate_single_story_x_post('defence', article), draft)
        with patch('urllib.request.urlopen', side_effect=socket.timeout()), patch('builtins.print') as output:
            self.assertIsNone(generate_single_story_x_post('defence', article))
            messages = ' '.join(str(call.args[0]) for call in output.call_args_list)
            self.assertIn('did not finish within', messages)
            self.assertNotIn('Cannot connect', messages)


if __name__ == "__main__":
    unittest.main()
