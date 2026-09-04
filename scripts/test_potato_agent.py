"""Agent stress tests: real local tools, deterministic model fixtures, no network."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from potato_agent import PotatoAgent
from potato_graph import TaskNode, NodeStatus
from potato_compiler import ContextCompiler


class AgentStressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / "source.txt"
        self.source.write_text("potato-proof-42", encoding="utf-8")

    def agent(self, goal="Inspect local evidence"):
        return PotatoAgent(goal, checkpoint_path=str(self.folder / "checkpoint.json"))

    def test_direct_read_needs_no_model(self):
        agent = self.agent('read "' + str(self.source) + '"')
        with patch.object(agent, "call_model", side_effect=AssertionError("Rule Zero bypassed")):
            result = agent.run()
        self.assertTrue(result["success"], result)
        self.assertEqual(result["tool_calls"], 1)
        self.assertIn("potato-proof-42", next(iter(agent.graph.nodes.values())).result)

    def test_model_tool_call_has_real_side_effect_and_dependency_reads_it(self):
        output = self.folder / "result.txt"
        command = subprocess.list2cmdline([sys.executable, "-c",
            "from pathlib import Path; Path(" + repr(str(output)) + ").write_text('verified-42')"])
        agent = self.agent()
        agent.graph.add_node(TaskNode("create", "Create requested artifact", tool_family="terminal"))
        agent.graph.add_node(TaskNode("read", 'read "' + str(output) + '"', dependencies=["create"], tool_family="filesystem"))
        proposal = {"content": "", "tool_calls": [{"function": {"name": "exec", "arguments": json.dumps({"command": command})}}]}
        with patch.object(agent, "call_model", return_value=proposal):
            result = agent.run()
        self.assertTrue(output.exists(), result)
        self.assertEqual(output.read_text(), "verified-42")
        self.assertTrue(result["success"], result)
        self.assertIn("verified-42", agent.graph.nodes["read"].result)

    def test_failure_does_not_unlock_dependent_nodes(self):
        agent = self.agent()
        agent.graph.add_node(TaskNode("missing", 'read "' + str(self.folder / "absent") + '"', tool_family="filesystem"))
        agent.graph.add_node(TaskNode("dependent", "Never run", dependencies=["missing"]))
        with patch.object(agent, "call_model", return_value={"content": "Done", "tool_calls": []}):
            result = agent.run()
        self.assertFalse(result["success"], result)
        self.assertNotEqual(agent.graph.nodes["dependent"].status, NodeStatus.COMPLETE)
        self.assertLessEqual(result["tool_calls"], 1)

    def test_text_or_model_errors_cannot_verify_tool_work(self):
        for response in [{"content": "Done", "tool_calls": []},
                         {"content": "[Error/Fallback: offline]", "tool_calls": []},
                         {"content": "", "tool_calls": []}]:
            with self.subTest(response=response):
                agent = self.agent()
                agent.graph.add_node(TaskNode("work", "Inspect the artifact", tool_family="filesystem", max_retries=0))
                with patch.object(agent, "call_model", return_value=response):
                    result = agent.run()
                self.assertFalse(result["success"], result)
                self.assertEqual(result["deterministic_verifications"], 0)

    def test_turn_limit_and_resume_do_not_claim_partial_success(self):
        agent = self.agent()
        for i in range(3):
            agent.graph.add_node(TaskNode(str(i), 'read "' + str(self.source) + '"',
                dependencies=[str(i - 1)] if i else [], tool_family="filesystem"))
        with patch.object(agent, "call_model", return_value={"content": "Done", "tool_calls": []}):
            self.assertFalse(agent.run(max_turns=1)["success"])
        resumed = PotatoAgent.load_checkpoint(agent.checkpoint_path)
        self.assertIsNotNone(resumed)
        self.assertEqual(resumed.checkpoint_path, agent.checkpoint_path)
        with patch.object(resumed, "call_model", side_effect=AssertionError("Rule Zero bypassed")):
            result = resumed.run()
        self.assertTrue(result["success"], result)
        self.assertEqual(result["tool_calls"], 3)

    def test_100_dependency_chains_execute_and_verify_all_steps(self):
        for case in range(100):
            with self.subTest(case=case):
                agent = self.agent()
                for step in range(4):
                    agent.graph.add_node(TaskNode(str(step), 'read "' + str(self.source) + '"',
                        dependencies=[str(step - 1)] if step else [], tool_family="filesystem"))
                with patch.object(agent, "call_model", return_value={"content": "Done", "tool_calls": []}):
                    result = agent.run()
                self.assertTrue(result["success"], result)
                self.assertEqual(result["tool_calls"], 4)
                for node in agent.graph.nodes.values():
                    self.assertIn("potato-proof-42", node.result)

    def test_retry_can_correct_arguments_without_replaying_failed_action(self):
        agent = self.agent()
        agent.graph.add_node(TaskNode("inspect", "Inspect local evidence", tool_family="filesystem"))
        responses = [{"content": json.dumps({"tool": "read", "args": {"path": str(path)}})}
                     for path in [self.folder / "absent", self.source]]
        with patch.object(agent, "call_model", side_effect=responses):
            result = agent.run()
        self.assertTrue(result["success"], result)
        self.assertEqual(result["tool_calls"], 2)
        self.assertEqual(result["retries"], 1)

    def test_large_context_is_rejected_before_network_or_side_effects(self):
        agent = self.agent()
        with patch("potato_agent.urllib.request.urlopen", side_effect=AssertionError("Oversized request sent")):
            response = agent.call_model([{"role": "user", "content": "界" * 3000}])
        self.assertIn("budget", response.get("error", "").lower())
        compiler = ContextCompiler(max_context_chars=200)
        with self.assertRaises(ValueError):
            compiler.compile_context("Keep all constraints", "G" * 200, "task")

    def test_cycle_cannot_execute_independent_side_effects(self):
        agent = self.agent()
        for node in [TaskNode("a", "a", dependencies=["b"]), TaskNode("b", "b", dependencies=["a"]),
                     TaskNode("free", 'read "' + str(self.source) + '"', tool_family="filesystem")]:
            agent.graph.add_node(node)
        with patch.object(agent, "call_model", return_value={"content": "Done"}):
            result = agent.run()
        self.assertFalse(result["success"])
        self.assertEqual(result["tool_calls"], 0)

    def test_failure_memory_survives_resume(self):
        agent = self.agent()
        agent.graph.add_node(TaskNode("missing", 'read "' + str(self.folder / "absent") + '"', tool_family="filesystem"))
        agent.run(max_turns=1)
        resumed = PotatoAgent.load_checkpoint(agent.checkpoint_path)
        self.assertIsNotNone(resumed)
        result = resumed.run()
        self.assertFalse(result["success"])
        self.assertEqual(result["tool_calls"], 1)


if __name__ == "__main__":
    unittest.main()
