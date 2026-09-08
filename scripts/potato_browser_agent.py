#!/usr/bin/env python3
"""
PotatoClaw Qwen Browser Policy Sidecar.

Runs a tiny local Qwen model as a browser-policy model while PotatoClaw keeps
deterministic execution, state inspection, loop breaking, and submit gating.

The model never receives shell access. It may choose one action from a compact
browser snapshot; the host executes that action through the local OpenClaw CLI.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import urllib.request
from typing import Any, Dict, Optional, Tuple

QWEN_API_URL = os.environ.get(
    "POTATO_BROWSER_API_URL",
    "http://127.0.0.1:11436/v1/chat/completions",
)
QWEN_HEALTH_URL = os.environ.get(
    "POTATO_BROWSER_HEALTH_URL",
    "http://127.0.0.1:11436/health",
)
QWEN_MODEL = os.environ.get("POTATO_BROWSER_MODEL", "qwen2.5-0.5b-browser")

MAX_GOAL_CHARS = 900
MAX_SNAPSHOT_CHARS = 5200
MAX_MODEL_TOKENS = 96
DEFAULT_MAX_STEPS = 20

_ALLOWED = {"navigate", "click", "type", "press", "wait", "submit", "done", "fail"}

_POLICY_SYSTEM = """You are PotatoClaw's tiny browser policy.
Choose exactly ONE next action from the current compact browser snapshot.
Return JSON only. Never invent refs. Never claim success yourself.
Actions:
{"action":"navigate","url":"https://..."}
{"action":"click","ref":"e12"}
{"action":"type","ref":"e12","text":"..."}
{"action":"press","key":"Enter"}
{"action":"wait","text":"..."}
{"action":"submit","ref":"e12"}
{"action":"done","note":"..."}
{"action":"fail","reason":"..."}
Use submit, never click, for irreversible Post/Send/Publish/Delete/Buy/Pay/Confirm actions.
"""

_IRREVERSIBLE_WORDS = (
    "post all",
    "publish",
    "send",
    "delete",
    "purchase",
    "buy now",
    "pay",
    "place order",
    "confirm",
)


class BrowserPolicyError(RuntimeError):
    pass


def _clean_text(text: str, limit: int) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _extract_object(raw: str) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    candidates = [text]
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match and match.group(0) != text:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
        except Exception:
            try:
                obj = ast.literal_eval(candidate)
            except Exception:
                continue
        if isinstance(obj, dict):
            return obj
    return None


def normalize_action(raw: Dict[str, Any]) -> Dict[str, str]:
    action = str(raw.get("action") or raw.get("tool") or "").strip().lower()
    aliases = {
        "open": "navigate",
        "goto": "navigate",
        "fill": "type",
        "enter_text": "type",
        "key": "press",
        "post": "submit",
        "publish": "submit",
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
        "wait": "text",
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
    context = _line_context_for_ref(snapshot, ref)
    if not context:
        return False
    if "add post" in context or "add another post" in context:
        return False
    if any(word in context for word in _IRREVERSIBLE_WORDS):
        return True
    # X commonly exposes the final button simply as "Post".
    if "post" in context and ("button" in context or "role" in context):
        return True
    return False


def check_model() -> bool:
    try:
        with urllib.request.urlopen(QWEN_HEALTH_URL, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def call_policy(goal: str, snapshot: str, step: int) -> Dict[str, str]:
    user = (
        f"GOAL: {_clean_text(goal, MAX_GOAL_CHARS)}\n"
        f"STEP: {step}\n"
        f"SNAPSHOT:\n{snapshot[:MAX_SNAPSHOT_CHARS]}"
    )
    payload = {
        "model": QWEN_MODEL,
        "messages": [
            {"role": "system", "content": _POLICY_SYSTEM},
            {"role": "user", "content": user},
        ],
        "max_tokens": MAX_MODEL_TOKENS,
        "temperature": 0.0,
    }
    req = urllib.request.Request(
        QWEN_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=35) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    msg = data["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    if not content and msg.get("reasoning_content"):
        content = str(msg["reasoning_content"])
    obj = _extract_object(content)
    if obj is None:
        raise BrowserPolicyError(f"model returned no action JSON: {content[:180]}")
    return normalize_action(obj)


def run_browser(*args: str, timeout: int = 30) -> Tuple[int, str]:
    cmd = ["openclaw", "browser", *args, "--json"]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise BrowserPolicyError(
            "openclaw CLI not found on PATH; run this from the PotatoClaw/OpenClaw environment"
        ) from exc
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, output.strip()


def snapshot() -> str:
    code, out = run_browser("snapshot", "--interactive", "--compact", "--depth", "5")
    if code != 0:
        raise BrowserPolicyError(f"browser snapshot failed: {out[:400]}")
    return out[:MAX_SNAPSHOT_CHARS]


def execute_action(
    action: Dict[str, str],
    before: str,
    allow_submit: bool,
) -> Tuple[bool, str, bool]:
    kind = action["action"]

    if kind == "done":
        return True, action.get("note", "done"), False
    if kind == "fail":
        return False, action.get("reason", "policy reported failure"), False

    if kind == "submit":
        if not allow_submit:
            ref = action["ref"]
            return False, f"APPROVAL_REQUIRED submit ref={ref}", True
        args = ("click", action["ref"])
    elif kind == "click":
        ref = action["ref"]
        if ref_looks_irreversible(before, ref):
            return False, f"BLOCKED_IRREVERSIBLE_CLICK ref={ref}; policy must use submit", False
        args = ("click", ref)
    elif kind == "navigate":
        url = action["url"]
        if not (url.startswith("http://") or url.startswith("https://")):
            return False, "navigate requires an HTTP(S) URL", False
        args = ("navigate", url)
    elif kind == "type":
        args = ("type", action["ref"], action.get("text", ""))
    elif kind == "press":
        args = ("press", action["key"])
    elif kind == "wait":
        args = ("wait", "--text", action["text"])
    else:
        return False, f"unsupported action {kind}", False

    code, out = run_browser(*args)
    if code != 0:
        return False, f"{kind} failed: {out[:420]}", False

    # Deterministic post-action observation. Command exit code plus a readable
    # browser state is the minimum evidence required to count execution.
    try:
        after = snapshot()
    except Exception as exc:
        return False, f"{kind} executed but post-action snapshot failed: {exc}", False

    changed = _clean_text(before, MAX_SNAPSHOT_CHARS) != _clean_text(after, MAX_SNAPSHOT_CHARS)
    if kind not in {"wait"} and not changed:
        return False, f"{kind} returned success but browser state did not change", False

    return True, f"{kind} verified", False


def run(goal: str, max_steps: int, allow_submit: bool) -> int:
    if not check_model():
        print(
            f"Qwen browser server is not ready at {QWEN_HEALTH_URL}. "
            "Run scripts/start-qwen-browser.ps1 first.",
            file=sys.stderr,
        )
        return 2

    last_sig = ""
    repeat_count = 0
    executed_steps = 0

    for step in range(1, max_steps + 1):
        before = snapshot()
        action = call_policy(goal, before, step)
        sig = json.dumps(action, sort_keys=True, ensure_ascii=False)

        if sig == last_sig:
            repeat_count += 1
        else:
            repeat_count = 1
            last_sig = sig
        if repeat_count >= 3:
            print(f"LOOP_BLOCKED after repeated action: {sig}", file=sys.stderr)
            return 4

        print(f"[{step}] {sig}")

        if action["action"] == "done":
            if executed_steps == 0:
                print("Rejected premature done: no browser action has been verified.", file=sys.stderr)
                return 5
            print(action.get("note", "Browser task complete."))
            return 0

        ok, message, approval_required = execute_action(action, before, allow_submit)
        print(f"    -> {message}")

        if approval_required:
            return 3
        if not ok:
            return 6

        executed_steps += 1

    print(f"Stopped after max_steps={max_steps} without verified completion.", file=sys.stderr)
    return 7


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Qwen2.5-0.5B as PotatoClaw's local browser policy."
    )
    parser.add_argument("goal", help="Browser task, kept compact for the 2048-token budget.")
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    parser.add_argument(
        "--allow-submit",
        action="store_true",
        help="Allow irreversible submit actions such as Post/Send/Publish.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.max_steps < 1 or args.max_steps > 50:
        print("--max-steps must be between 1 and 50", file=sys.stderr)
        return 2
    return run(args.goal, args.max_steps, args.allow_submit)


if __name__ == "__main__":
    raise SystemExit(main())
