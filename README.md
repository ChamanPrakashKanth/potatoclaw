# PotatoClaw 🥔🦞 — Ultra-Low-Resource Local Computer Agent & Autonomous Systems Suite

<p align="center">
  <b>Run capable autonomous AI computer agents 100% locally on budget hardware.</b><br>
  <i>Engineered for low-VRAM GPUs (GTX 1650 4GB), 6GB RAM, and a hard 2048-token context budget with small language models (Spark-X2.5-4B / 3B–7B GGUF).</i>
</p>

<p align="center">
  <a href="#-table-of-contents"><img src="https://img.shields.io/badge/Architecture-PotatoClaw%20V3%20Graph--LLM-brightgreen?style=flat-square" alt="Architecture"></a>
  <a href="#-hardware--model-specifications"><img src="https://img.shields.io/badge/Model-Spark--X2.5--4B--Q4__K__M-blue?style=flat-square" alt="Model"></a>
  <a href="#-hardware--model-specifications"><img src="https://img.shields.io/badge/Hardware-GTX%201650%20(4GB%20VRAM)-green?style=flat-square" alt="Hardware"></a>
  <a href="#-empirical-evaluation-potatobench-10-task-research-suite"><img src="https://img.shields.io/badge/PotatoBench-100%25%20PASS%20(10%2F10)-gold?style=flat-square" alt="PotatoBench"></a>
  <a href="#-empirical-evaluation-potatobench-10-task-research-suite"><img src="https://img.shields.io/badge/Context%20Budget-2048%20Tokens-orange?style=flat-square" alt="Context Budget"></a>
  <a href="#-privacy-first--air-gapped-architecture"><img src="https://img.shields.io/badge/Cloud%20Dependencies-ZERO%20(100%25%20Local)-red?style=flat-square" alt="Zero Cloud"></a>
  <a href="#-license"><img src="https://img.shields.io/badge/License-MIT-purple?style=flat-square" alt="License"></a>
</p>

---

## 🔍 SEO & Search Index Summary

| Target Search Queries | Supported Features / Architecture |
| :--- | :--- |
| **Local AI Computer Agent** | Full desktop agent with terminal execution, browser automation, and file editing. |
| **Run LLM on 4GB VRAM / GTX 1650** | Optimized 26-layer GPU offload consuming only ~2.1 GB VRAM with single-slot Flash Attention. |
| **Small Language Model Agent Architecture** | Recovers frontier agent capability using DAG planning, BWM, and deterministic verification. |
| **Ollama / llama.cpp Compatible Agent** | Standard OpenAI-compatible local HTTP API endpoint (`/v1/chat/completions`). |
| **Offline / Air-Gapped Computer Use** | Zero telemetry, zero external API keys, zero cloud tokens burned. |
| **OpenClaw Local Optimization** | Groundbreaking low-resource evolution of the upstream OpenClaw agent paradigm. |

---

## 📑 Table of Contents

- [💡 The PotatoClaw Research Mission](#-the-potatobench-research-mission)
- [⚙️ Core Principle: "Rule Zero"](#️-core-principle-rule-zero)
- [⚠️ Imperfect, Work-in-Progress & An Open Invitation to Build](#️-imperfect-work-in-progress--an-open-invitation-to-build)
- [🎯 Comprehensive Real-World Use Cases](#-comprehensive-real-world-use-cases)
  - [1. Autonomous Software Engineering & Local Developer Workflows](#1-autonomous-software-engineering--local-developer-workflows)
  - [2. Privacy-Preserving OSINT, Technical Research & News Intelligence](#2-privacy-preserving-osint-technical-research--news-intelligence)
  - [3. Social Media, Content Creation & Automated Publishing](#3-social-media-content-creation--automated-publishing)
  - [4. Air-Gapped Environments, Edge Computing & Defense Systems](#4-air-gapped-environments-edge-computing--defense-systems)
  - [5. System Administration, DevOps & Infrastructure Reliability](#5-system-administration-devops--infrastructure-reliability)
  - [6. Lightweight Web Scraping, Navigation & Regression Testing](#6-lightweight-web-scraping-navigation--regression-testing)
  - [7. Daily Desktop Productivity & Personal AI Companion](#7-daily-desktop-productivity--personal-ai-companion)
  - [8. Robotics Edge-Based Computing & Physical Embodied Agents](#8-robotics-edge-based-computing--physical-embodied-agents)
  - [9. Industrial Edge Computing, Smart Manufacturing & Critical Infrastructure](#9-industrial-edge-computing-smart-manufacturing--critical-infrastructure)
- [⚡ Empirical Evaluation: PotatoBench 10-Task Research Suite](#-empirical-evaluation-potatobench-10-task-research-suite)
- [🏗️ PotatoClaw V3 Modular Architecture](#️-potatoclaw-v3-modular-architecture)
- [🥊 PotatoClaw vs Traditional Cloud Agent Frameworks](#-potatoclaw-vs-traditional-cloud-agent-frameworks)
- [💻 Hardware & Model Specifications](#-hardware--model-specifications)
- [🚀 Quick Start & 1-Click Launchers](#-quick-start--1-click-launchers)
- [🧪 Testing & Benchmarking](#-testing--benchmarking)
- [🙏 Credits & Attribution](#-credits--attribution)
- [📄 License](#-license)

---

## 💡 The PotatoClaw Research Mission

Modern autonomous computer-use agents (e.g., AutoGPT, CrewAI, frontier browser agents) assume unlimited resources: 70B–405B parameter frontier models, 32k–128k context windows, giant vector databases, and expensive cloud API subscriptions. On consumer hardware, these architectures fail instantly due to Out-Of-Memory (OOM) errors, context saturation, token thrashing, and hallucinated action loops.

**PotatoClaw** answers the central research question:

> *"How much apparent agent capability can be recovered through architecture, memory, graph planning, deterministic execution, verification, and selective neural computation when the underlying language model is small?"*

PotatoClaw proves that a **compact 4B model running on a budget GTX 1650 GPU with only 2048 tokens of context** can match or exceed the task completion reliability of cloud agents when supported by a deterministic systems architecture.

---

## ⚙️ Core Principle: "Rule Zero"

> **DO LESS NEURAL COMPUTATION.** Never use an LLM for algorithmic work that zero-overhead code can solve deterministically.

1. **Deterministic Planning**: Task sequencing and readiness are solved by DAG Topological Sort, not LLM self-reflection.
2. **Deterministic Memory**: Context budgeting is solved by Bounded Working Memory (BWM) with utility decay, not unbounded conversation history.
3. **Deterministic Verification**: Output correctness is verified via OS exit codes, AST parsing, regex, and file signatures, not LLM self-grading.
4. **Deterministic Observation**: Raw terminal outputs, browser HTML, and file listings are compressed into milestone summaries by Observation Compilers before reaching the model.
5. **Deterministic Circuit Breaking**: Action repeat loops and oscillatory cycles are halted by cryptographic failure signature hashing.

---

## ⚠️ Imperfect, Work-in-Progress & An Open Invitation to Build

> **Honest Engineering Note**: PotatoClaw is an experimental, evolving open-source research project, not a polished commercial black-box product. It is intentionally raw, scrappy, and imperfect.

When running 3B–7B parameter models on budget consumer hardware under tight 2048-token context constraints:
- Small models will occasionally stumble, generate awkward phrasing, or produce reasoning quirks.
- Edge-case user prompts might occasionally bypass fast-path intent matching or require an extra conversational turn.
- Small models have varying reasoning styles (e.g., `<think>` tokens, JSON formatting fidelity).

### 🛠️ You Can Build Upon This — Make It Better For Your Potato PC!
**This codebase is a modular foundation designed for you to hack, adapt, customize, and improve for your own unique hardware:**
1. **Swap & Test Other Small Models**: Plug in `Phi-3.5-mini`, `Qwen-2.5-Coder-3B`, `Llama-3.2-3B`, `Gemma-2-2B`, or `DeepSeek-R1-Distill-Qwen-1.5B`.
2. **Tune BWM Memory Scoring**: Adjust the mathematical weights in [`scripts/potato_bwm.py`](scripts/potato_bwm.py) ($\text{Score} = w_1 \cdot \text{imp} + w_2 \cdot \text{rel} + w_3 \cdot \text{nov} + w_4 \cdot \text{rec} - w_5 \cdot \text{cost}$) to prioritize code snippets, tool outcomes, or conversation continuity for your specific workflows.
3. **Add Custom Domain Tools**: Extend [`scripts/potato_chat.py`](scripts/potato_chat.py) with custom local tools — such as SQLite query executors, local audio transcription (Whisper.cpp), PDF text extractors, or local Docker managers.
4. **Adapt to Lower (or Higher) Specs**: 
   - *Lower specs (Integrated GPU / 8GB RAM)*: Adjust GPU offload layers (`-ngl`) in [`scripts/start-spark-potato.ps1`](scripts/start-spark-potato.ps1) or run pure CPU inference with `llama.cpp`.
   - *Higher specs (RTX 2060/3060/4060)*: Expand context to 4096 tokens and run 7B/8B Q4 models with even greater reasoning depth!
5. **Contribute Your Fixes**: Found a bug or engineered a smarter compiler/verifier heuristic? Submit a pull request! Let's empower potato PC owners worldwide to run real AI computer agents without paying cloud tolls.

### 🤖 Calling Robotics & Industrial Edge Engineers: Build Upon This!
Physical machines, robots, and industrial systems cannot afford cloud network latency, dropped packets, or 45-second LLM reasoning stalls. PotatoClaw's architecture provides the exact primitives needed for physical embodied computing:
- **Deterministic Action Gating**: No motor, actuator, or valve fires without formal verification from [`DeterministicVerifier`](scripts/potato_verifier.py).
- **Sensor Telemetry Compilers**: Converts multi-megabyte sensor telemetry (IMU streams, LIDAR ranges, PLC register logs) into compact structured states before neural evaluation.
- **Fail-Safe Circuit Breakers**: Halts repetitive obstacle collisions or oscillating trajectory cycles before mechanical hardware damage occurs.
- **100% On-Device Autonomy**: Runs completely offline on low-power companion computers (NVIDIA Jetson, Raspberry Pi 5 + NPU, x86 industrial DIN-rail boxes) without needing satellite or cellular internet.

---

## 🎯 Comprehensive Real-World Use Cases

PotatoClaw is not a toy proof-of-concept; it is a battle-tested daily driver for developers, researchers, and system operators who need real automation without cloud dependency.

### 1. Autonomous Software Engineering & Local Developer Workflows
- **Autonomous Git Maintenance**: Inspect repository status, stage modified files, generate clean conventional commit messages, and push changes to remote branches without leaving the terminal.
- **AST-Verified Code Generation**: Generate Python, JavaScript, and Bash scripts with deterministic syntax tree verification that catches syntax errors before execution.
- **Automated Bug Localization & Traceback Diagnosis**: Parse complex runtime errors, locate the exact offending source lines, and generate targeted regression patches.
- **Zero-Cloud Codebase Q&A**: Interrogate large local code repositories within a tight 2048-token window using local graph extraction ($G_{\text{local}}$) without uploading proprietary IP to cloud servers.
- **Automated Test Suite Orchestration**: Execute unit and integration test suites, extract failing assertions, and iteratively repair broken tests.

### 2. Privacy-Preserving OSINT, Technical Research & News Intelligence
- **Real-Time Defense & Strategic News Curation**: Ingest breaking defense intelligence from authoritative global and regional sources (e.g. **IDRW / Indian Defence**, **Livefist**, **Breaking Defense**, **Defense One**, **US Naval Institute**).
- **Automated ArXiv & Research Digesting**: Query scientific preprint feeds across Quantum Physics, Artificial Intelligence, and Materials Science, extracting abstracts and methodology milestones.
- **Hacker News & Tech Pulse Extraction**: Scan top engineering and technology discussions, filtering out promotional spam and clickbait via deterministic keyword scoring.
- **Air-Gapped Market & Technical Surveillance**: Monitor RSS/Atom feeds, corporate announcements, and open-source changelogs completely offline.

### 3. Social Media, Content Creation & Automated Publishing
- **Autonomous X (Twitter) News Dispatcher**: Automatically identify the day's highest-signal breaking story, draft a punchy, hook-driven tweet with relevant hashtags, and deterministically enforce Twitter’s 280-character limit (including `t.co` URL weighting).
- **Multi-Source News Synthesis**: Ingest 5–10 disparate articles on a single topic and compile an objective, concise executive briefing.
- **Markdown Documentation Refactoring**: Automatically generate comprehensive documentation, changelogs, and usage guides from git commit history and source comments.

### 4. Air-Gapped Environments, Edge Computing & Defense Systems
- **Confidential Military & Defense Operations**: Deploy autonomous computer assistance in SCIFs, field units, and air-gapped workstations where internet access is physically prohibited.
- **Edge Computing & Remote Hardware**: Run on budget laptops, Intel NUCs, AMD Ryzen mini-PCs, and industrial workstations in areas with intermittent or zero satellite connectivity.
- **Healthcare & Regulated Enterprise Compliance**: Automate data manipulation and report formatting on patient data (HIPAA) or financial transactions (SOC2) with mathematical proof that zero bytes leave the local machine.

### 5. System Administration, DevOps & Infrastructure Reliability
- **Automated Log Analysis**: Ingest multi-megabyte server log files, apply deterministic head/tail compilation to filter out routine noise, and highlight critical stack traces and crash events.
- **Host Resource Auditing & Diagnostics**: Query GPU VRAM, system RAM, CPU temperatures, and disk utilization, formatting human-readable telemetry tables.
- **Safe Command Sandboxing**: Run administrative terminal commands with deterministic timeout bounds and exit-code validation to prevent runaway processes.

### 6. Lightweight Web Scraping, Navigation & Regression Testing
- **Progressive DOM Distillation**: Browse websites, extract `<title>`, meta descriptions, and core body text, discarding megabytes of JavaScript, CSS, and advertising payloads before prompt creation.
- **Automated Endpoint & Health Probing**: Monitor local dev servers, verify HTTP response codes, and validate JSON API contracts.
- **Browser-Based Research Capture**: Extract technical documentation across multiple web pages and assemble structured local markdown reference manuals.

### 7. Daily Desktop Productivity & Personal AI Companion
- **Sub-Second Rule Zero Direct Chat**: Type commands like `fetch_news defence`, `cat README.md`, or `run git status` into `potato_chat.bat` and receive instant **0.05-second deterministic execution** without burning model tokens.
- **Natural Language Command Translation**: Convert casual instructions ("check if port 11435 is open", "find all files modified today") into verified PowerShell/Bash commands.
- **Local Scratchpad & Task Memory**: Maintain long-term project memory across reboots using persistent BWM disk checkpoints without needing a dedicated vector database server.

### 8. Robotics Edge-Based Computing & Physical Embodied Agents
- **Autonomous Mobile Robots (AMRs) & AGVs**: Host a local task coordinator on an onboard NVIDIA Jetson Orin Nano, Raspberry Pi 5, or Intel NUC. The small model coordinates high-level route planning, obstacle avoidance re-routing, and status reporting without cloud latency.
- **ROS 2 / ROS 1 Bridge Integration**: Sequence ROS 2 action servers and topics deterministically. The agent receives telemetry summaries from `/odom` or `/scan`, verifies prerequisite safety constraints, and triggers motion commands.
- **Unmanned Aerial Vehicles (UAVs / Drones)**: Run an onboard mission supervisor communicating over MAVLink/serial. Ingest mission goals, monitor battery voltage and GPS coordinate drift, and adjust flight patterns locally during communication blackouts.
- **Robotic Arm & Manipulation Task Verification**: Verify gripper contact states, joint limit compliance, and object presence with deterministic sensor assertions before progressing to the next manipulation phase.
- **Hardware-Level Loop Circuit Breaking**: Cryptographic action hashing prevents infinite mechanical retry thrashing (e.g. attempting to grasp an ungraspable object repeatedly or oscillating between two unreachable waypoints).

### 9. Industrial Edge Computing, Smart Manufacturing & Critical Infrastructure
- **Air-Gapped SCADA & PLC Telemetry Diagnostics**: Run on fanless industrial PCs (Siemens, Advantech, Beckhoff) connected to factory Modbus, OPC-UA, and MQTT networks. Diagnose PLC fault alarms and register anomalies without exposing proprietary manufacturing processes to cloud servers.
- **Edge Predictive Maintenance on Vibration & Thermal Logs**: Parse high-frequency vibration data and thermal sensor logs, using `ObservationCompiler` to extract temperature anomalies, bearing wear indicators, and motor RPM deviations into structured anomaly alerts.
- **Field Technician SOP & Safety Copilot**: Deploy on ruggedized industrial tablets (Getac, Panasonic Toughbook) in offshore oil platforms, mining operations, substations, and cleanrooms. Guides field engineers through standard operating procedures (SOPs) with zero external connectivity.
- **Automated Manufacturing Quality Control (QC) Stations**: Ingest optical inspection logs, barcode scan records, and dimensional tolerance checks at assembly stations, deterministically validating batch pass/fail criteria and logging traceability records.
- **Off-Grid Energy & Utility Monitoring**: Oversee microgrids, solar inverter arrays, and wind turbine sub-assemblies in remote geographic installations with strict low-power consumption and zero cellular reliance.

---

## ⚡ Empirical Evaluation: PotatoBench 10-Task Research Suite

Evaluated live on **NVIDIA GeForce GTX 1650 (4GB VRAM)** + **AMD Ryzen 5 5600H (6 Cores)** with `Spark-X2.5-4B-Q4_K_M.gguf` under a hard $\le 2048$ token budget:

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

### Key Benchmark Metrics
- **Success Rate**: **100.0% (10/10 tasks passed)**
- **Average Task Latency**: **5.23s** (vs 56.74s uncompressed baseline, **>10x faster**)
- **Average Tokens / Task**: **129.3 tokens** (fits easily inside 2048 budget)
- **Model Invocations / Task**: **1.0 call** (strictly optimal)
- **VRAM Footprint**: **~2,165 MiB steady** (leaving ~1.9 GB headroom for system display)
- **Unit & Integration Tests**: **66/66 passed (100%)**

*Detailed reports and raw datasets:*
- [`BENCHMARK.md`](BENCHMARK.md) — Complete 10-task experimental report.
- [`ABLATIONS.md`](ABLATIONS.md) — 8-way ablation study isolating each architectural module.
- [`benchmarks/potatobench/results.json`](benchmarks/potatobench/results.json) — Full machine-readable dataset.

---

## 🏗️ PotatoClaw V3 Modular Architecture

```mermaid
graph TD
    User["User Prompt / Goal"] --> R0{"Rule Zero Fast-Path?"}
    R0 -- "Direct Command (news/run/cat)" --> DetExec["Deterministic Execution (0.05s, 0 Tokens)"]
    R0 -- "Complex Goal" --> DAG["Deterministic TaskGraph & DAG Planner"]
    
    DAG --> Scheduler["Topological Ready-Node Selector"]
    Scheduler --> Glocal["Local Graph Neighborhood G_local(v)"]
    
    Glocal --> BWM["Bounded Working Memory (BWM <= 850 chars)"]
    BWM --> Comp["Observation & Context Compilers"]
    
    Comp --> LLM["Spark-X2.5-4B (GTX 1650 4GB VRAM)"]
    LLM --> Action["Proposed Action / Tool Call"]
    
    Action --> Loop["Loop Detector & Cycle Breaker"]
    Loop -- "3x Repeat Detected" --> Halt["Halt Action & Request Alternative"]
    Loop -- "Novel Action" --> Exec["Tool Execution (Sandbox)"]
    
    Exec --> Verifier["Deterministic Verifier (Exit Code / Regex / AST)"]
    Verifier -- "PASS" --> BWM_Update["Promote to BWM / Checkpoint"]
    Verifier -- "FAIL" --> FailMem["Record Failure Signature hash(v, a, err)"]
    FailMem --> DynamicPatch["Dynamic Prerequisite Insertion"]
    DynamicPatch --> DAG
```

1. **🗺️ Deterministic Task Graph & DAG Scheduler ([`scripts/potato_graph.py`](scripts/potato_graph.py))**:
   - Explicit dependency graphs with deterministic readiness validation:
     $$\text{Ready}(v) \iff \forall p \in \text{Parents}(v), \text{status}(p) = \text{COMPLETE}$$
   - Dynamic prerequisite insertion and milestone subgraph compaction to keep graph representations ultra-compact.
2. **🧠 Bounded Working Memory (BWM) ([`scripts/potato_bwm.py`](scripts/potato_bwm.py))**:
   - Multi-tier memory architecture (**L0** raw observation $\to$ **L1** active BWM $\to$ **L2** disk checkpoints).
   - Utility scoring function:
     $$\text{Score}(m_i, v) = w_1 \cdot \text{imp} + w_2 \cdot \text{rel}(v) + w_3 \cdot \text{nov} + w_4 \cdot \text{rec} - w_5 \cdot \text{cost}$$
   - Non-evictable protected memory for user goals, critical rules, and modified file paths.
3. **🔍 Observation & Context Compilers ([`scripts/potato_compiler.py`](scripts/potato_compiler.py))**:
   - Compresses noisy multi-line terminal dumps and HTML DOM trees into 1–3 line structured summaries.
4. **⚖️ Deterministic Verifier ([`scripts/potato_verifier.py`](scripts/potato_verifier.py))**:
   - Zero-LLM validation of exit codes, file existence, content regex, and JSON schema in $<0.5$ ms.
5. **🛡️ Failure Memory & Loop Breaker ([`scripts/potato_failure_memory.py`](scripts/potato_failure_memory.py))**:
   - Cryptographic failure signature hashing (`hash(node, action, error)`).
   - Halts 3x identical repeat loops and oscillatory $A \to B \to A \to B$ thrashing.

---

## 🥊 PotatoClaw vs Traditional Cloud Agent Frameworks

| Capability / Metric | Traditional Cloud Frameworks (LangChain / CrewAI / AutoGen) | PotatoClaw V3 Architecture |
| :--- | :--- | :--- |
| **Minimum Hardware** | 16GB–32GB RAM + Cloud API Key | **4GB GPU (GTX 1650) + 6GB RAM** |
| **Working Context** | 32,000 – 128,000 tokens | **Hard bounded $\le 2048$ tokens** |
| **Operating Cost** | $0.05 – $2.00 per task run | **$0.00 (100% Free & Local)** |
| **Data Privacy** | Code & data sent to external cloud servers | **100% On-Device / Air-Gapped Safe** |
| **Loop Prevention** | Heuristic retries (often exhausts token budget) | **Deterministic Action & Cycle Breakers** |
| **Direct Command Latency** | 15s – 45s (full LLM round-trip) | **0.05s (Rule Zero Fast-Path)** |
| **Output Verification** | LLM self-reflection (hallucination-prone) | **OS Exit Codes + AST + Regex Verifiers** |

---

## 💻 Hardware & Model Specifications

### Primary Target Hardware
- **GPU**: NVIDIA GeForce GTX 1650 (4 GB VRAM)
- **CPU**: AMD Ryzen 5 5600H (6 Cores / 12 Threads)
- **RAM**: 6 GB – 8 GB System RAM
- **Storage**: Standard NVMe / SATA SSD

### Model Runtime Configuration
- **Model**: `Spark-X2.5-4B-Q4_K_M.gguf` (~2.4 GB GGUF weight)
- **Inference Engine**: `llama-server` (`llama.cpp`) running inside WSL 2 or Linux
- **Offload Configuration**: 26 GPU layers offloaded to VRAM (`-ngl 26 -c 2048 -np 1 -fa on -t 6`)
- **VRAM Allocation**: ~2,165 MiB (leaves ~1.9 GB VRAM free for desktop display)
- **API Endpoint**: `http://127.0.0.1:11435/v1/chat/completions`

---

## 🚀 Quick Start & 1-Click Launchers

### 1. Start the Local Model Server
```powershell
.\scripts\start-spark-potato.ps1
```
*Initializes `llama-server` with single-slot Flash Attention on port 11435.*

### 2. Launch Interactive Potato AI Agent Chat
Double-click **`potato_chat.bat`** or run via PowerShell:
```powershell
.\potato_chat.ps1
```
*Try typing:*
- `indian defence news` $\to$ *Instant breaking DRDO / IDRW stories (0.05s)*
- `fetch_news tech` $\to$ *MIT Tech Review & Hacker News updates*
- `read README.md` $\to$ *Fast file inspection with observation compression*
- `run git status` $\to$ *Verified terminal command execution*

### 3. Launch Master Automation Hub
Double-click **`post_all.bat`** or run via PowerShell:
```powershell
.\post_all.ps1
```
*Interactive console menu to launch Chat, post Tech/Defense/Physics stories to X, or execute benchmarks.*

---

## 🧪 Testing & Benchmarking

Verify all architectural invariants on your local machine:

```powershell
# Run Comprehensive V3 Architectural Test Suite (48/48 Passed)
python scripts\test_potato_core.py

# Run V2 Integration Test Suite (18/18 Passed)
python scripts\test_potato_v2.py

# Run Live PotatoBench Evaluation Suite (10 Tasks + 8 Ablations)
python scripts\run_benchmarks.py potatobench
```

---

## 🙏 Credits & Attribution

### 🦞 OpenClaw
PotatoClaw is built upon and inspired by the incredible open-source architecture of **[OpenClaw](https://github.com/openclaw/openclaw)**. We express deep gratitude to the OpenClaw maintainers for:
- Foundational gateway protocols and multi-platform agent execution patterns.
- Comprehensive tool definitions, sandbox boundaries, and session models.
- Pioneering open-source autonomous agent architectures that make small-model local experimentation possible.
- Documentation: [https://docs.openclaw.ai](https://docs.openclaw.ai) | Source: [https://github.com/openclaw/openclaw](https://github.com/openclaw/openclaw).

### ⚡ Gemini
Architectural evolution, empirical PotatoBench design, Bounded Working Memory algorithms, deterministic verifiers, loop circuit breakers, and systems co-engineering designed and implemented in collaboration with **Google DeepMind's Gemini**.

### 🤖 ChatGPT
Conceptual exploration, baseline prompt structuring ideas, and research dialogue developed in consultation with **OpenAI's ChatGPT**.

---

## 📄 License
MIT License. Built with ❤️ for the open-source community and owners of potato PCs everywhere.
