# PotatoClaw 🥔🦞 — Small-Local-Model Computer Agent & Automation Suite

<p align="center">
  <b>The ultra-low-resource local computer agent and content automation engine designed for potato PCs.</b><br>
  <i>Runs 100% locally on a 4GB GPU (GTX 1650), 6GB RAM, and a 2048-token context budget with Spark-X2.5-4B.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Architecture-PotatoClaw%20V3%20Graph--LLM-brightgreen?style=flat-square" alt="Architecture">
  <img src="https://img.shields.io/badge/Model-Spark--X2.5--4B--Q4__K__M-blue?style=flat-square" alt="Model">
  <img src="https://img.shields.io/badge/Hardware-GTX%201650%20(4GB%20VRAM)-green?style=flat-square" alt="Hardware">
  <img src="https://img.shields.io/badge/PotatoBench-100%25%20PASS%20(10%2F10)-gold?style=flat-square" alt="PotatoBench">
  <img src="https://img.shields.io/badge/Context%20Budget-2048%20Tokens-orange?style=flat-square" alt="Context Budget">
  <img src="https://img.shields.io/badge/Cloud%20Dependencies-ZERO%20(100%25%20Local)-red?style=flat-square" alt="Zero Cloud">
  <img src="https://img.shields.io/badge/License-MIT-purple?style=flat-square" alt="License">
</p>

---

## 💡 The PotatoClaw Research Mission

Most AI computer agents require massive 70B+ cloud models, giant context windows (32k–128k), and heavy vector databases. **PotatoClaw** answers the central research question:

> **"How much apparent agent capability can be recovered through architecture, memory, graph planning, deterministic execution, verification, and selective neural computation when the underlying language model is small?"**

### Core Philosophy: "Rule Zero"
**DO LESS NEURAL COMPUTATION.** Never use an LLM for algorithmic work that zero-overhead code can solve deterministically:
- Task sequencing and dependency readiness $\to$ Deterministic DAG Topological Sort.
- Working memory management and capacity pruning $\to$ Bounded Working Memory (BWM) with utility scoring.
- Observation processing $\to$ Observation Compiler (terminal stdout, browser titles, filesystem summaries).
- Success validation $\to$ Deterministic Verifier (exit codes, file existence, regex, schema validation).
- Infinite loop prevention $\to$ Failure Memory Store & Action Circuit Breaker.

---

## ⚡ Empirical Evaluation: PotatoBench 10-Task Research Suite

Tested on **NVIDIA GeForce GTX 1650 (4GB VRAM)** + **AMD Ryzen 5 5600H (6 Cores)** with `Spark-X2.5-4B-Q4_K_M.gguf` under a hard $\le 2048$ token budget:

| Task Category | Status | Latency | Tokens | Model Calls | Key Mechanism Tested |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **1. Filesystem Operations** | ✅ PASS | 5.92s | 120 | 1 | Deterministic file existence & size check |
| **2. Terminal Operations** | ✅ PASS | 4.94s | 123 | 1 | Exit-code verification & stdout compilation |
| **3. Browser Navigation** | ✅ PASS | 7.43s | 134 | 1 | Level 0 progressive observation (title + URL) |
| **4. Coding Generation** | ✅ PASS | 3.44s | 79 | 1 | Deterministic Python AST syntax validation |
| **5. Debugging & Diagnosis** | ✅ PASS | 3.34s | 105 | 1 | Root-cause traceback parsing & diagnosis |
| **6. Information Extraction** | ✅ PASS | 5.60s | 141 | 1 | Targeted metadata extraction without page dump |
| **7. Multi-Step Workflow** | ✅ PASS | 4.86s | 93 | 1 | 3-step file pipeline (inspect $\to$ write $\to$ verify) |
| **8. Failure Recovery** | ✅ PASS | 6.52s | 150 | 1 | Failure signature memory halts duplicate loop |
| **9. Constraint Retention** | ✅ PASS | 6.72s | 131 | 1 | Protected memory preserves critical safety rules |
| **10. Long-Horizon Torture** | ✅ PASS | 3.52s | 217 | 1 | 8-step execution (>4096 raw tokens compressed) |

- **Overall PotatoBench Success Rate**: **100.0% (10/10 passed)**
- **Average Task Latency**: **5.23s** (down from 56.74s baseline, **>10x speedup**)
- **Average Tokens / Task**: **129.3 tokens**
- **Model Calls per Task**: **1.0 call** (strictly optimal)
- **VRAM Utilization**: **~2,165 MiB steady** (leaving ~1.9 GB VRAM headroom)
- **Core Unit Tests**: **48/48 passed** ([`test_potato_core.py`](file:///c:/Users/user/Downloads/Potatoclaw/scripts/test_potato_core.py))

Full experimental logs and dataset:
- [`BENCHMARK.md`](file:///c:/Users/user/Downloads/Potatoclaw/BENCHMARK.md)
- [`ABLATIONS.md`](file:///c:/Users/user/Downloads/Potatoclaw/ABLATIONS.md)
- [`benchmarks/potatobench/results.json`](file:///c:/Users/user/Downloads/Potatoclaw/benchmarks/potatobench/results.json)
- [`benchmarks/potatobench/results.csv`](file:///c:/Users/user/Downloads/Potatoclaw/benchmarks/potatobench/results.csv)

---

## 🏗️ PotatoClaw V3 Modular Architecture

### 1. 🗺️ Deterministic Task Graph & DAG Scheduler (`scripts/potato_graph.py`)
- Formal `TaskNode` representation with explicit parent-child dependencies.
- Zero-overhead deterministic node readiness formula: $\text{Ready}(v) \iff \forall p \in \text{Parents}(v), \text{status}(p) = \text{COMPLETE}$.
- Local graph retrieval: $G_{\text{local}}(v) = \{v\} \cup \text{Parents}(v) \cup \text{RelevantChildren}(v) \cup \text{Constraints}$.
- Dynamic prerequisite insertion, node replacement, and milestone subgraph compaction.
- *Detailed specification*: [`GRAPH_ARCHITECTURE.md`](file:///c:/Users/user/Downloads/Potatoclaw/GRAPH_ARCHITECTURE.md).

### 2. 🧠 Bounded Working Memory & Hierarchical Tiers (`scripts/potato_bwm.py`)
- Strict character/token budget enforcement ($\le 850$ characters / $\sim 200$ tokens).
- Utility scoring: $\text{Score}(m_i, v) = w_1 \cdot \text{imp} + w_2 \cdot \text{rel}(v) + w_3 \cdot \text{nov} + w_4 \cdot \text{rec} - w_5 \cdot \text{cost}$.
- Non-evictable protected state for user goals, critical safety rules, and altered file paths.
- Three computational tiers: **L0** (immediate transient raw observation), **L1** (active structured BWM), **L2** (durable disk checkpoints).
- *Detailed specification*: [`BWM_ARCHITECTURE.md`](file:///c:/Users/user/Downloads/Potatoclaw/BWM_ARCHITECTURE.md).

### 3. 🔍 Observation Compiler & Context Compiler (`scripts/potato_compiler.py`)
- Compresses noisy raw terminal output, file dumps, and browser DOM into compact structured summaries.
- Hard-budget prompt compiler with priority-based pruning protecting system instructions.

### 4. ⚖️ Deterministic Verifier (`scripts/potato_verifier.py`)
- Eliminates LLM self-questioning and confirmation bias.
- Validates file existence, file size, content regex patterns, process exit codes, and JSON schemas deterministically in $<0.5$ ms.

### 5. 🛡️ Failure Memory, Loop Breaker & Dynamic Tool Router (`scripts/potato_failure_memory.py`)
- Failure signature hashing (`hash(node, action, error)`).
- Identical 3x repeat breaker and $A \to B \to A \to B$ oscillatory cycle detector.
- Dynamic tool routing filtering active schemas to domain-relevant subsets.
- *Detailed specification*: [`FAILURE_ANALYSIS.md`](file:///c:/Users/user/Downloads/Potatoclaw/FAILURE_ANALYSIS.md).

---

## 📱 Connected Automation Engines

### 🥔 Potato AI Agent Chat V3 (Interactive Terminal Assistant)
- **Engine**: Fully connected to **PotatoClaw V3** (`scripts/potato_chat.py`).
- **Features**: Real-time back-and-forth conversation, safe local tool execution (`run_command`, `read_file`, `browser`, `fetch_news`), deterministic verification of tool results, BWM prompt state, and loop circuit breaking.
- **Commands**: `/reset`, `/stats`, `/bwm`, `/tools`, `/news [category]`, `/help`, `/exit`.

### 🐦 X (Twitter) Single-Story News Poster V3
- **Engine**: Powered by **PotatoClaw V3 BWM & Deterministic Verifier** (`scripts/x_news_engine.py`).
- **Features**: Automatically curates breaking stories in Tech, Defence, and Physics. Uses BWM protected constraints to enforce the strict 280-character limit, injects emoji hooks and hashtags, deterministically verifies character count with `t.co` link weighting, and copies post text to clipboard with 1-click browser intent composer.

---

## 🚀 Getting Started

### 1. Prerequisites
- Windows 10/11 (with WSL 2 for `llama-server`) or Linux / macOS.
- NVIDIA GPU with $\ge$ 4GB VRAM (e.g. GTX 1650, GTX 1060, RTX 3050).
- Python 3.8+ installed on system PATH.

### 2. Launch Local Model Server
```powershell
.\scripts\start-spark-potato.ps1
```
*Loads `Spark-X2.5-4B-Q4_K_M.gguf` on `http://127.0.0.1:11435/v1` with 26 GPU offloaded layers and 2048 context.*

---

## 🎮 1-Click Launchers

### 🥔 Potato AI Agent Chat
```cmd
:: Launch interactive chat
potato_chat.bat

:: Or run directly via PowerShell
.\potato_chat.ps1
```

### Master Automation Hub
```cmd
:: Launch Interactive Menu (Agent Chat + X Poster + Benchmarks)
post_all.bat

:: Or run directly via PowerShell
.\post_all.ps1
```

### Direct CLI Commands
```cmd
:: Chat directly with Potato AI
post_all.bat chat

:: Post Tech / Defence / Physics single-story to X
post_all.bat x tech
post_all.bat x defence
post_all.bat x physics
```

### Dedicated Launchers
- **[`potato_chat.bat`](file:///c:/Users/user/Downloads/Potatoclaw/potato_chat.bat)**: Direct interactive Potato AI Agent Chat.
- **[`post_tech_defence_physics_news.bat`](file:///c:/Users/user/Downloads/Potatoclaw/post_tech_defence_physics_news.bat)**: Direct single-story X poster.

---

## 🧪 Testing & Benchmarking

```powershell
# 1. Run Comprehensive V3 Architectural Test Suite (48 Passed, 0 Failed)
& "C:\Program Files\Python38\python.exe" scripts\test_potato_core.py

# 2. Run Full PotatoBench V3 Research Suite (10 Tasks + 8 Ablations)
& "C:\Program Files\Python38\python.exe" scripts\run_benchmarks.py potatobench
```

Detailed reports are generated in:
- [`BENCHMARK.md`](file:///c:/Users/user/Downloads/Potatoclaw/BENCHMARK.md)
- [`ABLATIONS.md`](file:///c:/Users/user/Downloads/Potatoclaw/ABLATIONS.md)
- [`CURRENT_ARCHITECTURE.md`](file:///c:/Users/user/Downloads/Potatoclaw/CURRENT_ARCHITECTURE.md)
- [`GRAPH_ARCHITECTURE.md`](file:///c:/Users/user/Downloads/Potatoclaw/GRAPH_ARCHITECTURE.md)
- [`BWM_ARCHITECTURE.md`](file:///c:/Users/user/Downloads/Potatoclaw/BWM_ARCHITECTURE.md)
- [`FAILURE_ANALYSIS.md`](file:///c:/Users/user/Downloads/Potatoclaw/FAILURE_ANALYSIS.md)

---

## 🙏 Credits & Attribution

PotatoClaw is built upon and inspired by the incredible open-source architecture of **[OpenClaw](https://github.com/openclaw/openclaw)**. 

We extend our sincere gratitude to the OpenClaw maintainers and community for:
- Foundational gateway protocols and multi-platform agent execution patterns
- Comprehensive tool definitions, sandbox boundaries, and session models
- Pioneering open-source autonomous agent architectures that make small-model local experimentation possible.

For upstream OpenClaw documentation and source, visit [https://docs.openclaw.ai](https://docs.openclaw.ai) and [https://github.com/openclaw/openclaw](https://github.com/openclaw/openclaw).

---

## 📄 License
MIT License. Built for the community with ❤️ for potato PC owners.

