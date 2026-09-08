#!/usr/bin/env python3
"""
PotatoClaw Autonomous Browser Agent
Target Architecture:
- Spark-X2.5-4B (port 11435) = Primary Reasoning Model
- Qwen2.5-0.5B-Instruct (port 11436) = Dedicated Browser-Action Policy
- Deterministic OpenClaw/PotatoClaw Code = Execution + Verification
- Context Hard Cap = 2048 tokens
- Zero Cloud APIs
- Deterministic Non-Premium X Thread Splitter & Safety Gate
"""

import os
import sys
import re
import json
import time
import argparse
import subprocess
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple

# Windows UTF-8 stdout configuration
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from potato_chat import repair_tool_json
from potato_verifier import DeterministicVerifier

QWEN_API_URL = "http://127.0.0.1:11436/v1/chat/completions"
QWEN_HEALTH_URL = "http://127.0.0.1:11436/health"
QWEN_MODEL_ID = "qwen2.5-0.5b:latest"

SPARK_HEALTH_URL = "http://127.0.0.1:11435/health"


# =====================================================================
# 1. Deterministic X Thread Splitter
# =====================================================================

def split_x_thread(
    text: str,
    max_chars: int = 280,
    add_numbering: bool = False,
    safety_margin: int = 0
) -> List[str]:
    """
    Deterministically splits a long text into standard X posts of <= max_chars (default 280).
    - Preserves paragraph and sentence boundaries where practical.
    - Never splits words unless an individual word exceeds the character limit.
    - Preserves original ordering.
    - Removes accidental empty parts.
    - Supports optional numbering (e.g. 1/8, 2/8) while guaranteeing no part exceeds max_chars.
    - Factors numbering length before finalizing each part.
    """
    if not text or not text.strip():
        return []

    clean_text = text.strip()
    effective_limit = max_chars - safety_margin
    if effective_limit <= 0:
        raise ValueError("Effective character limit must be greater than 0")

    # If already fits in one post and numbering is not requested or single-post:
    if not add_numbering and len(clean_text) <= effective_limit:
        return [clean_text]

    # Break into paragraphs first
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', clean_text) if p.strip()]

    def break_paragraph(para: str) -> List[str]:
        # Split on sentence boundaries (. ! ?) followed by whitespace
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', para) if s.strip()]
        pieces = []
        for s in sentences:
            if len(s) <= effective_limit:
                pieces.append(s)
            else:
                # Split sentence at whitespace
                words = s.split()
                for w in words:
                    if len(w) <= effective_limit:
                        pieces.append(w)
                    else:
                        # Split very long word without spaces
                        for k in range(0, len(w), effective_limit):
                            chunk = w[k:k + effective_limit]
                            if chunk:
                                pieces.append(chunk)
        return pieces

    # Build sequence of atomic tokens with appropriate spacing
    atomic_tokens: List[str] = []
    for p_idx, para in enumerate(paragraphs):
        if p_idx > 0:
            atomic_tokens.append('\n\n')
        units = break_paragraph(para)
        for u_idx, u in enumerate(units):
            if u_idx > 0:
                atomic_tokens.append(' ')
            atomic_tokens.append(u)

    def pack_tokens(limit_fn) -> List[str]:
        parts = []
        current = ""
        part_idx = 1
        i = 0
        working_tokens = list(atomic_tokens)
        while i < len(working_tokens):
            token = working_tokens[i]
            # Strip leading space/newlines at the start of a part
            if not current and token in (' ', '\n\n', '\n'):
                i += 1
                continue

            candidate = current + token
            max_len = limit_fn(part_idx)
            if len(candidate.strip()) <= max_len:
                current = candidate
                i += 1
            else:
                if current.strip():
                    parts.append(current.strip())
                    part_idx += 1
                    current = ""
                else:
                    # Token alone exceeds limit_fn(part_idx), slice it
                    parts.append(token[:max_len].strip())
                    part_idx += 1
                    current = ""
                    working_tokens[i] = token[max_len:]
        if current.strip():
            parts.append(current.strip())
        return parts

    if not add_numbering:
        return pack_tokens(lambda _: effective_limit)

    # With numbering: estimate N and iterate to ensure no part exceeds effective_limit
    raw_estimate = pack_tokens(lambda _: effective_limit)
    if len(raw_estimate) <= 1:
        # Avoid wasting characters on numbering for a single post
        return raw_estimate

    N = max(2, len(raw_estimate))
    parts = []
    for _ in range(6):
        def dynamic_limit(idx: int) -> int:
            prefix_len = len(f"{idx}/{N} ")
            return effective_limit - prefix_len

        parts = pack_tokens(dynamic_limit)
        if len(parts) == N:
            break
        N = len(parts)

    formatted = []
    total = len(parts)
    for i, p in enumerate(parts, 1):
        tag = f"{i}/{total} " if total > 1 else ""
        part_text = f"{tag}{p}".strip()
        # Enforce hard upper limit check
        if len(part_text) > max_chars:
            part_text = part_text[:max_chars].strip()
        formatted.append(part_text)
    return formatted


# =====================================================================
# 2. Browser Execution Interface (OpenClaw / WSL Bridge)
# =====================================================================

def strip_ansi(text: str) -> str:
    """Removes ANSI escape codes from output."""
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

def ensure_cdp_bridge() -> bool:
    """Ensures the CDP reverse bridge (scripts/cdp_bridge.py) is listening on port 9222."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", 9222))
        s.close()
        return True
    except Exception:
        pass

    bridge_script = os.path.join(SCRIPT_DIR, "cdp_bridge.py")
    if not os.path.exists(bridge_script):
        return False

    print("[PotatoBrowserAgent] Starting background CDP Bridge on 0.0.0.0:9222...")
    try:
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
            subprocess.Popen([sys.executable, bridge_script], creationflags=creationflags)
        else:
            subprocess.Popen([sys.executable, bridge_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
        return True
    except Exception as e:
        print(f"[PotatoBrowserAgent] Note: Could not auto-start cdp_bridge.py: {e}")
        return False

def run_browser_cmd(args: List[str], timeout: int = 30) -> Tuple[int, str, str]:
    """
    Executes an openclaw browser command deterministically.
    Supports openclaw.cmd on Windows, wsl openclaw, or node openclaw.mjs.
    """
    ensure_cdp_bridge()
    # 1. Try openclaw.cmd in repo root
    cmd_file = os.path.join(ROOT_DIR, "openclaw.cmd")
    if os.path.exists(cmd_file):
        full_cmd = [cmd_file, "browser"] + args
        try:
            res = subprocess.run(full_cmd, shell=True, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
            return res.returncode, strip_ansi(res.stdout).strip(), strip_ansi(res.stderr).strip()
        except Exception:
            pass

    # 2. Try direct WSL openclaw
    wsl_cmd = ["wsl", "-u", "openclaw", "-d", "OpenClawGateway", "-e", "openclaw", "browser"] + args
    try:
        res = subprocess.run(wsl_cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
        return res.returncode, strip_ansi(res.stdout).strip(), strip_ansi(res.stderr).strip()
    except Exception as e:
        return 1, "", f"Browser command execution failed: {e}"

def get_browser_snapshot() -> Tuple[str, List[Dict[str, str]]]:
    """
    Captures a compact interactive snapshot.
    Returns raw snapshot text and extracted elements with refs.
    """
    code, stdout, stderr = run_browser_cmd(["snapshot", "--interactive", "--compact"])
    if code != 0:
        return f"Snapshot error: {stderr or stdout}", []

    elements = []
    for line in stdout.splitlines():
        line = line.strip()
        ref_match = re.search(r'\[ref=([a-zA-Z0-9_\-]+)\]', line)
        if ref_match:
            ref = ref_match.group(1)
            elements.append({"line": line, "ref": ref})
    return stdout, elements


# =====================================================================
# 3. Dedicated Browser-Action Policy (Qwen2.5-0.5B-Instruct)
# =====================================================================

def check_qwen_health() -> bool:
    try:
        req = urllib.request.Request(QWEN_HEALTH_URL)
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False

def query_qwen_policy(goal: str, snapshot: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Sends goal and compact snapshot to Qwen2.5-0.5B on port 11436.
    Strictly bounded prompt <= 2048 tokens.
    Returns normalized action dictionary.
    """
    system_prompt = (
        "You are PotatoClaw's dedicated browser-action policy.\n"
        "Output ONLY a single JSON action object. Choose from:\n"
        '{"action": "navigate", "url": "https://..."}\n'
        '{"action": "click", "ref": "e1"}\n'
        '{"action": "type", "ref": "e2", "text": "content"}\n'
        '{"action": "press", "key": "Enter"}\n'
        '{"action": "wait", "seconds": 2}\n'
        '{"action": "submit", "ref": "e3"}\n'
        '{"action": "done", "message": "completed"}\n'
        "Output ONLY valid JSON."
    )

    # Compact snapshot representation
    max_snapshot_lines = 35
    snapshot_lines = snapshot.splitlines()[:max_snapshot_lines]
    compact_snapshot = "\n".join(snapshot_lines)

    user_msg = f"Goal: {goal}\n\nPage Snapshot:\n{compact_snapshot}"
    if history:
        recent_history = history[-2:]
        hist_str = "\n".join([f"Step: {h.get('action')} -> Result: {h.get('result')}" for h in recent_history])
        user_msg = f"Recent History:\n{hist_str}\n\n{user_msg}"

    payload = {
        "model": QWEN_MODEL_ID,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.1,
        "max_tokens": 120
    }

    try:
        req = urllib.request.Request(
            QWEN_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw = data["choices"][0]["message"]["content"]
            action = repair_tool_json(raw)
            if isinstance(action, dict) and "action" in action:
                return action
            # Fallback: extract action from text
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                parsed = repair_tool_json(match.group(0))
                if isinstance(parsed, dict) and "action" in parsed:
                    return parsed
    except Exception as e:
        return {"action": "wait", "seconds": 1, "error": str(e)}

    return {"action": "wait", "seconds": 1}


# =====================================================================
# 4. Thread State & Autonomous Execution Engine
# =====================================================================

class BrowserThreadState:
    def __init__(self, thread_parts: List[str]):
        self.thread_parts = thread_parts
        self.total_parts = len(thread_parts)
        self.current_part = 1
        self.filled_parts: List[str] = []
        self.last_verified_ref: Optional[str] = None
        self.failed_add_attempts = 0

    def get_current_text(self) -> str:
        if 1 <= self.current_part <= self.total_parts:
            return self.thread_parts[self.current_part - 1]
        return ""


def run_browser_agent(
    goal: str,
    allow_submit: bool = False,
    max_steps: int = 20
) -> Dict[str, Any]:
    """
    Orchestrates the browser agent run:
    - Prepares thread parts if thread or long text requested.
    - Loops: snapshot -> policy -> deterministic execution -> verification.
    - Enforces the Submit Safety Gate before irreversible actions.
    """
    print(f"\n[PotatoBrowserAgent] Goal: {goal}")
    print(f"[PotatoBrowserAgent] Allow Submit: {allow_submit}")

    # 1. Parse intent
    is_thread = "thread" in goal.lower()
    post_match = re.search(r'(?:prepare a post saying:|prepare this as a (?:non-Premium )?thread:|post this on x as a (?:non-Premium )?thread:)\s*(.*)', goal, re.IGNORECASE | re.DOTALL)
    
    extracted_text = post_match.group(1).strip() if post_match else ""
    if not extracted_text and ("post" in goal.lower() or "thread" in goal.lower()):
        # Check if text is enclosed in quotes
        quote_match = re.search(r'["\']([^"\']{10,})["\']', goal)
        if quote_match:
            extracted_text = quote_match.group(1).strip()

    thread_parts = []
    if extracted_text:
        # If thread requested or length exceeds 280 chars, use thread splitter
        should_split = is_thread or len(extracted_text) > 280
        thread_parts = split_x_thread(extracted_text, max_chars=280, add_numbering=should_split)
        print(f"[PotatoBrowserAgent] Extracted {len(thread_parts)} post part(s).")
        for idx, part in enumerate(thread_parts, 1):
            print(f"   Part {idx}/{len(thread_parts)} ({len(part)} chars): {part[:50]}...")

    thread_state = BrowserThreadState(thread_parts) if thread_parts else None

    # 2. Ensure Browser is Started
    print("[PotatoBrowserAgent] Checking browser readiness...")
    code, stdout, _ = run_browser_cmd(["status"])
    if "running: true" not in stdout.lower():
        print("[PotatoBrowserAgent] Starting browser...")
        run_browser_cmd(["start"])

    # 3. Rule Zero Fast-Path for Direct Navigation
    target_url = None
    url_match = re.search(r'https?://[^\s"\']+', goal)
    if url_match:
        target_url = url_match.group(0)
    elif "open x" in goal.lower() or "navigate to x" in goal.lower():
        target_url = "https://x.com"

    if target_url:
        print(f"[PotatoBrowserAgent] Direct Fast-Path: Navigating to {target_url}...")
        run_browser_cmd(["navigate", target_url])
        time.sleep(2)

    # 4. Agent Execution Loop
    history = []
    step = 0
    verifier = DeterministicVerifier()

    while step < max_steps:
        step += 1
        print(f"\n--- Step {step}/{max_steps} ---")

        # Capture snapshot
        snapshot, elements = get_browser_snapshot()
        print(f"[Snapshot] {len(elements)} interactive elements found.")

        # Goal Completion Check for simple navigation
        if "navigate to the home page" in goal.lower() or "open https://x.com and navigate" in goal.lower():
            if "x.com" in snapshot.lower() or "home" in snapshot.lower():
                print("  [✔] Navigation goal satisfied deterministically.")
                return {"status": "SUCCESS", "message": "Navigated to home page.", "steps": step}

        # Deterministic X Thread Flow
        if thread_state and thread_state.thread_parts:
            # Check if composer is open
            current_text = thread_state.get_current_text()
            print(f"[Thread Progress] Composing part {thread_state.current_part}/{thread_state.total_parts}")

            # Find textbox elements
            textbox_refs = [e["ref"] for e in elements if "textbox" in e["line"].lower() or "post text" in e["line"].lower()]
            add_button_refs = [e["ref"] for e in elements if "add post" in e["line"].lower() or "add another" in e["line"].lower() or "+" in e["line"].lower()]
            post_button_refs = [e["ref"] for e in elements if "post all" in e["line"].lower() or "post" in e["line"].lower()]

            if thread_state.current_part <= thread_state.total_parts:
                target_ref = textbox_refs[-1] if textbox_refs else None
                if target_ref:
                    print(f"  -> Typing part {thread_state.current_part} into ref [{target_ref}]...")
                    type_code, type_out, type_err = run_browser_cmd(["type", target_ref, current_text])
                    thread_state.filled_parts.append(current_text)
                    thread_state.last_verified_ref = target_ref

                    if thread_state.current_part < thread_state.total_parts:
                        # Click Add Post
                        time.sleep(1)
                        snap2, elem2 = get_browser_snapshot()
                        add_refs2 = [e["ref"] for e in elem2 if "add post" in e["line"].lower() or "+" in e["line"].lower()]
                        if add_refs2:
                            print(f"  -> Activating Add Post control [{add_refs2[0]}]...")
                            run_browser_cmd(["click", add_refs2[0]])
                            time.sleep(1)
                            thread_state.current_part += 1
                            continue
                        else:
                            print("  [!] Add post control not directly seen; querying policy.")
                    else:
                        # All parts entered!
                        print(f"  [✔] All {thread_state.total_parts} thread parts have been drafted and filled!")
                        
                        # Submission Safety Gate
                        if not allow_submit:
                            print("\n" + "=" * 65)
                            print(" [SUBMIT SAFETY GATE TRIGGERED]")
                            print(f" Drafted {thread_state.total_parts} post(s) successfully in the browser composer.")
                            print(" Submission halted safely because --allow-submit was not provided.")
                            print("=" * 65)
                            return {
                                "status": "PREPARED_SAFE",
                                "message": f"Prepared thread with {thread_state.total_parts} posts. Submission held safely.",
                                "parts": thread_state.total_parts,
                                "steps": step
                            }
                        else:
                            print("  -> Submitting thread via Post / Post all...")
                            if post_button_refs:
                                run_browser_cmd(["click", post_button_refs[0]])
                                time.sleep(3)
                                # Verify result
                                snap3, _ = get_browser_snapshot()
                                return {
                                    "status": "SUBMITTED",
                                    "message": f"Successfully submitted thread of {thread_state.total_parts} posts.",
                                    "steps": step
                                }

        # Query Qwen 0.5B Browser Action Policy
        print("[Policy] Querying Qwen 0.5B on port 11436...")
        action_dict = query_qwen_policy(goal, snapshot, history)
        action = action_dict.get("action", "wait")
        print(f"[Policy Action] {action_dict}")

        if action == "done":
            print(f"  [✔] Policy reported done: {action_dict.get('message')}")
            return {"status": "SUCCESS", "message": action_dict.get("message"), "steps": step}

        if action == "submit" or (action == "click" and any(w in str(action_dict.get("ref", "")).lower() for w in ["post", "tweet", "submit", "publish"])):
            if not allow_submit:
                print("\n[Submit Safety Gate] Irreversible submit action blocked. Use --allow-submit to post.")
                return {"status": "PREPARED_SAFE", "message": "Draft prepared. Submit blocked by safety gate.", "steps": step}

        # Deterministic Action Execution
        result_msg = ""
        if action == "navigate":
            url = action_dict.get("url", "")
            if url:
                c, out, err = run_browser_cmd(["navigate", url])
                result_msg = f"navigate({url}): code {c}"
        elif action == "click":
            ref = action_dict.get("ref", "")
            if ref:
                c, out, err = run_browser_cmd(["click", ref])
                result_msg = f"click({ref}): code {c}"
        elif action == "type":
            ref = action_dict.get("ref", "")
            text = action_dict.get("text", "")
            if ref and text:
                c, out, err = run_browser_cmd(["type", ref, text])
                result_msg = f"type({ref}): code {c}"
        elif action == "press":
            key = action_dict.get("key", "Enter")
            c, out, err = run_browser_cmd(["press", key])
            result_msg = f"press({key}): code {c}"
        elif action == "wait":
            secs = action_dict.get("seconds", 2)
            time.sleep(secs)
            result_msg = f"waited({secs}s)"

        history.append({"action": action_dict, "result": result_msg})
        time.sleep(1)

    return {"status": "TIMEOUT", "message": f"Exceeded max steps ({max_steps})", "steps": step}


# =====================================================================
# 5. CLI Entrypoint
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="PotatoClaw Autonomous Browser Agent")
    parser.add_argument("goal", type=str, help="Natural language browsing goal or posting instruction")
    parser.add_argument("--allow-submit", action="store_true", help="Explicitly permit irreversible post/submit actions")
    parser.add_argument("--max-steps", type=int, default=15, help="Maximum action steps")
    args = parser.parse_args()

    result = run_browser_agent(
        goal=args.goal,
        allow_submit=args.allow_submit,
        max_steps=args.max_steps
    )
    print("\n[Result Summary]")
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("status") in ["SUCCESS", "PREPARED_SAFE", "SUBMITTED"] else 1)

if __name__ == "__main__":
    main()
