# PotatoBench 10-Task Empirical Evaluation Report

**Date:** 2026-09-03 19:18:49

## 1. Experimental Environment & Hardware Profile

- **Primary Target GPU**: NVIDIA GeForce GTX 1650 (4 GB VRAM)
- **VRAM Allocation**: ~2,165 MiB steady (leaving ~1.9 GB headroom)
- **CPU**: AMD Ryzen 5 5600H (6 Cores, 12 Threads)
- **Language Model**: `spark-x2.5-4b:latest` (Q4_K_M GGUF via llama-server)
- **Context Working Cap**: Hard Budget $\le 2048$ Tokens

## 2. Summary Metrics Across 10 Tasks

- **Overall Success Rate**: **100.0%** (10/10 passed)
- **Average Task Latency**: **5.23s**
- **Average Tokens / Task**: **129.3 tokens**
- **Total Model Calls**: **10 calls**

## 3. Individual Task Results (10 Categories)

| Task ID | Category | Status | Latency (s) | Total Tokens | Model Calls | Tool Calls |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `task_1_filesystem` | Filesystem Operations | ✅ PASS | 5.92s | 120 | 1 | 1 |
| `task_2_terminal` | Terminal Operations | ✅ PASS | 4.938s | 123 | 1 | 1 |
| `task_3_browser` | Browser Navigation | ✅ PASS | 7.433s | 134 | 1 | 1 |
| `task_4_coding` | Coding | ✅ PASS | 3.439s | 79 | 1 | 0 |
| `task_5_debugging` | Debugging | ✅ PASS | 3.337s | 105 | 1 | 0 |
| `task_6_info_extract` | Information Extraction | ✅ PASS | 5.602s | 141 | 1 | 1 |
| `task_7_multistep` | Multi-Step Workflow | ✅ PASS | 4.863s | 93 | 1 | 3 |
| `task_8_failure_recovery` | Failure Recovery | ✅ PASS | 6.521s | 150 | 1 | 2 |
| `task_9_constraint_retention` | Constraint Retention | ✅ PASS | 6.716s | 131 | 1 | 0 |
| `task_10_long_horizon` | Long-Horizon Torture Test | ✅ PASS | 3.524s | 217 | 1 | 8 |

## 4. Machine-Readable Artifacts

- JSON: [`benchmarks/potatobench/results.json`](file:///c:/Users/user/Downloads/Potatoclaw/benchmarks/potatobench/results.json)
- CSV: [`benchmarks/potatobench/results.csv`](file:///c:/Users/user/Downloads/Potatoclaw/benchmarks/potatobench/results.csv)
