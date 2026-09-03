#!/usr/bin/env python3
"""
PotatoClaw Bounded Working Memory (BWM) & Hierarchical Memory Architecture
Implements selective retention, mathematical memory scoring, graph-aware retrieval,
protected state preservation, and hierarchical tiers (L0, L1, L2).
"""

from typing import Dict, List, Optional, Any, Set
import time
import json
import re

class MemoryItem:
    def __init__(
        self,
        memory_id: str,
        content: str,
        source: str = "agent",
        importance: float = 0.5,
        goal_relevance: float = 0.5,
        node_relevance: Optional[Dict[str, float]] = None,
        novelty: float = 1.0,
        protected: bool = False,
        token_cost: Optional[int] = None,
    ):
        self.id = memory_id
        self.content = content.strip()
        self.source = source
        self.timestamp = time.time()
        self.importance = max(0.0, min(1.0, importance))
        self.goal_relevance = max(0.0, min(1.0, goal_relevance))
        self.node_relevance = dict(node_relevance or {})
        self.novelty = max(0.0, min(1.0, novelty))
        self.protected = protected
        self.access_count = 0
        self.last_access = self.timestamp
        self.token_cost = token_cost if token_cost is not None else max(1, len(self.content) // 4)

    def touch(self) -> None:
        self.access_count += 1
        self.last_access = time.time()

    def score(
        self,
        current_node_id: Optional[str] = None,
        w_imp: float = 0.30,
        w_rel: float = 0.35,
        w_nov: float = 0.15,
        w_rec: float = 0.15,
        w_cost: float = 0.05,
    ) -> float:
        """
        Computes composite utility score.
        Score = w1*Importance + w2*Relevance(v) + w3*Novelty + w4*Recency - w5*TokenCost
        """
        # Node-specific relevance if available, otherwise fallback to goal relevance
        rel = self.node_relevance.get(current_node_id, self.goal_relevance) if current_node_id else self.goal_relevance

        # Recency decay: half-life of 300 seconds
        age_sec = max(0.0, time.time() - self.last_access)
        recency = 0.5 ** (age_sec / 300.0)

        # Normalized token cost penalty (assumes max item ~100 tokens)
        norm_cost = min(1.0, self.token_cost / 100.0)

        total = (
            w_imp * self.importance
            + w_rel * rel
            + w_nov * self.novelty
            + w_rec * recency
            - w_cost * norm_cost
        )
        return total

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "timestamp": self.timestamp,
            "importance": round(self.importance, 3),
            "goal_relevance": round(self.goal_relevance, 3),
            "node_relevance": self.node_relevance,
            "novelty": round(self.novelty, 3),
            "protected": self.protected,
            "access_count": self.access_count,
            "last_access": self.last_access,
            "token_cost": self.token_cost,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        item = cls(
            memory_id=data["id"],
            content=data["content"],
            source=data.get("source", "agent"),
            importance=data.get("importance", 0.5),
            goal_relevance=data.get("goal_relevance", 0.5),
            node_relevance=data.get("node_relevance", {}),
            novelty=data.get("novelty", 1.0),
            protected=data.get("protected", False),
            token_cost=data.get("token_cost"),
        )
        item.timestamp = data.get("timestamp", time.time())
        item.access_count = data.get("access_count", 0)
        item.last_access = data.get("last_access", time.time())
        return item


class BoundedWorkingMemory:
    """
    L1 Working Memory with strict active-state budgeting and protected state.
    """
    def __init__(self, max_total_chars: int = 850, max_items: int = 8):
        self.max_total_chars = max_total_chars
        self.max_items = max_items
        self.items: Dict[str, MemoryItem] = {}
        self.protected_keys: Set[str] = set()

    def add_item(self, item: MemoryItem) -> None:
        if item.protected:
            self.protected_keys.add(item.id)
        self.items[item.id] = item
        self._enforce_budget()

    def add_fact(self, content: str, importance: float = 0.5, current_node_id: Optional[str] = None, protected: bool = False) -> str:
        clean = content.strip()
        # Avoid exact duplicate content
        for item in self.items.values():
            if item.content == clean:
                item.touch()
                return item.id

        item_id = f"fact_{int(time.time()*1000)%1000000}_{len(self.items)}"
        node_rel = {current_node_id: 0.9} if current_node_id else {}
        item = MemoryItem(
            memory_id=item_id,
            content=clean,
            importance=importance,
            node_relevance=node_rel,
            protected=protected,
        )
        self.add_item(item)
        return item_id

    def add_protected_fact(self, content: str, importance: float = 1.0) -> str:
        return self.add_fact(content, importance=importance, protected=True)

    def _enforce_budget(self) -> None:
        """Evicts lowest scoring non-protected items until count and character budgets are satisfied."""
        if len(self.items) <= self.max_items and sum(len(i.content) for i in self.items.values()) <= self.max_total_chars:
            return

        # Sort non-protected items by composite score ascending
        non_protected = [i for i in self.items.values() if not i.protected]
        non_protected.sort(key=lambda x: x.score())

        while (len(self.items) > self.max_items or sum(len(i.content) for i in self.items.values()) > self.max_total_chars) and non_protected:
            evict = non_protected.pop(0)
            if evict.id in self.items:
                del self.items[evict.id]

    # ------------------------------------------------------------
    # Graph-Aware Retrieval
    # ------------------------------------------------------------
    def retrieve_for_node(self, node_id: str, limit: int = 5) -> List[MemoryItem]:
        """
        Memory(v) = TopK(GoalRelevance + NodeRelevance(v) + DependencyRelevance)
        Always includes protected items, then highest scoring non-protected items for node v.
        """
        protected_items = [i for i in self.items.values() if i.protected]
        non_protected = [i for i in self.items.values() if not i.protected]

        # Score relative to current node
        scored = [(item.score(current_node_id=node_id), item) for item in non_protected]
        scored.sort(key=lambda x: x[0], reverse=True)

        selected = list(protected_items)
        for _, item in scored:
            if len(selected) >= limit:
                break
            if item not in selected:
                selected.append(item)
                item.touch()

        return selected

    def format_prompt_block(self, current_node_id: Optional[str] = None) -> str:
        """Renders the bounded working memory block for prompt injection."""
        items = self.retrieve_for_node(current_node_id) if current_node_id else list(self.items.values())
        if not items:
            return ""

        lines = ["[BOUNDED WORKING MEMORY]"]
        for item in items:
            prefix = "[CRITICAL] " if item.protected else "- "
            lines.append(f"{prefix}{item.content}")

        output = "\n".join(lines)
        if len(output) > self.max_total_chars:
            return output[:self.max_total_chars] + "\n[...]"
        return output

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_total_chars": self.max_total_chars,
            "max_items": self.max_items,
            "items": {mid: m.to_dict() for mid, m in self.items.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BoundedWorkingMemory":
        bwm = cls(
            max_total_chars=data.get("max_total_chars", 850),
            max_items=data.get("max_items", 8),
        )
        for mid, mdata in data.get("items", {}).items():
            bwm.items[mid] = MemoryItem.from_dict(mdata)
            if bwm.items[mid].protected:
                bwm.protected_keys.add(mid)
        return bwm


class HierarchicalMemory:
    """
    Three-tier memory hierarchy:
    L0: Immediate context (last raw action/observation)
    L1: BWM (active bounded working memory block)
    L2: Persistent semantic state (durable facts, artifacts, decisions)
    """
    def __init__(self, l1_budget_chars: int = 850):
        self.l0_immediate: Optional[Dict[str, Any]] = None
        self.l1_bwm = BoundedWorkingMemory(max_total_chars=l1_budget_chars)
        self.l2_persistent: Dict[str, Any] = {
            "artifacts": {},
            "decisions": [],
            "environment": {},
            "milestones": [],
        }

    def record_l0(self, action: str, raw_observation: str, tool_name: str) -> None:
        """Stores immediate raw turn output."""
        self.l0_immediate = {
            "action": action,
            "observation": raw_observation,
            "tool_name": tool_name,
            "timestamp": time.time(),
        }

    def promote_to_l1(self, fact: str, importance: float = 0.5, current_node_id: Optional[str] = None, protected: bool = False) -> str:
        """Promotes extracted information to BWM."""
        return self.l1_bwm.add_fact(fact, importance=importance, current_node_id=current_node_id, protected=protected)

    def store_l2_artifact(self, name: str, value: Any) -> None:
        """Stores a persistent artifact (e.g. created file path, extracted dataset)."""
        self.l2_persistent["artifacts"][name] = value

    def record_l2_decision(self, decision: str) -> None:
        """Records a durable milestone decision."""
        self.l2_persistent["decisions"].append({
            "decision": decision,
            "timestamp": time.time(),
        })

    def get_l2_summary(self) -> str:
        """Returns compact summary of persistent L2 state."""
        parts = []
        if self.l2_persistent["artifacts"]:
            art_str = ", ".join(f"{k}={v}" for k, v in list(self.l2_persistent["artifacts"].items())[:4])
            parts.append(f"Artifacts: {art_str}")
        if self.l2_persistent["decisions"]:
            recent_dec = self.l2_persistent["decisions"][-1]["decision"]
            parts.append(f"Last Decision: {recent_dec}")
        return " | ".join(parts)
