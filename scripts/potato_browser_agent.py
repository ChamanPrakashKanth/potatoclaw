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

_ALLOWED = {"navigate", "click", "type", "press", "wait", "submit", "done", "fail"}
_IRREVERSIBLE_WORDS = ("post", "tweet", "publish", "send", "submit", "delete", "buy", "pay")


class BrowserPolicyError(Exception):
    """Raised when the small browser policy produces an invalid or unexecutable action."""
    pass


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

    # If already fits in one post and numbering is not requested:
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
                        for k in range(0, len(w), effective_limit):
                            chunk = w[k:k + effective_limit]
                            if chunk:
                                pieces.append(chunk)
        return pieces

    # Build sequence of atomic tokens
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
            cur_limit = limit_fn(part_idx)
            candidate = current + token
            if len(candidate) <= cur_limit:
                current = candidate
                i += 1
            else:
                if current.strip():
                    parts.append(current.strip())
                    current = ""
                    part_idx += 1
                else:
                    if len(token) > cur_limit:
                        parts.append(token[:cur_limit].strip())
                        working_tokens[i] = token[cur_limit:]
                        part_idx += 1
                    else:
                        current = token
                        i += 1
        if current.strip():
            parts.append(current.strip())
        return parts

    if not add_numbering:
        return pack_tokens(lambda _: effective_limit)

    # Numbering logic
    initial_parts = pack_tokens(lambda _: effective_limit - 6)
    estimated_total = max(len(initial_parts), 1)

    def get_numbered_limit(p_idx: int) -> int:
        tag_len = len(f"{p_idx}/{estimated_total} ")
        return effective_limit - tag_len

    parts = pack_tokens(get_numbered_limit)
    if len(parts) > estimated_total:
        estimated_total = len(parts)
        parts = pack_tokens(get_numbered_limit)

    total = len(parts)
    formatted = []
    for i, p in enumerate(parts, 1):
        tag = f"{i}/{total} " if total > 1 else ""
        part_text = f"{tag}{p}".strip()
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
# 3. Dedicated Browser-Action Policy & Guardrails
# =====================================================================

def check_qwen_health() -> bool:
    try:
        req = urllib.request.Request(QWEN_HEALTH_URL)
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False

def _extract_object(text: str) -> Optional[Dict[str, Any]]:
    """Extracts a JSON object from text or markdown code fences."""
    clean = re.sub(r'```(?:json)?\s*', '', text)
    clean = re.sub(r'```', '', clean).strip()
    match = re.search(r'\{[^{}]*\}', clean, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    try:
        return repair_tool_json(clean)
    except Exception:
        return None

def normalize_action(raw: Dict[str, Any]) -> Dict[str, str]:
    """Validates and normalizes small-model policy action JSON."""
    if not isinstance(raw, dict):
        raise BrowserPolicyError("policy payload is not a dict")
    action = str(raw.get("action", "")).strip().lower()
    aliases = {
        "goto": "navigate",
        "open": "navigate",
        "post": "submit",
        "send": "submit",
        "success": "done",
        "stop": "done",
        "error": "fail",
    }
    action = aliases.get(action, action)
    if action not in _ALLOWED:
        raise BrowserPolicyError(f"unsupported policy action: {action or '<empty>'}")

    out: Dict[str, str] = {"action": action}
    for key in ("url", "ref", "text", "key", "note", "reason"):
        value = raw.get(key)
        if value is not None:
            out[key] = str(value).strip()

    required = {
        "navigate": "url",
        "click": "ref",
        "type": "ref",
        "press": "key",
        "submit": "ref",
    }
    req = required.get(action)
    if req and not out.get(req):
        raise BrowserPolicyError(f"{action} requires '{req}'")
    if action == "type" and "text" not in out:
        raise BrowserPolicyError("type requires 'text'")
    return out

def _line_context_for_ref(snapshot: str, ref: str) -> str:
    low = snapshot.lower()
    needle = ref.lower()
    idx = low.find(needle)
    if idx < 0:
        return ""
    start = max(0, idx - 180)
    end = min(len(snapshot), idx + len(ref) + 220)
    return snapshot[start:end].lower()

def ref_looks_irreversible(snapshot: str, ref: str) -> bool:
    """Deterministically identifies whether an element ref performs an irreversible action."""
    context = _line_context_for_ref(snapshot, ref)
    if not context:
        return False
    if "add post" in context or "add another post" in context:
        return False
    if any(word in context for word in _IRREVERSIBLE_WORDS):
        return True
    if "post" in context and ("button" in context or "role" in context):
        return True
    return False

def execute_action(
    action: Dict[str, str],
    before: str,
    allow_submit: bool,
) -> Tuple[bool, str, bool]:
    """
    Deterministically validates and executes a browser action with safety gates.
    Returns: (success, message, approval_required)
    """
    kind = action["action"]

    if kind == "done":
        return True, action.get("note", "done"), False
    if kind == "fail":
        return False, action.get("reason", "policy reported failure"), False

    if kind == "submit":
        if not allow_submit:
            ref = action.get("ref", "")
            return False, f"APPROVAL_REQUIRED submit ref={ref}", True
        args = ["click", action["ref"]]
    elif kind == "click":
        ref = action["ref"]
        if ref_looks_irreversible(before, ref):
            if not allow_submit:
                return False, f"APPROVAL_REQUIRED submit ref={ref}", True
        args = ["click", ref]
    elif kind == "navigate":
        url = action["url"]
        if not (url.startswith("http://") or url.startswith("https://")):
            return False, "navigate requires an HTTP(S) URL", False
        args = ["navigate", url]
    elif kind == "type":
        args = ["type", action["ref"], action.get("text", "")]
    elif kind == "press":
        args = ["press", action["key"]]
    elif kind == "wait":
        args = ["wait", "--text", action.get("text", "")]
    else:
        return False, f"unsupported action {kind}", False

    code, out, err = run_browser_cmd(args)
    if code != 0:
        return False, f"{kind} failed: {(out or err)[:420]}", False

    return True, f"{kind} verified", False

def query_qwen_policy(goal: str, snapshot: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Sends goal and compact snapshot to Qwen2.5-0.5B on port 11436 within 2048-token context."""
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

    clean_snapshot = snapshot[:1200]
    prompt_text = f"Goal: {goal}\n\nRecent History:\n"
    for h in history[-2:]:
        prompt_text += f"- Action: {h.get('action')}, Result: {h.get('result')}\n"
    prompt_text += f"\nCurrent Browser Snapshot (interactive elements):\n{clean_snapshot}\n\nChoose next action:"

    payload = {
        "model": QWEN_MODEL_ID,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.0,
        "max_tokens": 120
    }

    req = urllib.request.Request(
        QWEN_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"].get("content", "")
            return _extract_object(content) or {}
    except Exception as e:
        print(f"[PotatoBrowserAgent] Warning: Policy call failed: {e}")
        return {}


# =====================================================================
# 4. Agent Orchestrator & Non-Premium Thread State Machine
# =====================================================================

class BrowserThreadState:
    """Tracks state during multi-part non-Premium X thread creation."""
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
        quote_match = re.search(r'["\']([^"\']{10,})["\']', goal)
        if quote_match:
            extracted_text = quote_match.group(1).strip()

    thread_parts = []
    if extracted_text:
        should_split = is_thread or len(extracted_text) > 280
        thread_parts = split_x_thread(extracted_text, max_chars=280, add_numbering=should_split)
        print(f"[PotatoBrowserAgent] Extracted {len(thread_parts)} post part(s).")
        for idx, part in enumerate(thread_parts, 1):
            print(f"   Part {idx}/{len(thread_parts)} ({len(part)} chars): {part[:50]}...")

    thread_state = BrowserThreadState(thread_parts) if thread_parts else None

    # 2. Ensure Browser is Started
    print("[PotatoBrowserAgent] Checking browser readiness...")
    ensure_cdp_bridge()
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

    while step < max_steps:
        step += 1
        print(f"\n--- Step {step}/{max_steps} ---")

        snapshot_text, elements = get_browser_snapshot()
        print(f"[Snapshot] {len(elements)} interactive elements found.")

        # X Thread Handling Logic
        if thread_state and thread_state.current_part <= thread_state.total_parts:
            print(f"[Thread Progress] Composing part {thread_state.current_part}/{thread_state.total_parts}")
            
            target_ref = None
            for el in elements:
                line = el["line"].lower()
                if "what is happening" in line or "post text" in line or "compose" in line or "textbox" in line:
                    target_ref = el["ref"]
                    break

            if not target_ref:
                for el in elements:
                    if "textbox" in el["line"].lower() or "editor" in el["line"].lower():
                        target_ref = el["ref"]
                        break

            if target_ref:
                current_text = thread_state.get_current_text()
                print(f"  -> Typing part {thread_state.current_part} into ref [{target_ref}]...")
                c, out, err = run_browser_cmd(["type", target_ref, current_text])
                if c == 0:
                    thread_state.filled_parts.append(current_text)
                    thread_state.last_verified_ref = target_ref

                    if thread_state.current_part < thread_state.total_parts:
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
                        print(f"  [✔] All {thread_state.total_parts} thread parts have been drafted and filled!")
                        
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
                            snap3, elem3 = get_browser_snapshot()
                            submit_refs = [e["ref"] for e in elem3 if "post all" in e["line"].lower() or "post" in e["line"].lower()]
                            if submit_refs:
                                print(f"  -> Explicit submit granted: Clicking [{submit_refs[0]}]...")
                                run_browser_cmd(["click", submit_refs[0]])
                                time.sleep(2)
                                return {"status": "SUBMITTED", "message": "Thread submitted live.", "steps": step}

        # Policy Action Selection
        action_dict = query_qwen_policy(goal, snapshot_text, history)
        if not action_dict:
            action_dict = {"action": "wait", "seconds": 2}

        print(f"[Policy Action] {json.dumps(action_dict)}")
        action = action_dict.get("action")

        if action == "done":
            return {"status": "SUCCESS", "message": action_dict.get("message", "Task completed"), "steps": step}

        # Submit Safety Gate
        ref = str(action_dict.get("ref", ""))
        if action == "submit" or (action == "click" and ref_looks_irreversible(snapshot_text, ref)):
            if not allow_submit:
                print("\n[Submit Safety Gate] Irreversible submit action blocked. Use --allow-submit to post.")
                return {"status": "PREPARED_SAFE", "message": "Draft prepared. Submit blocked by safety gate.", "steps": step}

        # Action Execution
        ok, result_msg, approval_req = execute_action(action_dict, snapshot_text, allow_submit)
        history.append({"action": action_dict, "result": result_msg})
        time.sleep(1)

    return {"status": "TIMEOUT", "message": f"Exceeded max steps ({max_steps})", "steps": step}


# Alias for backward compatibility
run = run_browser_agent


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
