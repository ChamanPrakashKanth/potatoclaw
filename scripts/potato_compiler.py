#!/usr/bin/env python3
"""
PotatoClaw Observation Compiler & Context Compiler
Phase 6: Compresses enormous raw tool outputs into compact task states.
Phase 11: Constructs the smallest sufficient prompt context under a strict hard token budget.
"""

from typing import Dict, List, Optional, Any, Tuple
import re
import json

class CompactObservation:
    def __init__(
        self,
        summary: str,
        success: bool = True,
        error: Optional[str] = None,
        facts: Optional[List[str]] = None,
        artifacts: Optional[Dict[str, Any]] = None,
        raw_length: int = 0,
    ):
        self.summary = summary.strip()
        self.success = success
        self.error = error
        self.facts = list(facts or [])
        self.artifacts = dict(artifacts or {})
        self.raw_length = raw_length

    def format_block(self, max_chars: int = 400) -> str:
        parts = [f"OBSERVATION: {self.summary[:max_chars]}"]
        if self.error:
            parts.append(f"ERROR: {self.error[:150]}")
        if self.facts:
            parts.append("EXTRACTED: " + "; ".join(self.facts[:3]))
        return "\n".join(parts)


class ObservationCompiler:
    """
    Compresses raw terminal, browser, and filesystem output into compact task state S_t.
    """
    @staticmethod
    def compile_terminal(command: str, exit_code: int, stdout: str, stderr: str) -> CompactObservation:
        raw_total_len = len(stdout) + len(stderr)
        success = (exit_code == 0)
        facts = []
        artifacts = {}

        # Error extraction
        error_msg = None
        if not success or stderr:
            lines = [l.strip() for l in (stderr or stdout).split("\n") if l.strip()]
            error_msg = lines[-1] if lines else f"Exit code {exit_code}"

        # Clean stdout
        out_lines = [l.strip() for l in stdout.split("\n") if l.strip()]
        if len(out_lines) > 6:
            # Keep head 2 and tail 3
            summary_lines = out_lines[:2] + ["..."] + out_lines[-3:]
            summary = "\n".join(summary_lines)
        else:
            summary = "\n".join(out_lines) if out_lines else f"Command completed (exit code {exit_code})"

        # Check for created files or commits
        cmd_l = command.lower()
        out_l = stdout.lower()
        if "commit" in cmd_l or "commit" in out_l:
            facts.append("Git commit recorded")
        if "created" in out_l or "written" in out_l:
            facts.append("Output written successfully")

        return CompactObservation(
            summary=summary,
            success=success,
            error=error_msg,
            facts=facts,
            artifacts=artifacts,
            raw_length=raw_total_len,
        )

    @staticmethod
    def compile_browser(url: str, title: str, raw_text: str = "", interactive: Optional[List[Dict[str, str]]] = None) -> CompactObservation:
        raw_len = len(raw_text)
        facts = [f"Page: '{title}' ({url})"]
        artifacts = {"url": url, "title": title}

        # Truncate visible text to top 250 chars
        clean_text = " ".join(raw_text.split())
        summary = f"Title: '{title}'\nURL: {url}"
        if clean_text:
            summary += f"\nSnippet: {clean_text[:250]}..."

        if interactive:
            elements = [f"[{e.get('ref', '')}] {e.get('tag', '')} '{e.get('text', '')[:25]}'" for e in interactive[:4]]
            summary += "\nInteractive: " + ", ".join(elements)

        return CompactObservation(
            summary=summary,
            success=True,
            facts=facts,
            artifacts=artifacts,
            raw_length=raw_len,
        )

    @staticmethod
    def compile_filesystem(path: str, content: str, action: str = "read") -> CompactObservation:
        raw_len = len(content)
        lines = content.split("\n")
        line_count = len(lines)

        if action == "read":
            preview = lines[:4]
            if line_count > 4:
                preview.append(f"... ({line_count} total lines)")
            summary = f"File: '{path}' ({line_count} lines, {raw_len} bytes)\n" + "\n".join(preview)
        else:
            summary = f"File '{path}' written successfully ({line_count} lines, {raw_len} bytes)"

        return CompactObservation(
            summary=summary,
            success=True,
            facts=[f"Accessed file {path}"],
            artifacts={"path": path, "size_bytes": raw_len},
            raw_length=raw_len,
        )


class ContextCompiler:
    """
    Assembles the SMALLEST sufficient context under a hard token / character budget.
    Priority when over budget:
      1. Safety / Critical constraints (never dropped)
      2. Global goal
      3. Current node & success condition
      4. Protected BWM facts
      5. Failure signatures
      6. Latest observation summary
      7. Local graph context G_local
      8. Non-protected memories
      9. Tool schema
    """
    def __init__(self, max_context_chars: int = 3200): # ~800 tokens hard prompt budget
        self.max_context_chars = max_context_chars

    def compile_context(
        self,
        system_prompt: str,
        goal: str,
        current_node_desc: str,
        success_condition: Optional[str] = None,
        critical_constraints: Optional[List[str]] = None,
        local_graph_block: Optional[str] = None,
        bwm_block: Optional[str] = None,
        failure_block: Optional[str] = None,
        observation_block: Optional[str] = None,
    ) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
        sections: List[Tuple[str, int, str]] = []

        # Priority 1: System prompt & critical constraints
        sys_parts = [system_prompt.strip()]
        if critical_constraints:
            sys_parts.append("CRITICAL CONSTRAINTS: " + "; ".join(critical_constraints))
        sys_content = "\n\n".join(sys_parts)
        sections.append(("system", 1, sys_content))

        # Priority 2: Goal & Current Node
        user_core = [
            f"GOAL: {goal.strip()}",
            f"CURRENT TASK: {current_node_desc.strip()}",
        ]
        if success_condition:
            user_core.append(f"SUCCESS CONDITION: {success_condition.strip()}")
        sections.append(("core", 2, "\n".join(user_core)))

        # Priority 4: Protected BWM
        if bwm_block:
            sections.append(("bwm", 3, bwm_block.strip()))

        # Priority 5: Failure Information
        if failure_block:
            sections.append(("failure", 4, failure_block.strip()))

        # Priority 6: Latest Observation
        if observation_block:
            sections.append(("observation", 5, observation_block.strip()))

        # Priority 7: Local Graph Block
        if local_graph_block:
            sections.append(("graph", 6, local_graph_block.strip()))

        # Enforce budget starting from lowest priority
        suffix = "\n\nExecute the current task now. If a tool is required, call it. Otherwise reply concisely."
        def rendered_size():
            return sum(len(content) for _, _, content in sections) + max(0, len(sections) - 2) * 2 + len(suffix)
        total_len = rendered_size()
        pruned_sections = []
        if total_len > self.max_context_chars:
            # Sort by priority descending (highest priority number gets pruned first)
            sections.sort(key=lambda x: x[1], reverse=True)
            while total_len > self.max_context_chars and sections:
                if sections[0][1] <= 2:
                    break # Never prune system or core goal
                dropped = sections.pop(0)
                total_len = rendered_size()
                pruned_sections.append(dropped[0])
            # Re-sort by priority ascending
            sections.sort(key=lambda x: x[1])
        if total_len > self.max_context_chars:
            raise ValueError("Context budget exceeded by required goal or constraints; shorten the request.")

        # Construct OpenAI message format
        messages = [
            {"role": "system", "content": sys_content}
        ]
        user_body = "\n\n".join(content for sec_name, _, content in sections if sec_name != "system")
        user_body += suffix
        messages.append({"role": "user", "content": user_body})

        stats = {
            "total_chars": sum(len(m["content"]) for m in messages),
            "estimated_tokens": sum(len(m["content"]) for m in messages) // 4,
            "pruned_sections": pruned_sections,
        }
        return messages, stats
