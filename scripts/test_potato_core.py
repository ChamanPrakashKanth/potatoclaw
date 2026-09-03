#!/usr/bin/env python3
"""
PotatoClaw Core Architecture Comprehensive Test Suite
Tests TaskGraph, Deterministic Scheduler, G_local Retrieval, Subgraph Compaction,
Bounded Working Memory, Hierarchical Memory, Observation Compiler, Context Compiler,
Deterministic Verifier, Failure Memory, Loop Detection, Dynamic Tool Router,
and Checkpoint/Resume.
"""

import os
import sys
import json
import time

# Windows UTF-8 stdout configuration
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from potato_graph import TaskGraph, TaskNode, NodeStatus, ToolFamily
from potato_bwm import BoundedWorkingMemory, HierarchicalMemory, MemoryItem
from potato_compiler import ObservationCompiler, ContextCompiler
from potato_verifier import DeterministicVerifier
from potato_failure_memory import FailureMemoryStore, LoopDetector, DynamicToolRouter
from potato_agent import PotatoAgent

passed_count = 0
failed_count = 0

def check(condition: bool, test_name: str) -> None:
    global passed_count, failed_count
    if condition:
        print(f"  [✔] PASS: {test_name}")
        passed_count += 1
    else:
        print(f"  [❌] FAIL: {test_name}")
        failed_count += 1

print("=" * 70)
print("  POTATOCLAW V3 ARCHITECTURAL COMPREHENSIVE TEST SUITE")
print("=" * 70)

# ------------------------------------------------------------
# 1. TaskGraph & Deterministic DAG Scheduler
# ------------------------------------------------------------
print("\n[1] Testing Deterministic TaskGraph & DAG Scheduler...")
graph = TaskGraph(goal="Build and verify software patch")
n1 = TaskNode("inspect_code", "Inspect affected module", priority=3)
n2 = TaskNode("write_patch", "Modify source code", dependencies=["inspect_code"], priority=2)
n3 = TaskNode("run_tests", "Run automated test suite", dependencies=["write_patch"], priority=1)

graph.add_node(n1)
graph.add_node(n2)
graph.add_node(n3)

# Initial readiness: only n1 has no dependencies
ready = graph.update_readiness()
check(len(ready) == 1 and ready[0].id == "inspect_code", "Initial ready node is inspect_code")
check(not graph.is_ready("write_patch"), "write_patch is NOT ready before inspect_code completes")

# Select next node
selected = graph.select_next_node()
check(selected is not None and selected.id == "inspect_code", "select_next_node() chooses inspect_code")

# Simulate completion of n1
selected.status = NodeStatus.COMPLETE
selected.result = "Identified bug at line 42"

# Next ready node should be n2
ready2 = graph.update_readiness()
check(len(ready2) == 1 and ready2[0].id == "write_patch", "write_patch becomes ready after inspect_code completes")

# Local graph neighborhood retrieval G_local(v)
local_block = graph.format_local_prompt_block("write_patch")
check("CURRENT STEP [write_patch]" in local_block, "G_local includes current node")
check("inspect_code(COMPLETE)" in local_block, "G_local includes completed parent node")
check("run_tests" not in local_block, "G_local excludes irrelevant distant child details")

# Event-driven local graph patching: insert prerequisite
n_extra = TaskNode("backup_file", "Create backup of source file")
graph.patch_insert_prerequisite("write_patch", n_extra)
check(n_extra.id in graph.nodes, "Prerequisite inserted into graph")
check(graph.nodes["write_patch"].dependencies == ["backup_file"], "Target node dependency updated to prerequisite")

# Subgraph compaction
n1.status = NodeStatus.COMPLETE
n_extra.status = NodeStatus.COMPLETE
graph.compact_completed_subgraph(["inspect_code", "backup_file"], "prep_phase", "Preparation completed")
check("prep_phase" in graph.nodes, "Compacted summary node created")
check("inspect_code" not in graph.nodes, "Compacted nodes pruned from active graph")
check("prep_phase" in graph.nodes["write_patch"].dependencies, "Dependency rerouted to compacted summary node")

# Graph serialization / deserialization
g_json = graph.to_json()
g_restored = TaskGraph.from_dict(json.loads(g_json))
check(len(g_restored.nodes) == len(graph.nodes), "Graph successfully serialized and restored")

# ------------------------------------------------------------
# 2. Bounded Working Memory & Hierarchical Tiers
# ------------------------------------------------------------
print("\n[2] Testing Bounded Working Memory (BWM) & Hierarchical Tiers...")
bwm = BoundedWorkingMemory(max_total_chars=400, max_items=4)
id_crit = bwm.add_protected_fact("NEVER delete production database")
id_f1 = bwm.add_fact("Target repo is at C:\\dev\\potatoclaw", importance=0.8)
id_f2 = bwm.add_fact("Found crash on empty input string", importance=0.9, current_node_id="run_tests")
id_f3 = bwm.add_fact("Minor warning in unused CSS file", importance=0.1)

# Verify protected memory
check(bwm.items[id_crit].protected is True, "Protected fact marked as protected")
check(id_crit in bwm.protected_keys, "Protected keys recorded")

# Add items to force eviction of lowest score
bwm.add_fact("Extra fact 1", importance=0.7)
bwm.add_fact("Extra fact 2", importance=0.7)
check(id_crit in bwm.items, "Protected memory is NEVER evicted during capacity pressure")
check(id_f3 not in bwm.items, "Low importance fact evicted first")
check(len(bwm.items) <= 4, "Item count budget strictly enforced (<= 4 items)")

# Graph-aware retrieval
retrieved = bwm.retrieve_for_node("run_tests", limit=3)
retrieved_ids = [i.id for i in retrieved]
check(id_crit in retrieved_ids, "Graph retrieval includes protected memory")
check(id_f2 in retrieved_ids, "Graph retrieval prioritizes node-relevant memory for 'run_tests'")

# Hierarchical Memory (L0, L1, L2)
hmem = HierarchicalMemory()
hmem.record_l0("exec git status", "On branch main, clean working tree", "exec")
check(hmem.l0_immediate is not None, "L0 records immediate raw action/observation")
hmem.promote_to_l1("Branch is main", importance=0.6)
check(len(hmem.l1_bwm.items) == 1, "L1 BWM receives promoted fact")
hmem.store_l2_artifact("release_binary", "dist/potato.exe")
hmem.record_l2_decision("Migrated schema to v2")
l2_sum = hmem.get_l2_summary()
check("release_binary" in l2_sum and "Migrated schema" in l2_sum, "L2 stores durable artifacts and decisions")

# ------------------------------------------------------------
# 3. Observation Compiler & Context Compiler
# ------------------------------------------------------------
print("\n[3] Testing Observation Compiler & Context Compiler...")
obs_comp = ObservationCompiler()

# Compile terminal output
raw_stdout = "\n".join([f"Line {i}: processing data block..." for i in range(50)]) + "\nGit commit: abc1234\nBuild successful"
comp_term = obs_comp.compile_terminal("cargo build", exit_code=0, stdout=raw_stdout, stderr="")
check(comp_term.success is True, "Terminal observation marked successful")
check(len(comp_term.summary) < len(raw_stdout) // 2, "Terminal output compressed to head/tail summary")
check("Git commit recorded" in comp_term.facts, "Terminal compiler extracts key milestone facts")

# Compile browser output
comp_brow = obs_comp.compile_browser("http://example.com", "Example Domain", "This domain is for use in documentation illustrative examples.", [{"ref": "e1", "tag": "a", "text": "More info"}])
check("Example Domain" in comp_brow.summary, "Browser compiler extracts title and URL")
check("Snippet:" in comp_brow.summary, "Browser compiler retains compact text snippet")

# Context Compiler with hard budget
ctx_comp = ContextCompiler(max_context_chars=800) # strict budget
messages, stats = ctx_comp.compile_context(
    system_prompt="You are PotatoClaw, a minimal computer agent.",
    goal="Fix the parser bug",
    current_node_desc="Run pytest on test_parser.py",
    critical_constraints=["Do not modify external repos"],
    local_graph_block="G_LOCAL: Step 2 of 3",
    bwm_block="BWM: Found syntax error at line 5",
    observation_block="OBS: Pytest failed with AssertionError",
)
check(stats["total_chars"] <= 800, f"Context compiler strictly enforces budget ({stats['total_chars']} <= 800 chars)")
check("Do not modify external repos" in messages[0]["content"], "Critical constraints preserved in system prompt")
check("Fix the parser bug" in messages[1]["content"], "Goal preserved in user prompt")

# ------------------------------------------------------------
# 4. Deterministic Verifier
# ------------------------------------------------------------
print("\n[4] Testing Deterministic Verifier...")
verifier = DeterministicVerifier()

# Test file existence
temp_test_file = "test_verifier_temp.txt"
with open(temp_test_file, "w", encoding="utf-8") as f:
    f.write("POTATO_VERIFICATION_PASS_TOKEN")

try:
    v_exist = verifier.verify_file_exists(temp_test_file, min_bytes=5)
    check(v_exist.passed is True and v_exist.method == "deterministic_fs", "File existence verified deterministically")

    v_missing = verifier.verify_file_exists("non_existent_file_xyz.bin")
    check(v_missing.passed is False, "Missing file correctly rejected without LLM")

    v_pattern = verifier.verify_file_content_matches(temp_test_file, r"POTATO_VERIFICATION_PASS")
    check(v_pattern.passed is True, "File regex match verified deterministically")
finally:
    if os.path.exists(temp_test_file):
        os.remove(temp_test_file)

# Test exit code
v_code_0 = verifier.verify_exit_code(0, 0)
v_code_1 = verifier.verify_exit_code(1, 0)
check(v_code_0.passed is True and v_code_1.passed is False, "Exit codes verified deterministically")

# Test JSON schema
valid_json = '{"task_id": "t1", "status": "passed", "score": 98.5}'
v_json = verifier.verify_json_schema(valid_json, ["task_id", "status"])
check(v_json.passed is True, "JSON schema validated deterministically")

# ------------------------------------------------------------
# 5. Failure Memory & Loop Detection
# ------------------------------------------------------------
print("\n[5] Testing Failure Memory & Loop Detection...")
f_store = FailureMemoryStore(max_records=5)

# Record failure
f_store.record_failure(
    node_id="node_open",
    action="click('#submit-button')",
    error_msg="ElementNotInteractableException",
    diagnosis="Button is disabled until input filled",
)

is_known, fail_item = f_store.is_known_failure("node_open", "click('#submit-button')")
check(is_known is True and fail_item is not None, "Failure memory recognizes identical failing action")

is_known_other, _ = f_store.is_known_failure("node_open", "click('#other-button')")
check(is_known_other is False, "Failure memory allows novel actions")

# Loop Detector
loop_det = LoopDetector(max_identical_repeats=3, max_oscillations=2)
# Action 1 & 2
is_loop1, _ = loop_det.record_action("browser", {"action": "click", "selector": "#btn"})
is_loop2, _ = loop_det.record_action("browser", {"action": "click", "selector": "#btn"})
check(is_loop1 is False and is_loop2 is False, "1st and 2nd repeated action allowed")

# Action 3 (Identical repeat trigger)
is_loop3, msg3 = loop_det.record_action("browser", {"action": "click", "selector": "#btn"})
check(is_loop3 is True and "LOOP DETECTED" in msg3, "3rd repeated action triggers loop circuit breaker")

# Oscillatory A -> B -> A -> B
loop_det.reset()
loop_det.record_action("browser", {"action": "open"})
loop_det.record_action("exec", {"command": "git status"})
loop_det.record_action("browser", {"action": "open"})
is_osc, osc_msg = loop_det.record_action("exec", {"command": "git status"})
check(is_osc is True and "OSCILLATING LOOP DETECTED" in osc_msg, "A -> B -> A -> B oscillatory cycle detected")

# ------------------------------------------------------------
# 6. Dynamic Tool Router
# ------------------------------------------------------------
print("\n[6] Testing Dynamic Tool Router...")
schemas_browser = DynamicToolRouter.get_schemas_for_family("browser")
check(len(schemas_browser) == 1 and schemas_browser[0]["function"]["name"] == "browser", "Router exposes only browser schema for browser family")

schemas_fs = DynamicToolRouter.get_schemas_for_family("filesystem")
fs_names = [s["function"]["name"] for s in schemas_fs]
check("read" in fs_names and "write" in fs_names and "browser" not in fs_names, "Router exposes read/write and excludes browser for filesystem family")

# ------------------------------------------------------------
# 7. Agent Checkpoint / Resume
# ------------------------------------------------------------
print("\n[7] Testing Checkpoint & Resume...")
test_ckpt = "test_potato_checkpoint.json"
agent = PotatoAgent(goal="Test Checkpoint Goal", critical_constraints=["No cloud models"], checkpoint_path=test_ckpt)
agent.graph.add_node(TaskNode("step_a", "First step"))
agent.memory.promote_to_l1("Checkpoint milestone recorded")
agent.save_checkpoint()

check(os.path.exists(test_ckpt), "Checkpoint file written to disk")

restored_agent = PotatoAgent.load_checkpoint(test_ckpt)
check(restored_agent is not None, "Agent successfully loaded from checkpoint")
check(restored_agent.goal == "Test Checkpoint Goal", "Restored agent preserves goal")
check("step_a" in restored_agent.graph.nodes, "Restored agent preserves task graph")
check(len(restored_agent.memory.l1_bwm.items) == 2, "Restored agent preserves BWM items")

if os.path.exists(test_ckpt):
    os.remove(test_ckpt)

# ------------------------------------------------------------
# Final Test Results Summary
# ------------------------------------------------------------
print("\n" + "=" * 70)
print(f" TOTAL TESTS: {passed_count + failed_count} | PASSED: {passed_count} | FAILED: {failed_count}")
print("=" * 70)

if failed_count > 0:
    sys.exit(1)
else:
    sys.exit(0)
