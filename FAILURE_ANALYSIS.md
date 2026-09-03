# PotatoClaw Failure Memory, Loop Detection & Confidence Escalation

## 1. Small-Model Failure Modes in Computer-Use Agents

Small language models (3B–4B parameters) exhibit distinct behavioral failure patterns when interacting with computer environments:

### 1. The Blind Retry Loop
When a tool returns an error (such as `FileNotFoundError: config.json` or `ElementNotInteractableException`), small models lack the self-correcting meta-reasoning of frontier 70B+ models. They frequently repeat the exact same command or click with identical arguments 3 to 10 times consecutively, burning tokens and context without making progress.

### 2. The Oscillatory Cycle ($A \to B \to A \to B$)
When alternating between two related tools (e.g., trying a shell command, seeing it fail, switching to a browser lookup, switching back to the shell command), the model gets trapped in an alternating infinite oscillation where state changes in step $A$ are immediately undone in step $B$.

### 3. Syntax & Schema Degradation
Under context pressure, small models frequently drop closing braces, produce trailing commas, wrap keys in single quotes, or hallucinate tool aliases (`browser_navigate` instead of `browser`).

---

## 2. Failure Signature Tracking (Phase 8)

PotatoClaw introduces **Failure Memory** to store and compare failure signatures before any action is executed.

### Failure Signature Formulation
$$\text{Signature} = \text{hash}\Big(\text{node\_id}, \; \text{normalized\_action}, \; \text{error\_snippet}, \; \text{env\_state\_hash}\Big)$$

```python
class FailureSignature:
    node_id: str             # Active graph node
    action: str              # Canonicalized tool call or command
    error_msg: str           # First line / core exception
    env_state_hash: str      # Environment state fingerprint
    diagnosis: Optional[str] # Algorithmic or LLM diagnosis
    attempted_fix: Optional[str] # Strategy applied
```

### Pre-Execution Guard
Before dispatching any tool turn:
1. Compute the proposed action's signature against the active state.
2. If `(node_id, action, state)` matches a recorded failure:
   - **DO NOT EXECUTE.**
   - Intercept the action deterministically.
   - Escalate to diagnosis and local graph replanning.

---

## 3. Deterministic Loop Detection & Circuit Breaker (Phase 9)

PotatoClaw deploys a zero-overhead **Loop Detector**:

```python
class LoopDetector:
    max_identical_repeats = 3
    max_oscillations = 2
```

### 1. Identical Action Repeat Detection
Tracks the last 25 action signatures. If the same `(tool, args)` tuple occurs $\ge 3$ times consecutively:
- The circuit breaker **trips**.
- Tool execution is halted.
- A concise corrective warning is injected into the BWM state:
  `LOOP DETECTED: Action 'browser' repeated 3 times with identical arguments. Circuit breaker tripped. Choose an alternative action.`

### 2. Oscillatory Cycle Detection
Analyzes recent turn signatures for alternating patterns:
$$h_{t-1} = h_{t-3} \quad \land \quad h_{t-2} = h_{t-4} \quad \land \quad h_{t-1} \neq h_{t-2}$$
- When detected, the agent immediately terminates the ping-pong cycle.

---

## 4. Behavioral Confidence & Escalation Matrix (Phase 13)

Rather than relying on poorly calibrated model self-reported probabilities (*"I am 95% confident"*), PotatoClaw monitors **deterministic behavioral signals**:

| Behavioral Signal | Uncertainty Level | Automated System Response |
| :--- | :---: | :--- |
| First attempt, clean state, dependencies complete | **LOW** | Direct fast execution with minimal reasoning tokens ($\le 60$). |
| Tool returns non-zero exit code or error trace | **MEDIUM** | Record failure signature; compile observation error; retry with diagnosis ($\le 120$ tokens). |
| Repeated error or verifier contradiction | **HIGH** | Local graph patch: insert prerequisite or alternative node path. |
| Circuit breaker tripped (3x repeat or oscillation) | **CRITICAL** | Halt turn; inject failure block into context; force alternative tool family or human escalation. |

This eliminates thousands of wasted tokens on repetitive dead-end cycles and ensures 100% deterministic recovery from tool-level faults.
