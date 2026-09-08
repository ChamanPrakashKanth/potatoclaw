---
name: potato-microdecoders
description: Decode batches of short read-only engineering requests into 100 local specialist task IDs. Use when batch routing avoids repeated interpretation; not for tool execution, code generation, answers, general planning, or tasks cheaper to handle directly.
---

# Local microdecoders

The user wants small local specialists only when beneficial. Prefer this for batches of similar short requests, not individual obvious questions. Use `decoder.py catalog` to inspect supported IDs only when needed. Profiles cover logs, test evidence, Python, TypeScript, Git, configuration, documentation, data, performance, and network evidence.

Run `python -X utf8 <skill-directory>/decoder.py decode --file <authorized-JSON-array>` for 1-100 requests. Or use `--text "Find python imports modules"` for a single probe. No tools or filesystem mutations occur. The returned task IDs are routing suggestions; Codex remains responsible for interpreting the request and obtaining evidence with normal authorized tools.

The optional API is `python -X utf8 <skill-directory>/decoder.py serve`, bound to `127.0.0.1:11436`. POST JSON `{"jobs":["request"]}` to `/decode` with `Content-Type: application/json`. It runs sequentially, logs no request content, and has no outbound network code. Do not start it unless needed; command-line batching avoids a persistent process. No boot auto-start is installed.

## Model boundary

There are 100 separately trained binary specialist heads on a shared two-layer causal tiny-GPT backbone. Each instantiated specialist uses 994,946 parameters, including 386 distinct head parameters. This is **not 100 independently pretrained LLMs**, not 100 native Codex subagents, and not a general-purpose language model. A single backbone is loaded to conserve memory; at most 16 inputs are evaluated together on two CPU threads. Context is 32 hashed-word tokens.

Read `models/qualification.json` and `decoder.py status` before considering neural use. Do not use neural routing automatically unless its held-out challenge accuracy exceeds the lexical baseline and the relevant specialist is qualified. `--experimental-neural` (API `experimental_neural:true`) is for explicitly requested experiments or that evidence-backed improvement, not a default. Missing models, hash mismatch, low confidence, ambiguity, or disabled specialists fall back to Codex. Never retrain during ordinary tasks.

Training uses synthetic requests only. Template holdouts are not evidence of generalization to arbitrary user language. The challenge set is small; token savings have not been established. Never call this to do exact searching, parsing, arithmetic, verification, or other deterministic work. No model output is permission to execute an action. Do not send secrets or unrelated task material.

For requested training work only: `train.py --output <new-directory> --steps 500 --seconds 240`. PyTorch is needed only for training or optional neural inference; default routing is standard-library Python. Preserve previous results. New weights must have matching qualification before use.
