#!/usr/bin/env python3
"""
PotatoClaw Deterministic Task Graph & DAG Scheduler
Implements lightweight graph-based planning, deterministic node readiness,
local graph neighborhood retrieval (G_local), event-driven local patching,
and subgraph compaction for small local models.
"""

from enum import Enum
from typing import Dict, List, Set, Optional, Any
import json
import time

class NodeStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    COMPLETE = "COMPLETE"
    SKIPPED = "SKIPPED"

class ToolFamily(str, Enum):
    BROWSER = "browser"
    TERMINAL = "terminal"
    FILESYSTEM = "filesystem"
    CODE = "code"
    SEARCH = "search"
    MEMORY = "memory"
    NONE = "none"

class TaskNode:
    def __init__(
        self,
        node_id: str,
        description: str,
        dependencies: Optional[List[str]] = None,
        tool_family: str = ToolFamily.NONE.value,
        success_condition: Optional[str] = None,
        failure_condition: Optional[str] = None,
        relevant_memory_ids: Optional[List[str]] = None,
        priority: int = 1,
        max_retries: int = 2,
        estimated_cost: float = 1.0,
    ):
        self.id = node_id
        self.description = description.strip()
        self.dependencies = list(dependencies or [])
        self.status = NodeStatus.PENDING
        self.tool_family = tool_family
        self.success_condition = success_condition
        self.failure_condition = failure_condition
        self.relevant_memory_ids = list(relevant_memory_ids or [])
        self.retry_count = 0
        self.max_retries = max_retries
        self.priority = priority
        self.confidence = 1.0
        self.estimated_cost = estimated_cost
        self.artifacts: Dict[str, Any] = {}
        self.result: Optional[str] = None
        self.error: Optional[str] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "tool_family": self.tool_family,
            "success_condition": self.success_condition,
            "failure_condition": self.failure_condition,
            "relevant_memory_ids": self.relevant_memory_ids,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "priority": self.priority,
            "confidence": round(self.confidence, 3),
            "estimated_cost": self.estimated_cost,
            "artifacts": self.artifacts,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskNode":
        node = cls(
            node_id=data["id"],
            description=data["description"],
            dependencies=data.get("dependencies", []),
            tool_family=data.get("tool_family", ToolFamily.NONE.value),
            success_condition=data.get("success_condition"),
            failure_condition=data.get("failure_condition"),
            relevant_memory_ids=data.get("relevant_memory_ids", []),
            priority=data.get("priority", 1),
            max_retries=data.get("max_retries", 2),
            estimated_cost=data.get("estimated_cost", 1.0),
        )
        node.status = NodeStatus(data.get("status", NodeStatus.PENDING.value))
        node.retry_count = data.get("retry_count", 0)
        node.confidence = data.get("confidence", 1.0)
        node.artifacts = data.get("artifacts", {})
        node.result = data.get("result")
        node.error = data.get("error")
        return node


class TaskGraph:
    def __init__(self, goal: str = "", critical_constraints: Optional[List[str]] = None):
        self.goal = goal.strip()
        self.critical_constraints = list(critical_constraints or [])
        self.nodes: Dict[str, TaskNode] = {}
        self.creation_time = time.time()
        self.last_modified_time = self.creation_time

    def add_node(self, node: TaskNode) -> None:
        if node.id in self.nodes:
            raise ValueError(f"Node '{node.id}' already exists in task graph.")
        self.nodes[node.id] = node
        self.last_modified_time = time.time()

    def get_node(self, node_id: str) -> Optional[TaskNode]:
        return self.nodes.get(node_id)

    def get_parents(self, node_id: str) -> List[TaskNode]:
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[dep] for dep in node.dependencies if dep in self.nodes]

    def get_children(self, node_id: str) -> List[TaskNode]:
        children = []
        for n in self.nodes.values():
            if node_id in n.dependencies:
                children.append(n)
        return children

    # ------------------------------------------------------------
    # Deterministic Readiness & Scheduling
    # ------------------------------------------------------------
    def is_ready(self, node_id: str) -> bool:
        """
        Ready(v) = status(v) == PENDING and all(parent.status == COMPLETE for parent in dependencies(v))
        Never uses an LLM to decide readiness.
        """
        node = self.nodes.get(node_id)
        if not node:
            return False
        if node.status != NodeStatus.PENDING:
            return False
        for dep_id in node.dependencies:
            dep_node = self.nodes.get(dep_id)
            if not dep_node or dep_node.status != NodeStatus.COMPLETE:
                return False
        return True

    def update_readiness(self) -> List[TaskNode]:
        """Scans pending nodes and promotes them to READY if dependencies are satisfied."""
        ready_nodes = []
        for node in self.nodes.values():
            if node.status == NodeStatus.PENDING and self.is_ready(node.id):
                node.status = NodeStatus.READY
                ready_nodes.append(node)
        return ready_nodes

    def select_next_node(self) -> Optional[TaskNode]:
        """
        Deterministic node selection: selects highest priority ready node.
        If priority ties, select the one with earliest creation/lowest cost.
        """
        self.update_readiness()
        ready_nodes = [n for n in self.nodes.values() if n.status == NodeStatus.READY]
        if not ready_nodes:
            return None
        # Sort by priority descending, then estimated cost ascending
        ready_nodes.sort(key=lambda x: (-x.priority, x.estimated_cost))
        return ready_nodes[0]

    def is_finished(self) -> bool:
        """Returns true if all nodes are in terminal state (COMPLETE, FAILED, or SKIPPED)."""
        if not self.nodes:
            return False
        terminal = {NodeStatus.COMPLETE, NodeStatus.FAILED, NodeStatus.SKIPPED}
        return all(n.status in terminal for n in self.nodes.values())

    def is_successful(self) -> bool:
        if not self.nodes:
            return False
        # True if at least one complete and none failed without alternative
        has_complete = any(n.status == NodeStatus.COMPLETE for n in self.nodes.values())
        has_failed = any(n.status == NodeStatus.FAILED for n in self.nodes.values())
        return has_complete and not has_failed

    # ------------------------------------------------------------
    # Local Graph Retrieval: G_local(v)
    # ------------------------------------------------------------
    def get_local_neighborhood(self, node_id: str) -> Dict[str, Any]:
        """
        G_local(v) = {v} U Parents(v) U RelevantChildren(v) U CriticalConstraints
        Avoids serializing 50 nodes into the small model context.
        """
        node = self.nodes.get(node_id)
        if not node:
            return {}

        parents = self.get_parents(node_id)
        children = self.get_children(node_id)

        # Compact parent info
        parent_summaries = [
            {"id": p.id, "desc": p.description, "status": p.status.value, "result": p.result}
            for p in parents
        ]
        # Compact child info
        child_summaries = [
            {"id": c.id, "desc": c.description, "status": c.status.value}
            for c in children
        ]

        return {
            "current_node": {
                "id": node.id,
                "description": node.description,
                "tool_family": node.tool_family,
                "success_condition": node.success_condition,
                "retry_count": node.retry_count,
            },
            "parents": parent_summaries,
            "children": child_summaries,
            "critical_constraints": self.critical_constraints,
            "goal": self.goal,
        }

    def format_local_prompt_block(self, node_id: str) -> str:
        """Constructs an ultra-compact string block representing G_local(v)."""
        local = self.get_local_neighborhood(node_id)
        if not local:
            return ""

        cur = local["current_node"]
        lines = [
            "[LOCAL TASK CONTEXT]",
            f"GOAL: {local['goal']}",
            f"CURRENT STEP [{cur['id']}]: {cur['description']}",
            f"TOOL FAMILY: {cur['tool_family']}",
        ]
        if cur.get("success_condition"):
            lines.append(f"SUCCESS CONDITION: {cur['success_condition']}")

        if local["parents"]:
            completed_str = " -> ".join(
                f"{p['id']}({p['status']})" for p in local["parents"]
            )
            lines.append(f"PREREQUISITES: {completed_str}")

        if local["critical_constraints"]:
            lines.append("CONSTRAINTS: " + "; ".join(local["critical_constraints"]))

        return "\n".join(lines)

    # ------------------------------------------------------------
    # Event-Driven Local Graph Patching
    # ------------------------------------------------------------
    def patch_insert_prerequisite(self, target_id: str, new_node: TaskNode) -> None:
        """
        Inserts new_node as an immediate prerequisite before target_id:
        A -> target becomes A -> new_node -> target.
        """
        target = self.nodes.get(target_id)
        if not target:
            raise ValueError(f"Target node '{target_id}' not found.")

        # Transfer target's current dependencies to new_node
        new_node.dependencies = list(target.dependencies)
        self.add_node(new_node)

        # Point target's dependencies to new_node
        target.dependencies = [new_node.id]
        target.status = NodeStatus.PENDING
        self.last_modified_time = time.time()

    def patch_replace_node(self, failed_id: str, alternative_node: TaskNode) -> None:
        """
        Replaces failed_id with an alternative path without regenerating the whole graph.
        """
        failed = self.nodes.get(failed_id)
        if not failed:
            raise ValueError(f"Failed node '{failed_id}' not found.")

        alternative_node.dependencies = list(failed.dependencies)
        self.add_node(alternative_node)

        # Re-link all children of failed node to depend on alternative_node
        for child in self.get_children(failed_id):
            child.dependencies = [
                alternative_node.id if dep == failed_id else dep
                for dep in child.dependencies
            ]

        failed.status = NodeStatus.SKIPPED
        self.last_modified_time = time.time()

    # ------------------------------------------------------------
    # Subgraph Compaction
    # ------------------------------------------------------------
    def compact_completed_subgraph(self, completed_ids: List[str], summary_id: str, summary_desc: str) -> None:
        """
        Compacts multiple successfully completed sequential nodes into a single summary node.
        Preserves dependency connections for future pending nodes.
        """
        for cid in completed_ids:
            node = self.nodes.get(cid)
            if not node or node.status != NodeStatus.COMPLETE:
                return  # Only compact fully completed sets

        combined_results = [
            f"{self.nodes[cid].id}: {self.nodes[cid].result or 'done'}"
            for cid in completed_ids
        ]

        # External dependencies coming into the subgraph
        external_deps = set()
        for cid in completed_ids:
            for dep in self.nodes[cid].dependencies:
                if dep not in completed_ids:
                    external_deps.add(dep)

        summary_node = TaskNode(
            node_id=summary_id,
            description=summary_desc,
            dependencies=list(external_deps),
            tool_family=ToolFamily.NONE.value,
        )
        summary_node.status = NodeStatus.COMPLETE
        summary_node.result = " | ".join(combined_results)

        self.nodes[summary_id] = summary_node

        # Reroute external children to depend on summary_id
        for n in self.nodes.values():
            if n.id not in completed_ids and n.id != summary_id:
                new_deps = []
                for dep in n.dependencies:
                    if dep in completed_ids:
                        if summary_id not in new_deps:
                            new_deps.append(summary_id)
                    else:
                        new_deps.append(dep)
                n.dependencies = new_deps

        # Remove compacted nodes from active runtime dictionary
        for cid in completed_ids:
            del self.nodes[cid]

        self.last_modified_time = time.time()

    # ------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "critical_constraints": self.critical_constraints,
            "creation_time": self.creation_time,
            "last_modified_time": self.last_modified_time,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskGraph":
        graph = cls(
            goal=data.get("goal", ""),
            critical_constraints=data.get("critical_constraints", []),
        )
        graph.creation_time = data.get("creation_time", time.time())
        graph.last_modified_time = data.get("last_modified_time", time.time())
        for nid, ndata in data.get("nodes", {}).items():
            graph.nodes[nid] = TaskNode.from_dict(ndata)
        return graph

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
