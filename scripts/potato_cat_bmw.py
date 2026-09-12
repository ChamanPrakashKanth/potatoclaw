#!/usr/bin/env python3
"""CATV3 concept graph and bounded working-memory experiment helpers.

This module is deliberately separate from the default PotatoClaw execution
path.  The experiment is opt-in through ``BMW_GRAPH_MEMORY=1`` and keeps raw
source records outside the prompt unless an exact-detail query asks for one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import os
import re
import time
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


BMW_GRAPH_MEMORY = "BMW_GRAPH_MEMORY"
CONTEXT_TOKEN_LIMIT = 2048
DEFAULT_ACTIVE_LIMIT = 32
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_:-]*", re.IGNORECASE)


def graph_memory_enabled(environ: Optional[Dict[str, str]] = None) -> bool:
    """Return the explicit opt-in state without changing the default agent path."""
    values = os.environ if environ is None else environ
    return values.get(BMW_GRAPH_MEMORY, "0").strip() == "1"


def estimate_tokens(text: str) -> int:
    """Use the repository's conservative character estimate for offline metrics."""
    return max(1, math.ceil(len(text.encode("utf-8")) / 4))


def estimate_messages_tokens(messages: Sequence[Dict[str, str]]) -> int:
    return estimate_tokens("\n".join(m.get("content", "") for m in messages))


def _terms(text: str) -> Set[str]:
    terms: Set[str] = set()
    for match in _TOKEN_RE.finditer(text):
        whole = match.group(0).lower()
        terms.add(whole)
        terms.update(part.strip(":-") for part in whole.split("_") if part.strip(":-"))
    return terms


@dataclass
class RawRecord:
    record_id: str
    content: str


@dataclass
class Concept:
    concept_id: str
    content: str
    source_record_id: str
    importance: float = 0.5
    protected: bool = False
    success_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)

    def decay(self, now: Optional[float] = None, half_life_seconds: float = 300.0) -> float:
        now = time.time() if now is None else now
        age = max(0.0, now - self.last_access)
        return math.pow(0.5, age / half_life_seconds)


@dataclass
class Retrieval:
    active_ids: List[str]
    candidate_ids: List[str]
    scanned_nodes: int
    scan_mode: str
    selection_latency_ms: float
    raw_fallback_ids: List[str] = field(default_factory=list)


class ConceptGraphMemory:
    """Incremental concept memory with indexed retrieval and bounded rendering."""

    def __init__(self, active_limit: int = DEFAULT_ACTIVE_LIMIT, half_life_seconds: float = 300.0):
        if active_limit < 1:
            raise ValueError("active_limit must be positive")
        self.active_limit = active_limit
        self.half_life_seconds = half_life_seconds
        self.concepts: Dict[str, Concept] = {}
        self.records: Dict[str, RawRecord] = {}
        self.edges: Dict[str, Set[str]] = {}
        self.index: Dict[str, Set[str]] = {}

    @property
    def nodes(self) -> Dict[str, Concept]:
        """Compatibility view for the core PotatoAgent integration."""
        return self.concepts

    def insert(
        self,
        concept_id: str,
        content: str,
        source_record_id: Optional[str] = None,
        importance: float = 0.5,
        protected: bool = False,
        raw_content: Optional[str] = None,
    ) -> str:
        if concept_id in self.concepts:
            raise ValueError("duplicate concept: %s" % concept_id)
        record_id = source_record_id or concept_id
        self.records.setdefault(record_id, RawRecord(record_id, content if raw_content is None else raw_content))
        concept = Concept(
            concept_id=concept_id,
            content=content.strip(),
            source_record_id=record_id,
            importance=max(0.0, min(1.0, importance)),
            protected=protected,
        )
        self.concepts[concept_id] = concept
        self.edges.setdefault(concept_id, set())
        for term in _terms(content):
            self.index.setdefault(term, set()).add(concept_id)
        return concept_id

    def add_observation(
        self,
        content: str,
        *,
        importance: float = 0.5,
        decay_rate: float = 0.01,
        protected: bool = False,
        concept_id: Optional[str] = None,
        relations: Iterable[str] = (),
    ) -> str:
        """Accept the core-agent observation contract without rebuilding indexes."""
        del decay_rate  # This implementation uses one bounded half-life per memory.
        concept_id = concept_id or "concept_%05d" % (len(self.concepts) + 1)
        if concept_id in self.concepts:
            concept = self.concepts[concept_id]
            concept.content = content.strip()
            concept.importance = max(concept.importance, min(1.0, importance))
            concept.protected = concept.protected or protected
            for term in _terms(content):
                self.index.setdefault(term, set()).add(concept_id)
        else:
            self.insert(concept_id, content, importance=importance, protected=protected)
        for related_id in relations:
            if related_id in self.concepts:
                self.link(concept_id, related_id)
        return concept_id

    def link(self, left_id: str, right_id: str) -> None:
        if left_id not in self.concepts or right_id not in self.concepts:
            raise KeyError("both graph endpoints must exist")
        self.edges.setdefault(left_id, set()).add(right_id)
        self.edges.setdefault(right_id, set()).add(left_id)

    def age(self, concept_id: str, seconds: float) -> None:
        self.concepts[concept_id].last_access -= max(0.0, seconds)

    def reinforce(
        self,
        concept_ids: Iterable[str],
        amount: float = 0.1,
        success: Optional[bool] = None,
    ) -> None:
        for concept_id in concept_ids:
            concept = self.concepts.get(concept_id)
            if concept is None:
                continue
            if success is False:
                concept.last_access = time.time()
                continue
            concept.success_count += 1
            concept.importance = min(1.0, concept.importance + amount)
            concept.last_access = time.time()

    def _score(self, concept: Concept, query_terms: Set[str], use_decay: bool) -> float:
        overlap = len(query_terms & _terms(concept.content))
        graph_bonus = 0.0
        if overlap:
            graph_bonus = 0.25
        decay = concept.decay(half_life_seconds=self.half_life_seconds) if use_decay else 1.0
        return (2.0 * overlap + concept.importance + 0.2 * concept.success_count + graph_bonus) * decay

    def retrieve(self, query: str, use_decay: bool = True, exact_detail: bool = False) -> Retrieval:
        started = time.perf_counter()
        query_terms = _terms(query)
        indexed: Set[str] = set()
        for term in query_terms:
            indexed.update(self.index.get(term, set()))
        if indexed:
            candidate_ids = set(indexed)
            scan_mode = "indexed_candidates"
        else:
            candidate_ids = set(self.concepts)
            scan_mode = "full_fallback"

        # A one-hop expansion is deterministic and does not require scanning M.
        expanded = set(candidate_ids)
        for concept_id in list(candidate_ids):
            expanded.update(self.edges.get(concept_id, set()))
        candidate_ids = expanded

        ranked = sorted(
            candidate_ids,
            key=lambda cid: self._score(self.concepts[cid], query_terms, use_decay),
            reverse=True,
        )
        protected = [cid for cid, concept in self.concepts.items() if concept.protected]
        active: List[str] = []
        for concept_id in protected + ranked:
            if concept_id not in active:
                active.append(concept_id)
            if len(active) >= self.active_limit:
                break
        for concept_id in active:
            self.concepts[concept_id].last_access = time.time()

        fallback_ids: List[str] = []
        if exact_detail:
            for concept_id in active:
                concept = self.concepts[concept_id]
                if concept.source_record_id in self.records:
                    fallback_ids.append(concept_id)

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return Retrieval(
            active_ids=active,
            candidate_ids=sorted(candidate_ids),
            scanned_nodes=len(candidate_ids),
            scan_mode=scan_mode,
            selection_latency_ms=elapsed_ms,
            raw_fallback_ids=fallback_ids,
        )

    def compact_content(self, concept_id: str, max_chars: int = 72) -> str:
        content = self.concepts[concept_id].content.replace("\n", " ").strip()
        return content if len(content) <= max_chars else content[: max_chars - 3] + "..."

    def render_active(self, retrieval: Retrieval, max_chars: int = 1050) -> str:
        lines = ["[ACTIVE CONCEPTS]"]
        for concept_id in retrieval.active_ids:
            concept = self.concepts[concept_id]
            prefix = "[CRITICAL] " if concept.protected else "- "
            lines.append("%s%s=%s" % (prefix, concept_id, self.compact_content(concept_id)))
        rendered = "\n".join(lines)
        return rendered if len(rendered) <= max_chars else rendered[: max_chars - 14] + "\n[...bounded]"

    def render_full_graph(self) -> str:
        lines = ["[FULL CONCEPT GRAPH]"]
        for concept_id in self.concepts:
            lines.append("- %s=%s" % (concept_id, self.compact_content(concept_id, 80)))
        return "\n".join(lines)

    def render_raw_fallback(self, retrieval: Retrieval) -> str:
        if not retrieval.raw_fallback_ids:
            return ""
        lines = ["[RAW SOURCE RECORDS: EXACT DETAIL FALLBACK]"]
        for concept_id in retrieval.raw_fallback_ids:
            record_id = self.concepts[concept_id].source_record_id
            lines.append("- %s=%s" % (record_id, self.records[record_id].content))
        return "\n".join(lines)

    def serialize(
        self,
        query: str,
        limit: Optional[int] = None,
        include_raw: bool = False,
    ) -> Tuple[str, Dict[str, object]]:
        """Serialize bounded graph context for the core PotatoAgent contract."""
        requested_limit = max(1, limit or self.active_limit)
        retrieval = self.retrieve(query, use_decay=True, exact_detail=include_raw)
        if len(retrieval.active_ids) > requested_limit:
            retrieval = Retrieval(
                active_ids=retrieval.active_ids[:requested_limit],
                candidate_ids=retrieval.candidate_ids,
                scanned_nodes=retrieval.scanned_nodes,
                scan_mode=retrieval.scan_mode,
                selection_latency_ms=retrieval.selection_latency_ms,
                raw_fallback_ids=retrieval.raw_fallback_ids[:requested_limit],
            )
        block = self.render_active(retrieval)
        if include_raw:
            raw_block = self.render_raw_fallback(retrieval)
            if raw_block:
                block += "\n" + raw_block
        return block, {
            "active_nodes": len(retrieval.active_ids),
            "prompt_tokens": estimate_tokens(block),
            "raw_fallback": bool(include_raw and retrieval.raw_fallback_ids),
            "selection_candidates": len(retrieval.candidate_ids),
            "selection_scanned": retrieval.scanned_nodes,
            "selection_fallback_scan": retrieval.scan_mode == "full_fallback",
        }


class BmwGraphBridge:
    """Small opt-in adapter for runtime entry points such as chat and X."""

    def __init__(self, namespace: str, active_limit: int = 8):
        self.namespace = namespace
        self.enabled = graph_memory_enabled()
        self.memory = ConceptGraphMemory(active_limit=active_limit) if self.enabled else None
        self._sequence = 0

    def clear(self) -> None:
        if self.enabled:
            self.memory = ConceptGraphMemory(active_limit=self.memory.active_limit)
            self._sequence = 0

    def add_event(
        self,
        label: str,
        content: str,
        importance: float = 0.5,
        protected: bool = False,
        source_record_id: Optional[str] = None,
    ) -> Optional[str]:
        if not self.enabled or self.memory is None:
            return None
        self._sequence += 1
        event_id = "%s_%05d" % (self.namespace, self._sequence)
        source_id = source_record_id or event_id
        terms = _TOKEN_RE.findall(content)[:12]
        summary = "%s summary: %s" % (label, " ".join(terms) if terms else "event")
        return self.memory.insert(
            event_id,
            summary,
            source_record_id=source_id,
            importance=importance,
            protected=protected,
            raw_content=content,
        )

    def link(self, left_id: Optional[str], right_id: Optional[str]) -> None:
        if self.enabled and self.memory is not None and left_id and right_id:
            self.memory.link(left_id, right_id)

    def context(self, query: str, exact_detail: bool = False) -> Tuple[str, Optional[Retrieval]]:
        if not self.enabled or self.memory is None or not self.memory.concepts:
            return "", None
        retrieval = self.memory.retrieve(query, use_decay=True, exact_detail=exact_detail)
        block = "[BMW GRAPH MEMORY]\n" + self.memory.render_active(retrieval, max_chars=700)
        if exact_detail:
            fallback = self.memory.render_raw_fallback(retrieval)
            if fallback:
                block += "\n" + fallback
        return block, retrieval

    def stats(self, retrieval: Optional[Retrieval] = None) -> Dict[str, object]:
        if not self.enabled or self.memory is None:
            return {"enabled": False, "nodes": 0, "active": 0, "scanned": 0, "scan_mode": "disabled"}
        return {
            "enabled": True,
            "nodes": len(self.memory.concepts),
            "active": len(retrieval.active_ids) if retrieval else 0,
            "scanned": retrieval.scanned_nodes if retrieval else 0,
            "scan_mode": retrieval.scan_mode if retrieval else "idle",
        }


@dataclass(frozen=True)
class SyntheticTask:
    task_id: str
    query: str
    marker: str
    exact_detail: bool = False


@dataclass
class BackendResponse:
    content: str = ""
    actual_prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    model_latency_ms: Optional[float] = None
    error: Optional[str] = None
    guard_rejected: bool = False


def synthetic_tasks() -> List[SyntheticTask]:
    return [
        SyntheticTask("critical_constraint", "What old constraint must still be obeyed?", "CRITICAL_CONSTRAINT"),
        SyntheticTask("old_concept", "Which old verifier gate is relevant?", "USEFUL_CONCEPT"),
        SyntheticTask("failed_action", "Which old failed action must not be repeated?", "FAILED_ACTION"),
        SyntheticTask("reinforcement", "Which frequently useful verifier memory received success reinforcement?", "USEFUL_CONCEPT"),
        SyntheticTask("stale_concepts", "Which memories are stale and irrelevant?", "STALE_IRRELEVANT"),
        SyntheticTask("one_hop_graph", "Which linked child is one hop from graph retrieval?", "RELATED_CONCEPT_CHILD"),
        SyntheticTask("exact_detail", "Give the exact detail and source record for the CATV3 checksum.", "CATV3-EXACT-7F19", True),
        SyntheticTask("no_match_scan", "Find no-match-sentinel-unique.", "NO_MATCH_SENTINEL"),
    ]


def build_synthetic_history(target_tokens: int) -> Tuple[str, List[RawRecord]]:
    """Create deterministic histories whose measured size is exactly target_tokens."""
    if target_tokens < 1:
        raise ValueError("history size must be positive")
    seeds = [
        "CRITICAL_CONSTRAINT: Never send data to cloud services; preserve local-only execution.",
        "FAILED_ACTION: remote_upload_to_cloud failed with a blocked network; do not repeat it.",
        "USEFUL_CONCEPT: deterministic verifier success gates model claims before completion.",
        "RELATED_CONCEPT_PARENT: indexed graph retrieval connects verifier concepts.",
        "RELATED_CONCEPT_CHILD: one-hop traversal preserves the adjacent verifier concept.",
        "EXACT_DETAIL: CATV3-EXACT-7F19 source_line=synthetic-checksum-42.",
    ]
    target_chars = target_tokens * 4
    lines = list(seeds)
    index = 0
    while len("\n".join(lines)) + 1 < target_chars:
        filler = "STALE_IRRELEVANT_%05d: unrelated synthetic observation about a disconnected topic." % index
        filler = (filler + " x" * 110)[:238]
        lines.append(filler)
        index += 1
    history = "\n".join(lines)[:target_chars]
    records = [RawRecord("record_%05d" % idx, line) for idx, line in enumerate(history.splitlines()) if line]
    return history, records


def load_history(memory: ConceptGraphMemory, records: Sequence[RawRecord]) -> None:
    for idx, record in enumerate(records):
        content = record.content
        lowered = content.lower()
        protected = "critical_constraint" in lowered
        importance = 1.0 if protected else (0.85 if "useful_concept" in lowered else 0.15)
        label, _, detail = content.partition(":")
        # Keep the semantic concept distinct from its raw source record. The
        # source pointer remains available only to explicit exact-detail fallback.
        summary = "%s concept summary" % label.strip()
        if "USEFUL_CONCEPT" in label:
            summary += " verifier gate success"
        elif "FAILED_ACTION" in label:
            summary += " remote action blocked"
        elif "RELATED_CONCEPT_PARENT" in label:
            summary += " graph retrieval"
        elif "RELATED_CONCEPT_CHILD" in label:
            summary += " one-hop linked child"
        if "CATV3-EXACT-7F19" in detail:
            summary += " CATV3-EXACT-7F19"
        memory.insert("concept_%05d" % idx, summary, record.record_id, importance=importance, protected=protected)
        memory.records[record.record_id] = record
    by_text = {concept.content.split(":", 1)[0]: concept.concept_id for concept in memory.concepts.values()}
    parent = by_text.get("RELATED_CONCEPT_PARENT")
    child = by_text.get("RELATED_CONCEPT_CHILD")
    if parent and child:
        memory.link(parent, child)


def make_messages(
    task: SyntheticTask,
    variant: str,
    history: str,
    memory: Optional[ConceptGraphMemory],
    retrieval: Optional[Retrieval],
) -> List[Dict[str, str]]:
    system = (
        "You are the CATV3 experiment responder. Answer briefly and include the requested marker. "
        "Do not invent actions."
    )
    parts = [
        "TASK: %s" % task.query,
        "REQUIRED MARKER: %s" % task.marker,
        "CRITICAL CONSTRAINT: local-only execution; no cloud services.",
    ]
    if variant == "A":
        parts.append("[RAW HISTORY]\n" + history)
    elif variant == "B":
        parts.append(memory.render_full_graph() if memory else "[FULL CONCEPT GRAPH]")
    elif variant == "C":
        parts.append(memory.render_active(retrieval) if memory and retrieval else "[ACTIVE CONCEPTS]")
    else:
        raise ValueError("unknown variant: %s" % variant)
    if task.exact_detail and memory and retrieval:
        parts.append(memory.render_raw_fallback(retrieval))
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(parts)}]


def prompt_leaks_raw_history(
    messages: Sequence[Dict[str, str]],
    variant: str,
    history: str,
    memory: Optional[ConceptGraphMemory],
    retrieval: Optional[Retrieval],
    task: SyntheticTask,
) -> List[str]:
    """Return observable prompt-leak violations for BMW variants."""
    if variant == "A":
        return []
    prompt = "\n".join(m.get("content", "") for m in messages)
    violations: List[str] = []
    if "[RAW HISTORY]" in prompt:
        violations.append("full raw-history block")
    if memory and retrieval:
        active = set(retrieval.active_ids)
        allowed_raw = {
            memory.concepts[concept_id].source_record_id
            for concept_id in retrieval.raw_fallback_ids
        } if task.exact_detail else set()
        for concept_id, concept in memory.concepts.items():
            if concept_id not in active and concept.content in prompt:
                violations.append("inactive concept %s" % concept_id)
            record_id = concept.source_record_id
            if record_id not in allowed_raw and memory.records[record_id].content in prompt:
                violations.append("raw source record %s" % record_id)
    return violations


def deterministic_response(task: SyntheticTask) -> BackendResponse:
    return BackendResponse(content="%s deterministic-fixture" % task.marker, model_latency_ms=0.0, completion_tokens=0)


def call_minicpm(messages: Sequence[Dict[str, str]], max_tokens: int = 64, temperature: float = 0.1) -> BackendResponse:
    """Call the existing PotatoAgent client and preserve its failure result."""
    try:
        from potato_agent import PotatoAgent
        from potato_agent import MINICPM_API_URL, DEFAULT_MODEL
    except Exception as exc:
        return BackendResponse(error="Could not load existing PotatoAgent client: %s" % exc)
    agent = PotatoAgent(
        goal="CATV3 MiniCPM5-2B backend experiment",
        model_url=MINICPM_API_URL,
        model_name=DEFAULT_MODEL,
    )
    started = time.perf_counter()
    result = agent.call_model(
        list(messages), category="EXECUTION", max_tokens=max_tokens, temperature=temperature
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    error = result.get("error")
    actual_prompt_tokens = result.get("prompt_tokens") or None
    completion_tokens = result.get("completion_tokens") or None
    return BackendResponse(
        content=result.get("content", "") if not error else "",
        actual_prompt_tokens=actual_prompt_tokens if not error else None,
        completion_tokens=completion_tokens if not error else None,
        model_latency_ms=elapsed_ms,
        error=error,
        guard_rejected=bool(error and "2048" in str(error)),
    )


def verify_response(response: BackendResponse, task: SyntheticTask, backend: str) -> str:
    if backend == "minicpm" and (response.error or not response.content):
        return "UNVERIFIED"
    return "PASS" if task.marker.lower() in response.content.lower() else "FAIL"
