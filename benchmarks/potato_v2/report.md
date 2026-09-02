# PotatoClaw Benchmark Report: POTATO_V2

**Date:** 2026-09-02 15:31:30

- **Model**: `spark-x2.5-4b:latest` (Q4_K_M)
- **Context Budget**: `2048 Tokens`
- **Success Rate**: `100.0%` (6/6 passed)
- **Avg Task Latency**: `28.51s`
- **Inference Speed**: `4.24 tokens/s`
- **Peak Context Tokens**: `217 / 2048`
- **GPU VRAM Used**: `2182.7 MiB / 4096 MiB`

## Standard Tasks

| Task | Success | Latency (s) | Model Calls | Peak Context | Output |
| :--- | :---: | :---: | :---: | :---: | :--- |
| Open example.com and return title | ✅ PASS | 40.706 | 2 | 157 | Thinking: The user wants me to open a UR... |
| List browser tabs | ✅ PASS | 12.765 | 2 | 167 | The user asked me to list all currently ... |
| Read local text file | ✅ PASS | 18.884 | 2 | 217 | The user asked me to read a file and ext... |
| Run git status | ✅ PASS | 31.524 | 2 | 208 | The user asked me to execute git status ... |
| Search web and extract 1 result | ✅ PASS | 36.206 | 2 | 194 | The user asked me to search the browser ... |
| 3-5 Step Browser Form Interaction | ✅ PASS | 30.978 | 3 | 217 | The user asked me to go to the URL, ente... |

## Stress Test Results (Levels 1 - 5)

| Level | Task | Status | Latency (s) | Total Tokens |
| :---: | :--- | :---: | :---: | :---: |
| 1 | Simple Title Extraction | ✅ PASS | 2.65 | 79 |
| 2 | Web Search & Selection | ✅ PASS | 1.66 | 88 |
| 3 | GitHub Release Inspection | ✅ PASS | 2.49 | 106 |
| 4 | Test Diagnosis & Bug Explanation | ✅ PASS | 2.7 | 117 |
| 5 | Combined Browser + Filesystem Report | ✅ PASS | 4.12 | 113 |
