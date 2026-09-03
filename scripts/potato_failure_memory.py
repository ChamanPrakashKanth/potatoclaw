#!/usr/bin/env python3
"""
PotatoClaw Failure Memory, Loop Detector & Dynamic Tool Router
Phase 8: Failure Memory Signature Tracking to prevent duplicate mistakes.
Phase 9: Deterministic Loop Detector & Circuit Breaker (Identical Repeats & Oscillatory Cycles).
Phase 10: Dynamic Tool Router exposing minimal tool schemas per task family.
"""

from typing import Dict, List, Optional, Any, Tuple
import hashlib
import json
import time

class FailureSignature:
    def __init__(
        self,
        node_id: str,
        action: str,
        error_msg: str,
        env_state_hash: str = "",
        diagnosis: Optional[str] = None,
        attempted_fix: Optional[str] = None,
    ):
        self.node_id = node_id
        self.action = action.strip()
        self.error_msg = error_msg.strip()
        self.env_state_hash = env_state_hash
        self.diagnosis = diagnosis
        self.attempted_fix = attempted_fix
        self.timestamp = time.time()
        self.signature_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        raw = f"{self.node_id}::{self.action}::{self.error_msg[:80]}::{self.env_state_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signature_hash": self.signature_hash,
            "node_id": self.node_id,
            "action": self.action,
            "error_msg": self.error_msg,
            "env_state_hash": self.env_state_hash,
            "diagnosis": self.diagnosis,
            "attempted_fix": self.attempted_fix,
            "timestamp": self.timestamp,
        }


class FailureMemoryStore:
    """
    Prevents small models from repeating known failed actions under the same state.
    """
    def __init__(self, max_records: int = 20):
        self.records: Dict[str, FailureSignature] = {}
        self.max_records = max_records

    def record_failure(
        self,
        node_id: str,
        action: str,
        error_msg: str,
        env_state_hash: str = "",
        diagnosis: Optional[str] = None,
        attempted_fix: Optional[str] = None,
    ) -> FailureSignature:
        sig = FailureSignature(
            node_id=node_id,
            action=action,
            error_msg=error_msg,
            env_state_hash=env_state_hash,
            diagnosis=diagnosis,
            attempted_fix=attempted_fix,
        )
        self.records[sig.signature_hash] = sig
        if len(self.records) > self.max_records:
            # Drop oldest
            oldest_key = min(self.records.keys(), key=lambda k: self.records[k].timestamp)
            del self.records[oldest_key]
        return sig

    def is_known_failure(self, node_id: str, action: str, env_state_hash: str = "") -> Tuple[bool, Optional[FailureSignature]]:
        """
        Checks if the exact same action has already failed in this state.
        """
        for sig in self.records.values():
            if sig.node_id == node_id and sig.action == action.strip():
                if not env_state_hash or sig.env_state_hash == env_state_hash:
                    return True, sig
        return False, None

    def format_failure_prompt_block(self, node_id: Optional[str] = None) -> str:
        relevant = [
            s for s in self.records.values()
            if not node_id or s.node_id == node_id
        ]
        if not relevant:
            return ""
        lines = ["[PAST FAILURES - DO NOT REPEAT]"]
        for s in relevant[-3:]:
            msg = f"- Action '{s.action}' failed: {s.error_msg}"
            if s.diagnosis:
                msg += f" (Diagnosis: {s.diagnosis})"
            lines.append(msg)
        return "\n".join(lines)


class LoopDetector:
    """
    Phase 9: Deterministic Loop Detector.
    Detects identical action repeats (default: 3x) and oscillatory A -> B -> A -> B cycles.
    """
    def __init__(self, max_identical_repeats: int = 3, max_oscillations: int = 2):
        self.max_identical_repeats = max_identical_repeats
        self.max_oscillations = max_oscillations
        self.history: List[Dict[str, Any]] = []

    def record_action(self, tool_name: str, args: Dict[str, Any], node_id: str = "") -> Tuple[bool, str]:
        """
        Returns (is_loop, loop_message).
        """
        clean_args = json.dumps(args, sort_keys=True)
        sig = f"{node_id}::{tool_name}::{clean_args}"
        self.history.append({"tool": tool_name, "args_sig": clean_args, "full_sig": sig})
        if len(self.history) > 30:
            self.history.pop(0)

        # 1. Identical repeat check
        if len(self.history) >= self.max_identical_repeats:
            recent = self.history[-self.max_identical_repeats:]
            if all(entry["full_sig"] == sig for entry in recent):
                return True, f"LOOP DETECTED: Action '{tool_name}' repeated {self.max_identical_repeats} times with identical arguments. Circuit breaker tripped."

        # 2. Oscillatory A -> B -> A -> B cycle check
        if len(self.history) >= 4:
            h = self.history
            if (
                h[-1]["full_sig"] == h[-3]["full_sig"]
                and h[-2]["full_sig"] == h[-4]["full_sig"]
                and h[-1]["full_sig"] != h[-2]["full_sig"]
            ):
                return True, f"OSCILLATING LOOP DETECTED between '{h[-2]['tool']}' and '{h[-1]['tool']}'. Circuit breaker tripped."

        return False, ""

    def reset(self) -> None:
        self.history.clear()


class DynamicToolRouter:
    """
    Phase 10: Dynamic Tool Router. Exposes only the tool family required for the active node.
    """
    TOOL_SCHEMAS = {
        "browser": [
            {
                "type": "function",
                "function": {
                    "name": "browser",
                    "description": "Control browser navigation, clicks, input, and reading.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "enum": ["open", "click", "type", "snapshot", "search"]},
                            "url": {"type": "string"},
                            "selector": {"type": "string"},
                            "text": {"type": "string"}
                        },
                        "required": ["action"]
                    }
                }
            }
        ],
        "terminal": [
            {
                "type": "function",
                "function": {
                    "name": "exec",
                    "description": "Execute shell command in terminal.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"}
                        },
                        "required": ["command"]
                    }
                }
            }
        ],
        "filesystem": [
            {
                "type": "function",
                "function": {
                    "name": "read",
                    "description": "Read file contents.",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write",
                    "description": "Write content to file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"}
                        },
                        "required": ["path", "content"]
                    }
                }
            }
        ],
        "core": [
            {
                "type": "function",
                "function": {
                    "name": "browser",
                    "description": "Browser actions.",
                    "parameters": {
                        "type": "object",
                        "properties": {"action": {"type": "string"}, "url": {"type": "string"}, "text": {"type": "string"}},
                        "required": ["action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "exec",
                    "description": "Run shell command.",
                    "parameters": {
                        "type": "object",
                        "properties": {"command": {"type": "string"}},
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read",
                    "description": "Read file.",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"]
                    }
                }
            }
        ]
    }

    @classmethod
    def get_schemas_for_family(cls, tool_family: str) -> List[Dict[str, Any]]:
        family = tool_family.lower().strip()
        if family in cls.TOOL_SCHEMAS:
            return cls.TOOL_SCHEMAS[family]
        if family in ["shell", "bash", "command"]:
            return cls.TOOL_SCHEMAS["terminal"]
        if family in ["file", "disk"]:
            return cls.TOOL_SCHEMAS["filesystem"]
        return cls.TOOL_SCHEMAS["core"]
