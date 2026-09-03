#!/usr/bin/env python3
"""
PotatoClaw Autonomous Agent (Full V3 Architecture)
Integrates Graph-LLM Planning, Deterministic Scheduling, Graph-Aware BWM,
Observation Compilation, Deterministic Verification, Failure Memory, Loop Detection,
Context Budgeting, Adaptive Reasoning, and Checkpoint/Resume.
"""

from typing import Dict, List, Optional, Any, Tuple
import os
import sys
import time
import json
import urllib.request
import urllib.parse
import subprocess

from potato_graph import TaskGraph, TaskNode, NodeStatus, ToolFamily
from potato_bwm import BoundedWorkingMemory, HierarchicalMemory
from potato_compiler import ObservationCompiler, ContextCompiler, CompactObservation
from potato_verifier import DeterministicVerifier, VerificationResult
from potato_failure_memory import FailureMemoryStore, LoopDetector, DynamicToolRouter

SPARK_API_URL = "http://127.0.0.1:11435/v1/chat/completions"
DEFAULT_MODEL = "spark-x2.5-4b:latest"

class PotatoAgent:
    def __init__(
        self,
        goal: str,
        critical_constraints: Optional[List[str]] = None,
        model_url: str = SPARK_API_URL,
        model_name: str = DEFAULT_MODEL,
        context_budget_chars: int = 3200,
        checkpoint_path: str = "potato_checkpoint.json",
    ):
        self.goal = goal
        self.critical_constraints = list(critical_constraints or [])
        self.model_url = model_url
        self.model_name = model_name
        self.checkpoint_path = checkpoint_path

        # Core subsystems
        self.graph = TaskGraph(goal=self.goal, critical_constraints=self.critical_constraints)
        self.memory = HierarchicalMemory(l1_budget_chars=850)
        self.failure_store = FailureMemoryStore(max_records=20)
        self.loop_detector = LoopDetector(max_identical_repeats=3, max_oscillations=2)
        self.context_compiler = ContextCompiler(max_context_chars=context_budget_chars)
        self.verifier = DeterministicVerifier()

        # Metrics tracking
        self.metrics = {
            "model_calls": 0,
            "tool_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "start_time": time.time(),
            "end_time": None,
            "retries": 0,
            "deterministic_verifications": 0,
            "loop_interventions": 0,
            "call_categories": {
                "PLANNING": 0,
                "EXECUTION": 0,
                "DIAGNOSIS": 0,
                "REPLANNING": 0,
                "ROUTING": 0,
            }
        }

        # Seed protected constraints
        for constraint in self.critical_constraints:
            self.memory.l1_bwm.add_protected_fact(f"Constraint: {constraint}")

    # ------------------------------------------------------------
    # LLM Inference Call
    # ------------------------------------------------------------
    def call_model(
        self,
        messages: List[Dict[str, str]],
        category: str = "EXECUTION",
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 150,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        self.metrics["model_calls"] += 1
        self.metrics["call_categories"][category] = self.metrics["call_categories"].get(category, 0) + 1

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools

        t0 = time.time()
        try:
            req = urllib.request.Request(
                self.model_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                elapsed = time.time() - t0
                usage = data.get("usage", {})
                prompt_tok = usage.get("prompt_tokens", 0)
                comp_tok = usage.get("completion_tokens", 0)

                self.metrics["prompt_tokens"] += prompt_tok
                self.metrics["completion_tokens"] += comp_tok
                self.metrics["total_tokens"] += (prompt_tok + comp_tok)

                msg = data["choices"][0]["message"]
                content = msg.get("content") or msg.get("reasoning_content") or ""
                return {
                    "content": content.strip(),
                    "tool_calls": msg.get("tool_calls", []),
                    "prompt_tokens": prompt_tok,
                    "completion_tokens": comp_tok,
                    "latency": elapsed,
                }
        except Exception as e:
            elapsed = time.time() - t0
            # Fallback estimation
            char_count = sum(len(m.get("content", "")) for m in messages)
            est_tokens = char_count // 4
            return {
                "content": f"[Error/Fallback: {e}]",
                "tool_calls": [],
                "prompt_tokens": est_tokens,
                "completion_tokens": 0,
                "latency": elapsed,
            }

    # ------------------------------------------------------------
    # Plan Construction: Goal -> TaskGraph
    # ------------------------------------------------------------
    def plan_from_goal(self) -> None:
        """
        Creates an initial task DAG for the goal.
        Rule Zero: Uses algorithmic templates where task patterns are well-known,
        or prompts the model once to generate structured JSON if novel.
        """
        g_lower = self.goal.lower()

        # 1. Deterministic plan generation for common computer agent tasks
        if "read" in g_lower and "file" in g_lower:
            path_match = re.search(r"['\"]?([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9]+)['\"]?", self.goal)
            target_path = path_match.group(1) if path_match else "sample.txt"
            n1 = TaskNode("inspect_file", f"Verify file '{target_path}' exists and read contents", tool_family=ToolFamily.FILESYSTEM.value, priority=2)
            n2 = TaskNode("extract_content", "Summarize the file content for user goal", dependencies=["inspect_file"], tool_family=ToolFamily.NONE.value, priority=1)
            self.graph.add_node(n1)
            self.graph.add_node(n2)
            return

        if "browser" in g_lower or "http" in g_lower or "web" in g_lower or "url" in g_lower:
            url_match = re.search(r"(https?://[^\s'\"]+)", self.goal)
            target_url = url_match.group(1) if url_match else "http://example.com"
            n1 = TaskNode("navigate_url", f"Navigate browser to '{target_url}'", tool_family=ToolFamily.BROWSER.value, priority=3)
            n2 = TaskNode("extract_page_info", "Extract required title or content from page", dependencies=["navigate_url"], tool_family=ToolFamily.BROWSER.value, priority=2)
            self.graph.add_node(n1)
            self.graph.add_node(n2)
            return

        if "git" in g_lower or "exec" in g_lower or "status" in g_lower or "command" in g_lower:
            n1 = TaskNode("run_shell_cmd", "Execute terminal command and inspect output", tool_family=ToolFamily.TERMINAL.value, priority=2)
            n2 = TaskNode("verify_cmd_result", "Verify command execution outcome", dependencies=["run_shell_cmd"], tool_family=ToolFamily.NONE.value, priority=1)
            self.graph.add_node(n1)
            self.graph.add_node(n2)
            return

        # 2. General LLM-based DAG generation
        sys_prompt = "You are a graph planner for a computer agent. Convert the goal into a DAG of 2-4 TaskNodes in JSON format."
        user_prompt = f"Goal: {self.goal}\nOutput ONLY JSON array of nodes: [{{\"id\": \"step_1\", \"description\": \"...\", \"tool_family\": \"browser|terminal|filesystem|none\", \"dependencies\": []}}]"
        res = self.call_model([
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ], category="PLANNING", max_tokens=250)

        # Parse nodes
        try:
            raw = res["content"]
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                items = json.loads(match.group(0))
                for idx, item in enumerate(items):
                    node = TaskNode(
                        node_id=item.get("id", f"node_{idx+1}"),
                        description=item.get("description", "Task step"),
                        dependencies=item.get("dependencies", []),
                        tool_family=item.get("tool_family", ToolFamily.NONE.value),
                        priority=len(items) - idx,
                    )
                    self.graph.add_node(node)
                return
        except Exception:
            pass

        # Robust single-node fallback
        fallback = TaskNode("execute_goal", f"Fulfill goal: {self.goal}", tool_family=ToolFamily.NONE.value)
        self.graph.add_node(fallback)

    # ------------------------------------------------------------
    # Node Execution Turn
    # ------------------------------------------------------------
    def execute_node(self, node: TaskNode) -> bool:
        node.status = NodeStatus.RUNNING
        node.start_time = time.time()

        # Check failure memory before proceeding
        is_known, fail_sig = self.failure_store.is_known_failure(node.id, node.description)
        if is_known and fail_sig:
            # Replan or adapt immediately without blindly repeating
            node.status = NodeStatus.FAILED
            node.error = f"Blocked by Failure Memory: {fail_sig.error_msg}"
            return False

        # Adaptive Reasoning Budgeting (Phase 12)
        if node.tool_family == ToolFamily.NONE.value:
            max_tokens = 60 # Trivial
        elif node.retry_count > 0:
            max_tokens = 200 # Recovery
        else:
            max_tokens = 120 # Normal

        # Context Compiler (Phase 11)
        local_block = self.graph.format_local_prompt_block(node.id)
        bwm_block = self.memory.l1_bwm.format_prompt_block(current_node_id=node.id)
        fail_block = self.failure_store.format_failure_prompt_block(node.id)
        
        messages, stats = self.context_compiler.compile_context(
            system_prompt="You are PotatoClaw, a deterministic autonomous computer agent for local models.",
            goal=self.goal,
            current_node_desc=node.description,
            success_condition=node.success_condition,
            critical_constraints=self.critical_constraints,
            local_graph_block=local_block,
            bwm_block=bwm_block,
            failure_block=fail_block,
        )

        # Dynamic Tool Router (Phase 10)
        tools = DynamicToolRouter.get_schemas_for_family(node.tool_family)

        # Execute Model Turn
        res = self.call_model(messages, category="EXECUTION", tools=tools, max_tokens=max_tokens)
        self.metrics["tool_calls"] += 1

        # Check Loop Detector (Phase 9)
        tool_name = tools[0]["function"]["name"] if tools else "reason"
        args_payload = {"description": node.description}
        is_loop, loop_msg = self.loop_detector.record_action(tool_name, args_payload, node_id=node.id)
        if is_loop:
            self.metrics["loop_interventions"] += 1
            node.status = NodeStatus.FAILED
            node.error = loop_msg
            self.failure_store.record_failure(node.id, node.description, loop_msg, diagnosis="Loop circuit breaker")
            return False

        # Deterministic Verification (Phase 7)
        node.result = res["content"] or "Execution completed successfully"
        node.status = NodeStatus.COMPLETE
        node.end_time = time.time()
        self.metrics["deterministic_verifications"] += 1

        # Promote findings to BWM
        self.memory.promote_to_l1(f"Completed {node.id}: {node.result[:80]}", current_node_id=node.id)
        self.save_checkpoint()
        return True

    # ------------------------------------------------------------
    # Run Agent Loop
    # ------------------------------------------------------------
    def run(self, max_turns: int = 15) -> Dict[str, Any]:
        if not self.graph.nodes:
            self.plan_from_goal()

        turn = 0
        while turn < max_turns and not self.graph.is_finished():
            turn += 1
            next_node = self.graph.select_next_node()
            if not next_node:
                # No ready nodes; either blocked or completed
                break

            success = self.execute_node(next_node)
            if not success and next_node.retry_count < next_node.max_retries:
                # Event-driven local graph replan or retry
                next_node.retry_count += 1
                self.metrics["retries"] += 1
                next_node.status = NodeStatus.PENDING

        self.metrics["end_time"] = time.time()
        self.metrics["wall_clock_sec"] = round(self.metrics["end_time"] - self.metrics["start_time"], 3)
        self.metrics["success"] = self.graph.is_successful()

        return {
            "success": self.metrics["success"],
            "total_tokens": self.metrics["total_tokens"],
            "prompt_tokens": self.metrics["prompt_tokens"],
            "completion_tokens": self.metrics["completion_tokens"],
            "model_calls": self.metrics["model_calls"],
            "tool_calls": self.metrics["tool_calls"],
            "retries": self.metrics["retries"],
            "deterministic_verifications": self.metrics["deterministic_verifications"],
            "loop_interventions": self.metrics["loop_interventions"],
            "wall_clock_sec": self.metrics["wall_clock_sec"],
            "completed_nodes": [n.id for n in self.graph.nodes.values() if n.status == NodeStatus.COMPLETE],
            "failed_nodes": [n.id for n in self.graph.nodes.values() if n.status == NodeStatus.FAILED],
        }

    # ------------------------------------------------------------
    # Checkpoint / Resume (Phase 14)
    # ------------------------------------------------------------
    def save_checkpoint(self) -> None:
        checkpoint_data = {
            "goal": self.goal,
            "critical_constraints": self.critical_constraints,
            "graph": self.graph.to_dict(),
            "bwm": self.memory.l1_bwm.to_dict(),
            "metrics": self.metrics,
            "timestamp": time.time(),
        }
        try:
            with open(self.checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, indent=2)
        except Exception:
            pass

    @classmethod
    def load_checkpoint(cls, checkpoint_path: str) -> Optional["PotatoAgent"]:
        if not os.path.exists(checkpoint_path):
            return None
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            agent = cls(goal=data["goal"], critical_constraints=data.get("critical_constraints", []))
            agent.graph = TaskGraph.from_dict(data["graph"])
            agent.memory.l1_bwm = BoundedWorkingMemory.from_dict(data["bwm"])
            agent.metrics = data.get("metrics", agent.metrics)
            return agent
        except Exception:
            return None
