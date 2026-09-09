#!/usr/bin/env python3
"""Reproducible CAT graph/BMW smoke test; no model weights or network required."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass

from potato_cat_bmw import ConceptGraphMemory
from potato_verifier import DeterministicVerifier


@dataclass
class Task:
    name: str
    query: str
    expected: tuple[str, ...]
    exact_detail: bool = False


def tok(text: str) -> int:
    return max(1, len(text) // 4)


def make_memory(limit: int = 32, history_tokens: int = 10_000) -> ConceptGraphMemory:
    mem = ConceptGraphMemory(active_limit=limit)
    mem.add_observation("The deployment must never delete user files; preserve existing data.",
                        importance=1.0, decay_rate=0.00001, protected=True,
                        concept_id="constraint_no_delete")
    mem.add_observation("Previous attempt: retrying the same malformed JSON action failed; do not repeat it.",
                        importance=0.85, decay_rate=0.0005, concept_id="failure_bad_json")
    mem.add_observation("The verified repair action is use strict JSON with double quotes.",
                        importance=0.82, decay_rate=0.001, concept_id="repair_strict_json",
                        relations=["failure_bad_json"])
    mem.add_observation("Frequently useful rule: run the deterministic verifier after every file action.",
                        importance=0.80, decay_rate=0.001, concept_id="rule_verify",
                        relations=["constraint_no_delete"])
    mem.add_observation("A related concept: file write success is confirmed by exit code zero.",
                        importance=0.65, decay_rate=0.01, concept_id="exit_code_success",
                        relations=["rule_verify"])
    mem.add_observation("Exact deployment detail: the approved artifact path is /tmp/potato-proof.txt.",
                        importance=0.75, decay_rate=0.002, concept_id="exact_artifact_path")
    # Synthetic disposable history makes T grow while the concept interface stays compact.
    i = 0
    while mem.stats()["raw_tokens"] < history_tokens:
        i += 1
        mem.add_observation(f"Disposable observation {i}: unrelated color={i % 17}, noise={i * 13}.",
                            importance=0.05, decay_rate=0.15,
                            concept_id=f"stale_{i}")
    return mem


TASKS = [
    Task("old constraint", "deploy artifact while preserving existing data", ("constraint_no_delete",)),
    Task("old failure", "avoid malformed JSON and use strict JSON repair", ("failure_bad_json", "repair_strict_json")),
    Task("frequent utility", "verify the file action after a write", ("rule_verify",)),
    Task("related traversal", "confirm file write using exit code", ("exit_code_success", "rule_verify")),
    Task("stale exclusion", "answer about current weather", ()),
    Task("exact fallback", "what is the exact approved artifact path", ("exact_artifact_path",), True),
]

MARKERS = {
    "constraint_no_delete": "never delete user files",
    "failure_bad_json": "malformed JSON",
    "repair_strict_json": "strict JSON",
    "rule_verify": "deterministic verifier",
    "exit_code_success": "exit code zero",
    "exact_artifact_path": "/tmp/potato-proof.txt",
}


def run_variant(name: str, history_tokens: int, limit: int, mode: str) -> dict:
    mem = make_memory(limit, history_tokens)
    rows = []
    for task in TASKS:
        t0 = time.perf_counter()
        if mode == "A":
            raw = "\n".join(r.text for r in mem.raw_records.values())
            memory_block = "[RAW HISTORY]\n" + raw
            selection = {"active_nodes": len(mem.nodes), "selection_scanned": len(mem.nodes),
                         "raw_fallback": False}
        elif mode == "B":
            lines = ["[ALL CONCEPT GRAPH]"]
            for node in mem.nodes.values():
                lines.append(f"{node.concept_id}|{node.content}")
            memory_block = "\n".join(lines)
            selection = {"active_nodes": len(mem.nodes), "selection_scanned": len(mem.nodes),
                         "raw_fallback": False}
        else:
            memory_block, selection = mem.serialize(task.query, limit, task.exact_detail)
        retrieval_ms = (time.perf_counter() - t0) * 1000
        prompt = f"SYSTEM: use only supplied memory.\nTASK: {task.query}\n{memory_block}"
        infer_t0 = time.perf_counter()
        # Deterministic stand-in for Spark: the measured prompt is real, and this
        # verifier intentionally checks whether the required concepts reached it.
        found = tuple(cid for cid in task.expected
                      if cid in prompt or MARKERS.get(cid, "") in prompt)
        context_allowed = tok(prompt) <= 2048
        response = "ACTION: verified-safe" if (not task.expected or len(found) == len(task.expected)) else "ACTION: unsafe"
        inference_ms = (time.perf_counter() - infer_t0) * 1000
        verification = DeterministicVerifier.verify_terminal_output_contains(response, "verified-safe")
        if not context_allowed:
            verification = DeterministicVerifier.verify_terminal_output_contains("context rejected", "verified-safe")
        required_retained = len(found) == len(task.expected)
        irrelevant_excluded = "Disposable observation" not in memory_block
        rows.append({
            "task": task.name, "prompt_tokens": tok(prompt), "active_nodes": selection["active_nodes"],
            "retrieval_ms": round(retrieval_ms, 3), "inference_ms": round(inference_ms, 3),
            "verified": verification.passed, "required_retained": required_retained,
            "irrelevant_excluded": irrelevant_excluded, "raw_fallback": selection.get("raw_fallback", False),
            "scanned": selection.get("selection_scanned", 0),
            "context_allowed": context_allowed,
        })
    stats = mem.stats()
    return {"variant": name, "mode": mode, "raw_history_tokens": stats["raw_tokens"],
            "concept_nodes": stats["concept_nodes"], "rows": rows,
            "prompt_tokens": [r["prompt_tokens"] for r in rows],
            "verified": sum(r["verified"] for r in rows), "tasks": len(rows)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limits", default="16,32,64")
    parser.add_argument("--histories", default="10000,50000,100000")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    limits = [int(x) for x in args.limits.split(",")]
    histories = [int(x) for x in args.histories.split(",")]
    report = {"live_model": False, "note": "Spark endpoint unavailable; deterministic prompt-path smoke test.",
              "bounded_prompt": [], "abc": []}
    for h in histories:
        for limit in limits:
            report["bounded_prompt"].append(run_variant(f"C-A{limit}-T{h}", h, limit, "C"))
    for mode, name in (("A", "A existing raw context"), ("B", "B graph no decay"), ("C", "C graph + BMW")):
        report["abc"].append(run_variant(name, 10_000, 32, mode))
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print("CAT/BMW smoke test (deterministic prompt-path; Spark offline)")
    print("A/B/C at T=10k, active limit=32")
    print("variant | raw T | nodes M | mean prompt | max prompt | verified")
    for row in report["abc"]:
        print(f"{row['variant']} | {row['raw_history_tokens']} | {row['concept_nodes']} | "
              f"{statistics.mean(row['prompt_tokens']):.1f} | {max(row['prompt_tokens'])} | "
              f"{row['verified']}/{row['tasks']}")
    print("\nT increases while A is fixed at 16/32/64")
    print("T | A | M | prompt token range | retained | excluded | scanned")
    for row in report["bounded_prompt"]:
        rs = row["rows"]
        print(f"{row['raw_history_tokens']} | {rs[0]['active_nodes']} | {row['concept_nodes']} | "
              f"{min(row['prompt_tokens'])}-{max(row['prompt_tokens'])} | "
              f"{sum(x['required_retained'] for x in rs)}/{len(rs)} | "
              f"{sum(x['irrelevant_excluded'] for x in rs)}/{len(rs)} | "
              f"{max(x['scanned'] for x in rs)}")
    print("\nRaw JSON: rerun with --json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
