"""Offline regressions at the real chat routing, parsing and execution boundaries."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import potato_chat as chat


class ChatReliabilityTests(unittest.TestCase):
    def test_explicit_commands_take_priority_over_news(self):
        for prompt, expected in [
            ('read "news update.txt"', ("read_file", {"path": "news update.txt"})),
            ('run echo software update', ("run_command", {"command": "echo software update"})),
            ('browser https://example.com/news', ("browser", {"url": "https://example.com/news"})),
            ('fetch_news physics', ("fetch_news", {"category": "physics"})),
        ]:
            with self.subTest(prompt=prompt):
                self.assertEqual(chat.intercept_direct_action(prompt), expected)

    def test_conversation_is_not_hijacked_by_keyword_fragments(self):
        for prompt in ["Tell me a story", "Explain software updates", "What is Indian defence?", "show the chair", "get started with quantum mechanics"]:
            with self.subTest(prompt=prompt):
                self.assertEqual(chat.intercept_direct_action(prompt), (None, {}))
        self.assertEqual(chat.intercept_direct_action("latest Indian defence news"),
                         ("fetch_news", {"category": "indian_defence"}))

    def test_json_repair_preserves_argument_contents(self):
        expected = {"tool": "run_command", "args": {"command": "echo 'hello' {raw: value,}"}}
        self.assertEqual(chat.repair_tool_json(json.dumps(expected)), expected)
        self.assertEqual(chat.repair_tool_json("{tool: 'browser', args: {url: 'https://example.com',},}"),
                         {"tool": "browser", "args": {"url": "https://example.com"}})
        self.assertEqual(chat.repair_tool_json('''{tool: "run_command", args: {command: "echo 'hello' {raw: value,}",},}'''), expected)

    def test_invalid_argument_shapes_are_rejected_without_crashing(self):
        for args in [42, ["example.com"], "not json"]:
            with self.subTest(args=args):
                self.assertEqual(chat.extract_tool_call(json.dumps({"tool": "browser", "args": args})), (None, {}))
        self.assertEqual(chat.extract_tool_call(json.dumps({"tool": "browser", "arguments": '{"url":"example.com"}'})),
                         ("browser", {"url": "https://example.com"}))

    def test_read_file_returns_content_including_empty_files(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "notes.txt"
            for content in ["hello potato", ""]:
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    summary, success = chat.execute_tool("read_file", {"path": str(path)})
                    self.assertTrue(success, summary)
                    self.assertIn(content, summary)

    def test_browser_verification_tracks_fetch_outcome(self):
        with patch.object(chat.urllib.request, "urlopen", side_effect=URLError("offline")):
            summary, success = chat.execute_tool("browser", {"url": "https://example.com"})
        self.assertFalse(success, summary)
        self.assertIn("offline", summary)
        with patch.object(chat.urllib.request, "urlopen", return_value=io.BytesIO(b"<title>Potato</title><p>Online</p>")):
            summary, success = chat.execute_tool("browser", {"url": "https://example.com"})
        self.assertTrue(success, summary)
        self.assertIn("Potato", summary)

    def test_reasoning_is_not_used_as_a_user_facing_answer(self):
        for message in [
            {"reasoning_content": "Private deliberation without any blacklist keywords."},
            {"content": "<think>Private deliberation cut off before completion"},
        ]:
            with self.subTest(message=message):
                response = io.BytesIO(json.dumps({"choices": [{"message": message}]}).encode())
                with patch.object(chat.urllib.request, "urlopen", return_value=response):
                    result = chat.call_potato_agent([{"role": "user", "content": "Hello"}])
                self.assertNotIn("Private deliberation", result["content"])
        for message, expected in [
            ({"content": "<think>Private deliberation</think>Hello!"}, "Hello!"),
            ({"content": "Hello!", "reasoning_content": "Private deliberation"}, "Hello!"),
            ({"reasoning_content": '{"tool":"read_file","args":{"path":"README.md"}}'},
             json.dumps({"tool": "read_file", "args": {"path": "README.md"}})),
        ]:
            with self.subTest(message=message):
                response = io.BytesIO(json.dumps({"choices": [{"message": message}]}).encode())
                with patch.object(chat.urllib.request, "urlopen", return_value=response):
                    result = chat.call_potato_agent([{"role": "user", "content": "Hello"}])
                self.assertEqual(result["content"], expected)


if __name__ == "__main__":
    unittest.main()
