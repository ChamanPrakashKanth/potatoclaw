# PotatoClaw 🥔🦞 — Small-Local-Model Computer Agent & Automation Suite

<p align="center">
  <b>The ultra-low-resource local computer agent and content automation engine designed for potato PCs.</b><br>
  <i>Runs 100% locally on a 4GB GPU (GTX 1650), 6GB RAM, and a 2048-token context budget with Spark-X2.5-4B.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Model-Spark--X2.5--4B--Q4__K__M-blue?style=flat-square" alt="Model">
  <img src="https://img.shields.io/badge/Hardware-GTX%201650%20(4GB%20VRAM)-green?style=flat-square" alt="Hardware">
  <img src="https://img.shields.io/badge/Context%20Budget-2048%20Tokens-orange?style=flat-square" alt="Context Budget">
  <img src="https://img.shields.io/badge/Cloud%20Dependencies-ZERO%20(100%25%20Local)-red?style=flat-square" alt="Zero Cloud">
  <img src="https://img.shields.io/badge/License-MIT-purple?style=flat-square" alt="License">
</p>

---

## 💡 The PotatoClaw Mission

Most AI computer agents require massive 70B+ cloud models, giant context windows (32k–128k), and heavy vector databases. **PotatoClaw** proves the opposite hypothesis:

> **"A small local model (3B–4B) becomes a highly capable, rock-solid computer agent when the runtime harness manages bounded memory, progressive observations, tool routing, and small-model syntax repair instead of forcing the model to reason through raw token bloat."**

---

## ⚡ Benchmark Results: Baseline vs PotatoClaw V2

Tested on **NVIDIA GeForce GTX 1650 (4GB VRAM)** + **AMD Ryzen 5 5600H (6 Cores)** with `Spark-X2.5-4B-Q4_K_M.gguf`:

| Metric | Baseline PotatoClaw | PotatoClaw V2 (BMW) | Improvement / Delta |
| :--- | :---: | :---: | :---: |
| **Task Success Rate** | **100.0%** (6/6) | **100.0%** (6/6) | Preserved 100% Reliability |
| **Average Task Latency** | **56.74s** | **28.51s** | **-49.7% Latency Reduction (2x faster)** |
| **Multi-Step Task Latency** | **142.30s** | **30.98s** | **-78.2% Latency Reduction (4.6x faster)** |
| **Peak Context Tokens** | **227 tokens** | **217 tokens** | Strict 2048 Token Budget Maintained |
| **GPU VRAM Utilization** | **2,171 MiB** | **2,182 MiB** | Steady (~1.9 GB VRAM Headroom) |
| **Process RAM (RSS)** | **45.0 MiB** | **45.0 MiB** | Ultra-lean memory footprint |
| **Stress Test Success (Levels 1–5)** | *Untested* | **100% (5/5 PASS)** | Sub-4.2s per step |

---

## 🏗️ Core Architecture Components

### 1. 🧠 BMW — Bounded Working Memory (`src/agents/potato-bmw.ts`)
- Structured task state representation (`GOAL`, `CURRENT STATE`, `IMPORTANT FACTS`, `COMPLETED ACTIONS`, `PENDING ACTIONS`, `ERRORS`, `RESULTS`).
- Enforces an 850-character budget (~200 tokens) with deterministic FIFO pruning, eliminating conversational bloat.

### 2. ⏳ Semantic Memory Decay (`src/agents/potato-semantic-decay.ts`)
- Fast, deterministic heuristic scoring (recency, goal keyword overlap, tool affinity, error preservation) without heavy vector databases or embedding models.

### 3. 🎯 Dynamic Tool Routing with Escape Mechanism (`src/agents/potato-tool-router.ts`)
- Dynamically filters tool schemas to the current domain (`browser`, `filesystem`, `shell`, `core`), reducing prompt token overhead by >65%.
- Includes lightweight `request_tool_family` escape capability.

### 4. 🔧 Small-Model Tool-Call Repair (`src/agents/small-model-repair.ts`)
- Automatically recovers single quotes, trailing commas, unquoted keys, unclosed braces, tool aliases (`browser_navigate` $\to$ `browser`, `run_command` $\to$ `exec`), and argument aliases (`target_url` $\to$ `url`).

### 5. 🛡️ Loop Protection Circuit Breaker (`src/agents/potato-loop-detector.ts`)
- Detects 3x repeated identical actions and oscillatory $A \to B \to A \to B$ cycles, injecting concise corrective state prompts before model runaway.

### 6. 🌐 Browser Intelligence in Code & Progressive Observation (`src/agents/potato-browser-intelligence.ts`)
- Offloads mechanical reasoning (page titles, URLs, link mapping) directly into code without LLM round-trips.
- 4 Progressive observation tiers (Level 0: title+URL to Level 3: full extraction).

### 7. 🚦 Lightweight Resource Governor (`src/agents/potato-resource-governor.ts`)
- Hardware-aware throttling (`GREEN` / `AMBER` / `RED`) based on context token pressure, system RAM, and GPU VRAM.

---

## 📱 Content Automation Engines

### 🐦 X (Twitter) Single-Story News Poster
- **Target**: Non-premium standard X accounts (strict 280-character budget).
- **Curated Feeds**: MIT Tech Review, Hacker News, Breaking Defense, Defense One, USNI, Phys.org Quantum, Physics World.
- **Features**: Twitter `t.co` 23-char link weighting, direct article link embedding for automatic rich preview cards, and 1-click browser posting with clipboard automation.

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

### Master Posting & Automation Hub
```cmd
:: Launch Interactive Menu
post_all.bat

:: Or run directly via PowerShell
.\post_all.ps1
```

### Direct CLI Commands
```cmd
:: Post Tech / Defence / Physics single-story to X
post_all.bat x tech
post_all.bat x defence
post_all.bat x physics
```

### Dedicated Launchers
- **[`post_tech_defence_physics_news.bat`](file:///c:/Users/user/Downloads/Potatoclaw/post_tech_defence_physics_news.bat)**: Direct single-story X poster.

---

## 🧪 Testing & Benchmarking

```powershell
# 1. Run Core Architecture Unit Tests (18 Passed, 0 Failed)
& "C:\Program Files\Python38\python.exe" scripts\test_potato_v2.py

# 2. Run Full V2 Benchmark Suite & Stress Tests (Levels 1-5)
& "C:\Program Files\Python38\python.exe" scripts\run_benchmarks.py potato_v2
```

Detailed reports are generated in:
- [`benchmarks/baseline/report.md`](file:///c:/Users/user/Downloads/Potatoclaw/benchmarks/baseline/report.md)
- [`benchmarks/potato_v2/comparison_report.md`](file:///c:/Users/user/Downloads/Potatoclaw/benchmarks/potato_v2/comparison_report.md)

---

## 📄 License
MIT License. Built for the community with ❤️ for potato PC owners.
