#!/usr/bin/env python3
import unittest

import potato_browser_agent as browser


class BrowserPolicyTests(unittest.TestCase):
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

    def test_rejects_missing_required_field(self):
        with self.assertRaises(browser.BrowserPolicyError):
            browser.normalize_action({"action": "click"})

    def test_submit_ref_detection_allows_add_post(self):
        snap = '- button "Add post" [ref=e20]'
        self.assertFalse(browser.ref_looks_irreversible(snap, "e20"))

    def test_submit_ref_detection_blocks_post_all(self):
        snap = '- button "Post all" [ref=e30]'
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


if __name__ == "__main__":
    unittest.main()
