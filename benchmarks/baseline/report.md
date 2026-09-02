# PotatoClaw Benchmark Report: BASELINE

**Date:** 2026-09-02 15:22:49

- **Model**: `spark-x2.5-4b:latest` (Q4_K_M)
- **Context Budget**: `2048 Tokens`
- **Success Rate**: `100.0%` (6/6 passed)
- **Avg Task Latency**: `56.74s`
- **Inference Speed**: `4.0 tokens/s`
- **Peak Context Tokens**: `227 / 2048`
- **GPU VRAM Used**: `2171.0 MiB / 4096 MiB`

## Task Results

| Task | Success | Latency (s) | Model Calls | Peak Context | Output |
| :--- | :---: | :---: | :---: | :---: | :--- |
| Open example.com and return title | ✅ PASS | 58.08 | 2 | 160 | Thinking: The user wants me to open a UR... |
| List browser tabs | ✅ PASS | 11.903 | 2 | 184 | The user asked me to list all currently ... |
| Read local text file | ✅ PASS | 14.914 | 2 | 219 | The user asked me to read a file and ext... |
| Run git status | ✅ PASS | 60.04 | 2 | 223 | The user asked me to execute git status ... |
| Search web and extract 1 result | ✅ PASS | 53.21 | 2 | 207 | The user asked me to search the browser ... |
| 3-5 Step Browser Form Interaction | ✅ PASS | 142.297 | 3 | 227 | The user asked me to go to the form page... |
