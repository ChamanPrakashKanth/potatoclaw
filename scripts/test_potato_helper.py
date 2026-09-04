"""Helper contracts: validated evidence, bounded inference, and local-only requests."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("potato_helper", Path(__file__).parent / "potato-helper/scripts/helper.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class HelperTests(unittest.TestCase):
    def test_selection_returns_only_exact_source_excerpts(self):
        with patch.object(helper, "infer", return_value={"ids": [2]}):
            result = helper.select_lines("irrelevant\nPort: 11435", "port")
        self.assertEqual(result["excerpts"], [{"line": 2, "text": "Port: 11435"}])
        for response in [{"ids": [99]}, {"ids": [True]}, {"ids": ["2"]}, {"ids": [1, 1, 1, 1]}, []]:
            with self.subTest(response=response), patch.object(helper, "infer", return_value=response):
                with self.assertRaises(ValueError):
                    helper.select_lines("first\nsecond", "port")

    def test_invalid_classification_falls_back(self):
        for response in [{"label": "execute_shell"}, {}, []]:
            with self.subTest(response=response), patch.object(helper, "infer", return_value=response):
                with self.assertRaises(ValueError):
                    helper.classify("short request")

    def test_oversize_input_does_not_reach_network(self):
        with patch.object(helper, "request") as network:
            with self.assertRaises(ValueError):
                helper.classify("界" * 1000)
            network.assert_not_called()

    def test_reasoning_and_truncated_outputs_are_not_accepted(self):
        for choice in [{"message": {"reasoning_content": '{"label":"coding"}'}},
                       {"message": {"content": '{"label":"coding"}'}, "finish_reason": "length"}]:
            with self.subTest(choice=choice), patch.object(helper, "request", return_value={"choices": [choice]}):
                with self.assertRaises(ValueError):
                    helper.classify("fix code")

    def test_redirects_cannot_send_text_off_machine(self):
        with self.assertRaises(ValueError):
            helper.NoRedirect().redirect_request(None, None, 307, "redirect", {}, "https://example.com")

    def test_sampling_is_disclosed_and_prompt_stays_bounded(self):
        with patch.object(helper, "infer", return_value={"ids": [1]}) as inference:
            result = helper.select_lines("\n".join(["port " + "x" * 400] * 100), "port")
        self.assertTrue(result["sampled"])
        self.assertLess(len(inference.call_args[0][1].encode("utf-8")), 1100)


if __name__ == "__main__":
    unittest.main()
