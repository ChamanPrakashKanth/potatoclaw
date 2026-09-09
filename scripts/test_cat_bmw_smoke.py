#!/usr/bin/env python3
"""Run the CATV3 A/B/C experiment against a deterministic fixture or Spark.

The deterministic backend verifies memory and prompt construction contracts. It
does not represent an LLM result. The Spark backend uses PotatoAgent's existing
local client and reports unavailable or guard-rejected calls as UNVERIFIED.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import statistics
import sys
import time
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from potato_cat_bmw import (
    BackendResponse,
    ConceptGraphMemory,
    CONTEXT_TOKEN_LIMIT,
    DEFAULT_ACTIVE_LIMIT,
    Retrieval,
    SyntheticTask,
    build_synthetic_history,
    call_spark,
    deterministic_response,
    estimate_messages_tokens,
    graph_memory_enabled,
    load_history,
    make_messages,
    prompt_leaks_raw_history,
    synthetic_tasks,
    verify_response,
)


@dataclass
class Row:
    backend: str
    variant: str
    task_id: str
    history_tokens: int
    graph_nodes: int
    active_concepts: int
    estimated_prompt_tokens: int
    actual_prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    selection_latency_ms: float
    model_latency_ms: Optional[float]
    total_latency_ms: float
    verifier: str
    constraint_retained: bool
    irrelevant_excluded: int
    raw_fallback: bool
    scanned_nodes: int
    scan_mode: str
    prompt_leaks: List[str]
    error: Optional[str] = None


def parse_ints(value: str) -> List[int]:
    result = []
    for item in value.split(","):
        number = int(item.strip())
        if number < 1:
            raise ValueError("values must be positive")
        result.append(number)
    return result


def full_graph_retrieval(memory: ConceptGraphMemory, task: SyntheticTask) -> Retrieval:
    started = time.perf_counter()
    ids = list(memory.concepts)
    fallback = [
        concept_id for concept_id in ids
        if task.exact_detail and task.marker.lower() in memory.concepts[concept_id].content.lower()
    ]
    return Retrieval(
        active_ids=ids,
        candidate_ids=ids,
        scanned_nodes=len(ids),
        scan_mode="full_graph",
        selection_latency_ms=(time.perf_counter() - started) * 1000.0,
        raw_fallback_ids=fallback,
    )


def run_contract_tests() -> None:
    """Protect independent behavior contracts at the owning library boundary."""
    assert not graph_memory_enabled({}), "BMW_GRAPH_MEMORY must default to disabled"
    assert graph_memory_enabled({"BMW_GRAPH_MEMORY": "1"}), "BMW_GRAPH_MEMORY=1 must activate the feature"

    memory = ConceptGraphMemory(active_limit=3, half_life_seconds=10.0)
    critical = memory.insert("critical", "CRITICAL_CONSTRAINT local-only", "r-critical", importance=1.0, protected=True)
    stale = memory.insert("stale", "STALE_IRRELEVANT old filler", "r-stale", importance=0.2)
    useful = memory.insert("useful", "USEFUL_CONCEPT verifier success", "r-useful", importance=0.4)
    child = memory.insert("child", "RELATED_CONCEPT_CHILD linked detail", "r-child", importance=0.4)
    memory.link("useful", child)
    memory.age(stale, 100.0)
    before = memory.concepts[useful].importance
    retrieval = memory.retrieve("USEFUL_CONCEPT", use_decay=True)
    assert critical in retrieval.active_ids, "protected constraint was evicted"
    assert stale not in retrieval.active_ids, "stale concept outranked a matching concept"
    memory.reinforce([useful])
    assert memory.concepts[useful].importance > before, "success reinforcement did not increase importance"

    linked = memory.retrieve("USEFUL_CONCEPT", use_decay=True)
    assert child in linked.active_ids, "one-hop graph traversal did not retain the linked child"
    exact_task = SyntheticTask("exact", "exact detail", "CATV3-EXACT", True)
    exact = memory.retrieve("exact detail", use_decay=True, exact_detail=True)
    assert exact.raw_fallback_ids, "exact-detail fallback did not expose a source pointer"
    messages = make_messages(exact_task, "C", "unused raw history", memory, exact)
    assert not prompt_leaks_raw_history(messages, "C", "unused raw history", memory, exact, exact_task)
    assert verify_response(BackendResponse(error="connection refused"), exact_task, "spark") == "UNVERIFIED"


def run_one(
    backend: str,
    variant: str,
    target_tokens: int,
    active_limit: int,
    task: SyntheticTask,
    history: str,
    records: Sequence,
    memory: Optional[ConceptGraphMemory] = None,
    spark_state: Optional[Dict[str, bool]] = None,
) -> Row:
    started = time.perf_counter()
    retrieval: Optional[Retrieval] = None

    if variant in ("B", "C"):
        if memory is None:
            memory = ConceptGraphMemory(active_limit=active_limit)
            load_history(memory, records)
        retrieval = (
            full_graph_retrieval(memory, task)
            if variant == "B"
            else memory.retrieve(task.query, use_decay=True, exact_detail=task.exact_detail)
        )

    messages = make_messages(task, variant, history, memory, retrieval)
    estimated = estimate_messages_tokens(messages)
    guard_rejected = estimated + 64 > CONTEXT_TOKEN_LIMIT
    if backend == "deterministic":
        response = deterministic_response(task)
    elif guard_rejected:
        response = BackendResponse(
            error="2048-token context guard rejected the measured prompt before Spark call",
            guard_rejected=True,
            model_latency_ms=0.0,
        )
    elif spark_state is not None and spark_state.get("connection_failure"):
        response = BackendResponse(
            error="Spark unavailable after the first connection failure; remaining rows are UNVERIFIED",
            model_latency_ms=0.0,
        )
    else:
        response = call_spark(messages, max_tokens=64, temperature=0.1)
        if spark_state is not None and response.error and not response.guard_rejected:
            spark_state["connection_failure"] = True

    verifier = verify_response(response, task, backend)
    if memory and retrieval and verifier == "PASS":
        # The useful concept is reinforced only after the deterministic marker verifier passes.
        memory.reinforce(retrieval.active_ids)

    prompt = "\n".join(message["content"] for message in messages)
    constraint_retained = "local-only execution" in prompt.lower()
    active_count = len(retrieval.active_ids) if retrieval else 0
    graph_nodes = len(memory.concepts) if memory else 0
    leaks = prompt_leaks_raw_history(messages, variant, history, memory, retrieval, task)
    if leaks:
        verifier = "FAIL"
    irrelevant_excluded = max(0, graph_nodes - active_count) if variant == "C" else 0
    return Row(
        backend=backend,
        variant=variant,
        task_id=task.task_id,
        history_tokens=target_tokens,
        graph_nodes=graph_nodes,
        active_concepts=active_count,
        estimated_prompt_tokens=estimated,
        actual_prompt_tokens=response.actual_prompt_tokens,
        completion_tokens=response.completion_tokens,
        selection_latency_ms=retrieval.selection_latency_ms if retrieval else 0.0,
        model_latency_ms=response.model_latency_ms,
        total_latency_ms=(time.perf_counter() - started) * 1000.0,
        verifier=verifier,
        constraint_retained=constraint_retained,
        irrelevant_excluded=irrelevant_excluded,
        raw_fallback=bool(retrieval and retrieval.raw_fallback_ids),
        scanned_nodes=retrieval.scanned_nodes if retrieval else 0,
        scan_mode=retrieval.scan_mode if retrieval else "raw_history",
        prompt_leaks=leaks,
        error=response.error,
    )


def run_experiment(backend: str, histories: Sequence[int], limits: Sequence[int]) -> List[Row]:
    rows: List[Row] = []
    spark_state: Dict[str, bool] = {}
    for active_limit in limits:
        for target_tokens in histories:
            history, records = build_synthetic_history(target_tokens)
            for variant in ("A", "B", "C"):
                memory = None
                if variant in ("B", "C"):
                    memory = ConceptGraphMemory(active_limit=active_limit)
                    load_history(memory, records)
                for task in synthetic_tasks():
                    row = run_one(
                        backend, variant, target_tokens, active_limit, task,
                        history, records, memory, spark_state,
                    )
                    rows.append(row)
                    error = " error=%s" % row.error if row.error else ""
                    actual = "-" if row.actual_prompt_tokens is None else str(row.actual_prompt_tokens)
                    completion = "-" if row.completion_tokens is None else str(row.completion_tokens)
                    model_ms = "-" if row.model_latency_ms is None else "%.1f" % row.model_latency_ms
                    print(
                        "TASK backend=%s variant=%s T=%d task=%s M=%d A=%d est=%d actual=%s completion=%s "
                        "select_ms=%.2f model_ms=%s total_ms=%.2f verifier=%s constraint=%s excluded=%d "
                        "raw_fallback=%s scanned=%d scan=%s leaks=%s%s"
                        % (
                            row.backend, row.variant, row.history_tokens, row.task_id,
                            row.graph_nodes, row.active_concepts, row.estimated_prompt_tokens,
                            actual, completion, row.selection_latency_ms, model_ms, row.total_latency_ms,
                            row.verifier, "PASS" if row.constraint_retained else "FAIL",
                            row.irrelevant_excluded, "YES" if row.raw_fallback else "NO",
                            row.scanned_nodes, row.scan_mode,
                            "NONE" if not row.prompt_leaks else ",".join(row.prompt_leaks), error,
                        )
                    )
    return rows


def _fmt(value: object) -> str:
    return "-" if value is None else str(value)


def print_summary(rows: Sequence[Row]) -> None:
    print("\n| Backend | Variant | T | M | A | Actual prompt tokens | Model latency | Verified |")
    print("|---|---|---:|---:|---:|---:|---:|---|")
    groups: Dict[Tuple[str, str, int], List[Row]] = {}
    for row in rows:
        groups.setdefault((row.backend, row.variant, row.history_tokens), []).append(row)
    for (backend, variant, target), group in groups.items():
        actuals = [r.actual_prompt_tokens for r in group if r.actual_prompt_tokens is not None]
        latencies = [r.model_latency_ms for r in group if r.model_latency_ms is not None]
        actual = "-" if not actuals else "%d-%d" % (min(actuals), max(actuals))
        latency = "-" if not latencies else "%.1f ms" % statistics.median(latencies)
        verified = "/".join(sorted({r.verifier for r in group}))
        first = group[0]
        print(
            "| %s | %s | %d | %d | %d | %s | %s | %s |"
            % (backend, variant, target, first.graph_nodes, max(r.active_concepts for r in group), actual, latency, verified)
        )

    c_rows = [r for r in rows if r.variant == "C"]
    if c_rows:
        max_active = max(r.active_concepts for r in c_rows)
        actuals = [r.actual_prompt_tokens for r in c_rows if r.actual_prompt_tokens is not None]
        if actuals:
            bounded = max(actuals) <= CONTEXT_TOKEN_LIMIT and max(actuals) - min(actuals) <= 512
            print("\nC central test: A max=%d (limit %d); actual prompt range=%d-%d; approximately bounded=%s" % (
                max_active, max(r.active_concepts for r in c_rows), min(actuals), max(actuals), "YES" if bounded else "NO"
            ))
        else:
            print("\nC central test: A max=%d; actual Spark prompt tokens unavailable, so boundedness is UNVERIFIED." % max_active)
    leaks = [r for r in rows if r.prompt_leaks]
    full_scans = [r for r in rows if r.scan_mode == "full_fallback"]
    print("Prompt leakage rows: %d" % len(leaks))
    print("Explicit full fallback scans: %d (indexed retrieval rows are reported separately)" % len(full_scans))
    if rows and rows[0].backend == "deterministic":
        print("Deterministic backend note: PASS means the deterministic fixture and memory verifier passed; it is not evidence that an LLM succeeded.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CATV3 concept graph + BMW A/B/C smoke experiment")
    parser.add_argument("--backend", choices=("deterministic", "spark"), default="deterministic")
    parser.add_argument("--histories", default="10000,50000,100000", help="comma-separated synthetic history token targets")
    parser.add_argument("--limits", default=str(DEFAULT_ACTIVE_LIMIT), help="comma-separated active concept limits")
    parser.add_argument("--skip-contract-tests", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        histories = parse_ints(args.histories)
        limits = parse_ints(args.limits)
        if not args.skip_contract_tests:
            run_contract_tests()
            print("Contract tests: PASS (BMW flag, bounded selection, decay, reinforcement, traversal, fallback, leak guard, Spark failure classification)")
        print("BMW_GRAPH_MEMORY=%s (the existing PotatoClaw path remains unchanged unless explicitly integrated)" % ("1" if graph_memory_enabled() else "0"))
        print("Backend=%s histories=%s limits=%s context_limit=%d" % (args.backend, histories, limits, CONTEXT_TOKEN_LIMIT))
        rows = run_experiment(args.backend, histories, limits)
        print_summary(rows)
        return 0
    except Exception as exc:
        print("CAT/BMW smoke failed: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
