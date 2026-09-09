#!/usr/bin/env python3
"""Boundary tests for the opt-in CAT/BMW connections to chat and X posting."""

import os
import unittest
from unittest.mock import patch

import potato_cat_bmw as bmw
import potato_chat as chat
import post_all_hub as hub


class FakeRetrieval:
    active_ids = ["event_1"]
    scanned_nodes = 1
    scan_mode = "indexed_candidates"


class RecordingBridge:
    """Small test double at the integration boundary, not a production seam."""

    instances = []

    def __init__(self, namespace, active_limit=8):
        self.namespace = namespace
        self.enabled = True
        self.active_limit = active_limit
        self.events = []
        type(self).instances.append(self)

    def add_event(self, label, content, importance=0.5, protected=False,
                  source_record_id=None):
        self.events.append({
            "label": label,
            "content": content,
            "importance": importance,
            "protected": protected,
            "source_record_id": source_record_id,
        })
        return f"{self.namespace}_{len(self.events):05d}"

    def context(self, query, exact_detail=False):
        return "[BMW GRAPH MEMORY]\n- event_1=retained", FakeRetrieval()

    def stats(self):
        return {"enabled": True, "nodes": len(self.events), "active": len(self.events)}

    def clear(self):
        self.events.clear()


class CatBmwIntegrationTests(unittest.TestCase):
    def setUp(self):
        RecordingBridge.instances.clear()

    def test_flag_off_preserves_bridge_noop(self):
        with patch.dict(os.environ, {bmw.BMW_GRAPH_MEMORY: "0"}, clear=False):
            bridge = bmw.BmwGraphBridge("compat")
            self.assertFalse(bridge.enabled)
            self.assertIsNone(bridge.add_event("request", "must remain local"))
            self.assertEqual(bridge.context("request"), ("", None))

    def test_flag_on_bridge_retains_bounded_context_without_raw_block(self):
        with patch.dict(os.environ, {bmw.BMW_GRAPH_MEMORY: "1"}, clear=False):
            bridge = bmw.BmwGraphBridge("enabled", active_limit=2)
            bridge.add_event("request", "the exact source observation that must remain local")
            block, retrieval = bridge.context("source observation")

            self.assertTrue(bridge.enabled)
            self.assertIn("[BMW GRAPH MEMORY]", block)
            self.assertNotIn("[RAW HISTORY]", block)
            self.assertIsNotNone(retrieval)
            self.assertLessEqual(len(retrieval.active_ids), 2)

    def test_chat_test_turn_records_graph_memory_when_enabled(self):
        response = {
            "success": True,
            "content": "Local chat response.",
            "elapsed": 0.01,
            "total_tokens": 4,
        }
        with patch.dict(os.environ, {bmw.BMW_GRAPH_MEMORY: "1"}, clear=False), \
             patch.object(chat, "BmwGraphBridge", RecordingBridge), \
             patch.object(chat, "call_potato_agent", return_value=response):
            self.assertTrue(chat.test_single_turn("remember this chat request"))

        self.assertEqual(
            [event["label"] for event in RecordingBridge.instances[0].events],
            ["chat_request", "chat_response"],
        )

    def test_x_workflow_records_article_and_draft_when_enabled(self):
        article = {
            "title": "Local AI update",
            "source": "Local Feed",
            "url": "https://example.invalid/news",
        }
        with patch.dict(os.environ, {bmw.BMW_GRAPH_MEMORY: "1"}, clear=False), \
             patch.object(hub, "BmwGraphBridge", RecordingBridge), \
             patch.object(hub, "fetch_category_news", return_value=[article]), \
             patch.object(hub, "generate_single_story_x_post", return_value="Local AI update.") as draft_mock, \
             patch.object(hub, "x_copy_to_clipboard", return_value=True):
            self.assertTrue(hub.run_x_post_workflow(auto_open=False))

        self.assertEqual(draft_mock.call_args.kwargs["graph_context"],
                         "[BMW GRAPH MEMORY]\n- event_1=retained")

        self.assertEqual(
            [event["label"] for event in RecordingBridge.instances[0].events[:2]],
            ["x_article", "x_post_draft"],
        )


if __name__ == "__main__":
    unittest.main()
