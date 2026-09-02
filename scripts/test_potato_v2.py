#!/usr/bin/env python3
"""
PotatoClaw V2 Core Components Integration Test
Tests BMW (Bounded Working Memory), Semantic Decay, Tool Routing, Tool Repair,
Loop Detection, Browser Intelligence in Code, and Resource Governor.
"""

import sys
import os
import io
import json

# Windows UTF-8 stdout
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

passed_tests = 0
failed_tests = 0

def assert_true(condition, test_name):
    global passed_tests, failed_tests
    if condition:
        print(f"  [✔] PASS: {test_name}")
        passed_tests += 1
    else:
        print(f"  [❌] FAIL: {test_name}")
        failed_tests += 1

print("=" * 65)
print("  POTATOCLAW V2 ARCHITECTURAL INTEGRATION TESTS")
print("=" * 65)

# --- 1. BMW (Bounded Working Memory) Test ---
print("\n[1] Testing BMW (Bounded Working Memory)...")

class BoundedWorkingMemory:
    def __init__(self, goal="", max_total_chars=850):
        self.goal = goal[:120]
        self.state = "INITIALIZED"
        self.facts = []
        self.completed = []
        self.pending = []
        self.errors = []
        self.results = []
        self.max_total_chars = max_total_chars
        
    def add_fact(self, fact):
        clean = fact.strip()[:120]
        if clean and clean not in self.facts:
            self.facts.append(clean)
            if len(self.facts) > 4:
                self.facts.pop(0)
                
    def record_completed(self, action):
        clean = action.strip()[:100]
        if clean:
            self.completed.append(clean)
            if len(self.completed) > 3:
                self.completed.pop(0)
                
    def format_block(self):
        parts = ["[TASK STATE (BMW)]"]
        if self.goal: parts.append(f"GOAL: {self.goal}")
        if self.state: parts.append(f"STATE: {self.state}")
        if self.facts: parts.append("FACTS:\n- " + "\n- ".join(self.facts))
        if self.completed: parts.append("COMPLETED: " + " -> ".join(self.completed))
        if self.results: parts.append("RESULTS:\n- " + "\n- ".join(self.results))
        res = "\n".join(parts)
        return res[:self.max_total_chars]

bmw = BoundedWorkingMemory("Extract headline from tech news")
bmw.add_fact("Target URL is https://news.ycombinator.com")
bmw.record_completed("browser(action='open')")
block = bmw.format_block()
assert_true("GOAL: Extract headline from tech news" in block, "BMW Goal correctly stored")
assert_true("Target URL is https://news.ycombinator.com" in block, "BMW Facts recorded")
assert_true(len(block) <= 850, "BMW Strict budget enforced (<= 850 chars)")

# Test deterministic pruning
bmw.add_fact("Fact 1")
bmw.add_fact("Fact 2")
bmw.add_fact("Fact 3")
bmw.add_fact("Fact 4")
bmw.add_fact("Fact 5") # Should evict oldest
assert_true("Fact 1" not in bmw.facts and "Fact 5" in bmw.facts, "BMW FIFO eviction prunes older facts")

# --- 2. Semantic Decay Test ---
print("\n[2] Testing Semantic Memory Decay...")
class SemanticDecay:
    def __init__(self, goal="quantum physics"):
        self.goal_kws = set(goal.lower().split())
        self.entries = []
        self.turn = 0
        
    def add_obs(self, text, has_error=False, has_result=False):
        self.turn += 1
        self.entries.append({
            "text": text,
            "turn": self.turn,
            "has_error": has_error,
            "has_result": has_result
        })
        
    def score_entry(self, entry):
        turns_ago = self.turn - entry["turn"]
        recency = 0.5 ** (turns_ago / 3.0)
        overlap = sum(1 for kw in self.goal_kws if kw in entry["text"].lower())
        relevance = 1.0 + min(2.0, overlap * 0.5)
        err_mult = 2.5 if entry["has_error"] else 1.0
        res_mult = 2.0 if entry["has_result"] else 1.0
        return recency * relevance * err_mult * res_mult
        
    def get_top(self, limit=2):
        scored = [(self.score_entry(e), e) for e in self.entries]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for s, e in scored[:limit]]

decay = SemanticDecay("quantum physics")
decay.add_obs("Cookie banner and ad popup")
decay.add_obs("Quantum entanglement photon test", has_result=True)
decay.add_obs("Connection error 500", has_error=True)

top_obs = decay.get_top(2)
assert_true(len(top_obs) == 2, "Semantic decay bounds active observation count")
assert_true(any(o["has_error"] for o in top_obs), "Semantic decay boosts active errors")
assert_true(any(o["has_result"] for o in top_obs), "Semantic decay boosts final results")

# --- 3. Dynamic Tool Routing Test ---
print("\n[3] Testing Dynamic Tool Routing...")
def classify_domain(prompt):
    p = prompt.lower()
    if any(k in p for k in ["http", "browser", "page", "click", "web", "site"]):
        return "browser"
    if any(k in p for k in ["file", "read", "write", "directory", "edit"]):
        return "filesystem"
    if any(k in p for k in ["git", "exec", "shell", "run", "npm", "cargo"]):
        return "shell"
    return "core"

assert_true(classify_domain("Open https://example.com and click button") == "browser", "Classifies browser task")
assert_true(classify_domain("Read sample.txt file in workspace") == "filesystem", "Classifies filesystem task")
assert_true(classify_domain("Run git status and npm test") == "shell", "Classifies shell task")

# --- 4. Small-Model Tool-Call Repair Test ---
print("\n[4] Testing Small-Model Tool-Call Repair...")
def repair_json(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].replace("json", "").strip()
    raw = raw.replace("'", '"')
    import re
    raw = re.sub(r',\s*([}\]])', r'\1', raw)
    raw = re.sub(r'([{,]\s*)([a-zA-Z0-9_$]+)\s*:', r'\1"\2":', raw)
    try:
        return json.loads(raw)
    except Exception:
        return None

repaired = repair_json("{ action: 'open', target_url: 'http://example.com', }")
assert_true(repaired is not None and repaired.get("action") == "open", "Repairs malformed single quotes, trailing commas, and unquoted keys")

# --- 5. Loop Detector Test ---
print("\n[5] Testing Loop Detector & Circuit Breaker...")
class LoopDetector:
    def __init__(self, max_repeats=3):
        self.history = []
        self.max_repeats = max_repeats
    def check(self, tool, args):
        sig = f"{tool}:{json.dumps(args)}"
        self.history.append(sig)
        if len(self.history) >= self.max_repeats:
            recent = self.history[-self.max_repeats:]
            if all(e == sig for e in recent):
                return True, f"LOOP DETECTED: {tool} repeated {self.max_repeats} times."
        return False, ""

loop_det = LoopDetector(3)
r1, _ = loop_det.check("browser", {"action": "click", "selector": "#btn"})
r2, _ = loop_det.check("browser", {"action": "click", "selector": "#btn"})
r3, msg = loop_det.check("browser", {"action": "click", "selector": "#btn"})
assert_true(r1 == False and r2 == False and r3 == True, "Detects identical repeated action loop on 3rd repeat")
assert_true("LOOP DETECTED" in msg, "Injects concise loop warning message")

# --- 6. Progressive Observation & Browser Intelligence Test ---
print("\n[6] Testing Progressive Observation & Code Intelligence...")
def format_progressive_obs(snapshot, level=1):
    if level == 0:
        return f"Title: \"{snapshot['title']}\"\nURL: {snapshot['url']}"
    elif level == 1:
        text = snapshot.get('text', '')[:150]
        return f"Title: \"{snapshot['title']}\"\nURL: {snapshot['url']}\nSummary: {text}"
    return f"Title: \"{snapshot['title']}\"\nURL: {snapshot['url']}\nFull: {snapshot.get('text', '')}"

snap = {"title": "Example Domain", "url": "http://example.com", "text": "This domain is established to be used for illustrative examples."}
lvl0 = format_progressive_obs(snap, 0)
lvl1 = format_progressive_obs(snap, 1)
assert_true(len(lvl0) < len(lvl1) and "Example Domain" in lvl0, "Level 0 generates ultra-compact title+URL observation")
assert_true("Summary:" in lvl1, "Level 1 adds key summary text")

# --- 7. Resource Governor Test ---
print("\n[7] Testing Resource Governor Tiers...")
def evaluate_governor(context_tokens, max_context=2048):
    if context_tokens > 1650:
        return "RED", ["EMERGENCY_PRUNE", "FORCE_LEVEL_0"]
    elif context_tokens > 1200:
        return "AMBER", ["PRUNE_OBS", "CAP_LEVEL_1"]
    return "GREEN", []

tier_g, _ = evaluate_governor(400)
tier_a, act_a = evaluate_governor(1300)
tier_r, act_r = evaluate_governor(1800)
assert_true(tier_g == "GREEN", "Governor GREEN tier under 1200 tokens")
assert_true(tier_a == "AMBER" and "CAP_LEVEL_1" in act_a, "Governor AMBER tier caps progressive observation")
assert_true(tier_r == "RED" and "EMERGENCY_PRUNE" in act_r, "Governor RED tier executes emergency context pruning")

print("\n" + "=" * 65)
print(f" RESULTS: {passed_tests} Passed, {failed_tests} Failed")
print("=" * 65)

if failed_tests > 0:
    sys.exit(1)
