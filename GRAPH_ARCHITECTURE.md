# PotatoClaw Deterministic Graph-LLM Planner & DAG Architecture

## 1. Core Architectural Principle: Why a Task Graph?

Small language models (~4B parameters, such as `Spark-X2.5-4B`) fail in long-horizon autonomous tasks primarily due to **reasoning fatigue** and **accumulative error propagation** when forced to act as both high-level planner, sequencer, and low-level actuator on every single turn.

In a traditional reactive agent loop:
$$\text{Action}_t = \text{LLM}(\text{History}_{0..t-1}, \text{Observation}_t)$$
The prompt expands continuously with raw history. The model must repeatedly re-deduce:
1. What was the overarching goal?
2. What steps have already succeeded?
3. Which step must happen next?
4. How do dependencies relate?

In PotatoClaw V3, we decouple:
- **WHAT NEEDS TO HAPPEN** $\to$ Captured explicitly in a **Deterministic Directed Acyclic Graph (DAG)**.
- **WHAT IS READY TO EXECUTE** $\to$ Evaluated deterministically in zero-overhead Python code.
- **WHAT REQUIRES REASONING RIGHT NOW** $\to$ Delegated to the small model for the active node only.

---

## 2. TaskNode Formal Specification

Each node in the task graph represents a concrete, discrete operational unit:

```python
TaskNode:
    id: str                         # Unique alphanumeric identifier (e.g., "inspect_repo")
    description: str                # Human-readable step objective
    dependencies: List[str]         # List of parent node IDs that must be COMPLETE
    status: NodeStatus              # PENDING | READY | RUNNING | BLOCKED | FAILED | COMPLETE | SKIPPED
    tool_family: ToolFamily         # BROWSER | TERMINAL | FILESYSTEM | CODE | SEARCH | MEMORY | NONE
    success_condition: Optional[str]# Verifiable completion rule
    failure_condition: Optional[str]# Known failure indicators
    relevant_memory_ids: List[str]  # Graph-aware memory pointers
    retry_count: int                # Number of execution attempts
    max_retries: int                # Cap before tripping circuit breaker
    priority: int                   # Execution priority (higher executes first among ready nodes)
    confidence: float               # Estimated probability of success (0.0 to 1.0)
    estimated_cost: float           # Relative computational expense
    artifacts: Dict[str, Any]       # Concrete outputs (paths, URLs, extracted tokens)
    result: Optional[str]           # Execution summary or output
    error: Optional[str]            # Diagnostic error string if failed
```

---

## 3. Deterministic Node Readiness & Scheduling

### Rule Zero Applied to Scheduling
We never ask the LLM *"Which step should I execute next?"* when parent-child dependencies provide a mathematically unambiguous answer.

### Mathematical Formulation
A node $v \in V$ is defined as **READY** if and only if:
$$\text{Ready}(v) \iff \Big(\text{status}(v) = \text{PENDING}\Big) \;\land\; \Big(\forall p \in \text{Parents}(v), \; \text{status}(p) = \text{COMPLETE}\Big)$$

### Scheduling Algorithm
```python
def select_next_node(graph: TaskGraph) -> Optional[TaskNode]:
    ready_nodes = [v for v in graph.nodes.values() if graph.is_ready(v.id)]
    if not ready_nodes:
        return None
    # Sort deterministically by priority descending, then estimated cost ascending
    return max(ready_nodes, key=lambda v: (v.priority, -v.estimated_cost))
```

This scheduling takes $<0.1$ milliseconds on CPU, avoiding 5–10 seconds of LLM inference latency and 150 prompt tokens per scheduling decision.

---

## 4. Local Graph Retrieval: $G_{\text{local}}(v)$

Small local models experience severe attention degradation when injected with large graph structures. Injecting a 25-node graph into a 2048-token context wastes over 500 tokens on irrelevant future or past steps.

PotatoClaw restricts context to the **Local Neighborhood**:
$$G_{\text{local}}(v) = \{v\} \cup \text{Parents}(v) \cup \text{RelevantChildren}(v) \cup \text{CriticalConstraints}$$

### Local Prompt Representation
```
[LOCAL TASK CONTEXT]
GOAL: Build and verify software patch
CURRENT STEP [write_patch]: Modify source code to resolve null-pointer crash
TOOL FAMILY: filesystem
SUCCESS CONDITION: parser.py contains non-null check
PREREQUISITES: inspect_code(COMPLETE)
CONSTRAINTS: Do not modify public API signatures; Preserve backwards compatibility
```

Everything else (nodes completed 10 steps ago, distant branch nodes, future unready steps) is pruned from the prompt.

---

## 5. Event-Driven Local Graph Patching & Replanning

### The Anti-Replanning Principle
The agent does **NOT** replan after every successful action. Replanning is strictly event-driven, triggered only by:
1. Verifier contradiction or failure
2. Repeated tool execution errors
3. Discovered missing prerequisite
4. Critical path blockages

### Local Patching vs. Global Regeneration
Instead of asking the LLM to hallucinate a new 20-node graph from scratch, PotatoClaw applies **Local Graph Mutations**:

#### 1. Prerequisite Insertion
When action $B$ discovers an unexpected dependency $X$ (e.g., `pytest` command not found $\to$ must install dependencies first):
$$\text{Existing: } A \longrightarrow B \longrightarrow C$$
$$\text{Local Patch: } A \longrightarrow X \longrightarrow B \longrightarrow C$$
Node $B$ is reset to `PENDING` with dependency $[X]$. Future nodes ($C$) remain untouched.

#### 2. Alternative Node Replacement
When node $B$ fails irreversibly:
$$\text{Existing: } A \longrightarrow B_{\text{failed}} \longrightarrow C$$
$$\text{Local Patch: } B \to \text{SKIPPED}; \quad A \longrightarrow B'_{\text{alternative}} \longrightarrow C$$

---

## 6. Subgraph Compaction

Completed graph regions can consume memory and clutter provenance logs. Once a linear sequence or subgraph $S = \{v_1, v_2, \dots, v_k\}$ is permanently complete:
$$v_1 \longrightarrow v_2 \longrightarrow v_3$$
PotatoClaw compacts $S$ into a unified milestone summary node:
$$[\text{MILESTONE COMPLETE: } \text{Environment setup, dependencies installed, baseline verified}]$$

- In-memory graph size remains bounded ($O(1)$ active working set).
- Full detailed logs are retained on disk in `potato_checkpoint.json` for auditing.
