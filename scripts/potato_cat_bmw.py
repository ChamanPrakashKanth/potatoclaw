#!/usr/bin/env python3
"""Small, deterministic CATV3-style concept graph + BMW memory prototype.

This module deliberately has no model, embedding, tokenizer, or persistence
dependency.  It turns observations into compact concepts, keeps raw records
behind source pointers, and serializes only a bounded active set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict, deque
import math
import re
import time
from typing import Dict, Iterable, List, Optional, Set, Tuple


_WORD_RE = re.compile(r"[A-Za-z0-9_./:-]+")


def _terms(text: str) -> Set[str]:
    return {w.lower() for w in _WORD_RE.findall(text) if len(w) > 1}


@dataclass
class RawRecord:
    record_id: str
    text: str
    token_count: int
    created_at: float


@dataclass
class ConceptNode:
    concept_id: str
    content: str
    importance: float = 0.5
    decay_rate: float = 0.01
    relevance: float = 0.0
    previous_utility: float = 0.0
    relations: Set[str] = field(default_factory=set)
    source_ids: List[str] = field(default_factory=list)
    last_update: float = 0.0
    access_count: int = 0
    protected: bool = False
    terms: Set[str] = field(default_factory=set)

    def decay(self, now: float) -> None:
        dt = max(0.0, now - self.last_update)
        self.importance *= math.exp(-self.decay_rate * dt)
        self.previous_utility *= math.exp(-self.decay_rate * dt)
        self.last_update = now

    def utility(self) -> float:
        return 0.45 * self.importance + 0.30 * self.relevance + 0.25 * self.previous_utility


class ConceptGraphMemory:
    """Incremental concept graph with BMW-style bounded prompt serialization."""

    def __init__(self, active_limit: int = 32, now=None):
        self.active_limit = active_limit
        self.nodes: Dict[str, ConceptNode] = {}
        self.raw_records: Dict[str, RawRecord] = {}
        self.term_index: Dict[str, Set[str]] = defaultdict(set)
        self.protected_ids: Set[str] = set()
        self._now = now or time.time
        self._counter = 0
        self.last_selection_scanned = 0
        self.last_selection_candidates = 0
        self.last_fallback = False
        self._last_relevant: Set[str] = set()

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)

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
        """Add one compact observation; does not rebuild the graph."""
        now = self._now()
        self._counter += 1
        raw_id = f"raw_{self._counter}"
        self.raw_records[raw_id] = RawRecord(raw_id, content, self.estimate_tokens(content), now)
        cid = concept_id or f"concept_{self._counter}"
        node = self.nodes.get(cid)
        if node is None:
            node = ConceptNode(cid, content.strip()[:240], importance, decay_rate,
                               0.0, 0.0, set(relations), [raw_id], now,
                               protected=protected, terms=_terms(content))
            self.nodes[cid] = node
            if protected:
                self.protected_ids.add(cid)
            for term in node.terms:
                self.term_index[term].add(cid)
        else:
            node.decay(now)
            node.content = content.strip()[:240]
            node.importance = max(node.importance, min(1.0, importance))
            node.protected = node.protected or protected
            if node.protected:
                self.protected_ids.add(cid)
            node.relations.update(relations)
            node.source_ids.append(raw_id)
        for related in relations:
            if related in self.nodes:
                self.nodes[related].relations.add(cid)
        return cid

    def add_relation(self, left: str, right: str) -> None:
        if left in self.nodes and right in self.nodes:
            self.nodes[left].relations.add(right)
            self.nodes[right].relations.add(left)

    def reinforce(self, concept_ids: Iterable[str], success: bool = True) -> None:
        now = self._now()
        for cid in concept_ids:
            node = self.nodes.get(cid)
            if not node:
                continue
            node.decay(now)
            node.access_count += 1
            if success:
                node.previous_utility = min(1.0, node.previous_utility + 0.20)
                node.importance = min(1.0, node.importance + 0.10)

    def select(self, query: str, limit: Optional[int] = None) -> List[ConceptNode]:
        limit = limit or self.active_limit
        q = _terms(query)
        candidates: Set[str] = set()
        for term in q:
            candidates.update(self.term_index.get(term, set()))
        # Protected concepts remain eligible even when no query term matches.
        candidates.update(self.protected_ids)
        # Relevance updates are incremental: clear only concepts that were
        # relevant in the previous query and score the new indexed candidates.
        relevance_targets = self._last_relevant | candidates
        for cid in relevance_targets:
            node = self.nodes.get(cid)
            if node:
                node.relevance = len(q & node.terms) / max(1, len(q))
        self._last_relevant = set(candidates)
        self.last_selection_candidates = len(candidates)
        self.last_selection_scanned = len(relevance_targets)
        self.last_fallback = not bool(candidates)
        if not candidates:
            candidates = set(self.nodes)
            self.last_selection_scanned = len(candidates)
            self.last_fallback = True

        now = self._now()
        ranked = []
        for cid in candidates:
            node = self.nodes[cid]
            node.decay(now)
            graph_bonus = 0.0
            if node.relevance > 0:
                graph_bonus = 0.05 * sum(self.nodes[r].relevance for r in node.relations if r in self.nodes)
            score = node.utility() + graph_bonus + (1.0 if node.protected else 0.0)
            ranked.append((score, cid, node))
        ranked.sort(key=lambda x: (-x[0], x[1]))
        selected = [row[2] for row in ranked[:limit]]
        selected_ids = {n.concept_id for n in selected}
        # One-hop graph traversal for related concepts, still bounded by limit.
        related = []
        for node in selected:
            for rid in node.relations:
                if rid in self.nodes and rid not in selected_ids:
                    related.append(self.nodes[rid])
        related.sort(key=lambda n: (-n.utility(), n.concept_id))
        for node in related:
            if len(selected) >= limit:
                break
            selected.append(node)
        self.reinforce((n.concept_id for n in selected), success=False)
        return selected

    def serialize(self, query: str, limit: Optional[int] = None, include_raw: bool = False) -> Tuple[str, Dict[str, object]]:
        selected = self.select(query, limit)
        lines = ["[ACTIVE CONCEPT GRAPH]"]
        for node in selected:
            rel = ",".join(sorted(node.relations)[:4]) or "-"
            lines.append(f"{node.concept_id}|{node.content}|rel={rel}|u={node.utility():.2f}")
        if include_raw and selected:
            # Explicit exact-detail fallback only; normal serialization never uses this.
            raw = self.raw_records[selected[0].source_ids[-1]]
            lines.append(f"[RAW DETAIL {raw.record_id}] {raw.text}")
        text = "\n".join(lines)
        return text, {
            "active_nodes": len(selected),
            "prompt_tokens": self.estimate_tokens(text),
            "raw_fallback": bool(include_raw and selected),
            "selection_candidates": self.last_selection_candidates,
            "selection_scanned": self.last_selection_scanned,
            "selection_fallback_scan": self.last_fallback,
        }

    def stats(self) -> Dict[str, int]:
        return {
            "raw_records": len(self.raw_records),
            "raw_tokens": sum(r.token_count for r in self.raw_records.values()),
            "concept_nodes": len(self.nodes),
        }
