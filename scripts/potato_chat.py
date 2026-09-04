#!/usr/bin/env python3
"""
PotatoClaw Interactive AI Agent Chat (PotatoAI V3)
Powered by Spark-X2.5-4B + Full PotatoClaw V3 Architecture:
- Rule Zero Direct Intent Interception (Instant 0.05s Execution)
- TaskGraph & DAG Scheduler (potato_graph.py)
- Bounded Working Memory & Hierarchical Tiers (potato_bwm.py)
- Observation Compiler & Context Compiler (potato_compiler.py)
- Deterministic Verifier (potato_verifier.py)
- Failure Memory, Loop Breaker & Dynamic Tool Router (potato_failure_memory.py)
"""

import sys
import os
import io
import time
import json
import ast
import re
import urllib.request
import urllib.parse
import subprocess
from datetime import datetime

# Windows UTF-8 stdout configuration
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Enable ANSI escape sequences on Windows
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from potato_graph import TaskGraph, TaskNode, NodeStatus, ToolFamily
from potato_bwm import BoundedWorkingMemory, HierarchicalMemory
from potato_compiler import ObservationCompiler, ContextCompiler
from potato_verifier import DeterministicVerifier
from potato_failure_memory import FailureMemoryStore, LoopDetector, DynamicToolRouter

try:
    from fresh_start import purge_all_caches, reset_llama_server_kv_cache
except ImportError:
    def purge_all_caches(verbose=False): pass
    def reset_llama_server_kv_cache(): pass

try:
    from x_news_engine import fetch_category_news
except ImportError:
    def fetch_category_news(cat, max_items=2): return []

SPARK_API_URL = "http://127.0.0.1:11435/v1/chat/completions"
SPARK_HEALTH_URL = "http://127.0.0.1:11435/health"
MODEL_ID = "spark-x2.5-4b:latest"

# ANSI Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

def intercept_direct_action(user_input):
    """
    Rule Zero: DO NOT USE AN LLM FOR ALGORITHMIC OR DIRECT COMMANDS.
    Intercepts explicit commands and natural news queries for instant 0.05s execution.
    """
    clean = user_input.strip().lower()

    # Explicit commands own their arguments, even when a path contains "news".
    if clean.startswith("read_file ") or clean.startswith("read ") or clean.startswith("cat ") or clean.startswith("view "):
        parts = user_input.strip().split(maxsplit=1)
        if len(parts) > 1:
            path = parts[1].strip()
            if len(path) >= 2 and path[0] == path[-1] and path[0] in "\"'":
                path = path[1:-1]
            return "read_file", {"path": path}

    # 3. Terminal execution
    if clean.startswith("run_command ") or clean.startswith("run ") or clean.startswith("exec ") or clean.startswith("shell "):
        parts = user_input.strip().split(maxsplit=1)
        if len(parts) > 1:
            return "run_command", {"command": parts[1].strip()}

    # 4. Browser navigation
    if clean.startswith("browser ") or clean.startswith("open_url ") or clean.startswith("open ") or clean.startswith("goto "):
        parts = user_input.strip().split(maxsplit=1)
        if len(parts) > 1:
            return "browser", {"url": parts[1].strip()}

    # Match whole words, not fragments like "ai" in "chair" or "war" in "software".
    words = set(re.findall(r"\w+", clean))
    is_news = bool(words & {"news", "headline", "headlines", "fetch_news"})
    categories = {"tech", "defence", "defense", "physics", "science", "indian_defence"}
    if is_news or clean in categories:
        if words & {"defence", "defense", "military", "drdo", "army", "navy", "iaf", "missile", "radar", "weapon", "war", "indian_defence"}:
            category = "indian_defence" if words & {"india", "indian", "bharat", "indian_defence"} else "defence"
        elif words & {"physics", "science", "quantum", "cern", "space", "astronomy", "cosmos", "particle"}:
            category = "physics"
        else:
            category = "tech"
        return "fetch_news", {"category": category}
    return None, {}

# --- Small Model Tool Repair & Universal Parser ---
def repair_tool_json(raw_text):
    if not isinstance(raw_text, str):
        return None
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    
    candidates = [text]
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match and match.group(0) != text:
        candidates.append(match.group(0))
    for candidate in candidates:
        # Valid JSON must be tried before repair so shell quoting stays intact.
        try:
            return json.loads(candidate)
        except (ValueError, RecursionError):
            pass
        # Repair syntax only outside quoted strings. Never evaluate model code.
        tokens = re.split(r'''("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')''', candidate)
        for index in range(0, len(tokens), 2):
            tokens[index] = re.sub(r'([{,]\s*)([a-zA-Z0-9_$]+)\s*:', r'\1"\2":', tokens[index])
            tokens[index] = re.sub(r',\s*([}\]])', r'\1', tokens[index])
        candidate = "".join(tokens)
        for parser in (json.loads, ast.literal_eval):
            try:
                return parser(candidate)
            except (ValueError, SyntaxError, RecursionError):
                pass
    return None

def normalize_tool_call(tool_name, args):
    if isinstance(args, str):
        args = repair_tool_json(args)
    if not isinstance(tool_name, str) or not isinstance(args, dict):
        return None, {}
    args = dict(args)
    tool = str(tool_name).lower().strip()
    if tool in ["chrome_tabs", "browser_tabs", "tabs", "list_tabs"] and any(k in args for k in ["url", "target", "link", "site", "web"]):
        tool = "browser"
        
    if tool in ["browser", "chrome", "open_url", "navigate", "open_browser", "goto"]:
        tool = "browser"
        url = args.get("url") or args.get("target") or args.get("link") or args.get("site") or args.get("arg_value") or ""
        if not url and args:
            url = list(args.values())[0]
        if url and not str(url).startswith("http://") and not str(url).startswith("https://"):
            url = f"https://{url}"
        args["url"] = url

    if tool in ["news", "get_news"]:
        tool = "fetch_news"

    return tool, args

def extract_tool_call(text):
    """
    Extracts tool calls from XML tags (<tool_call>), JSON objects, or function strings.
    """
    if not text:
        return None, {}

    # 1. XML format: <tool_call>...
    xml_match = re.search(r'<tool_call>(.*?)(?:</tool_call>|$)', text, re.DOTALL | re.IGNORECASE)
    if xml_match:
        inner = xml_match.group(1).strip()
        json_obj = repair_tool_json(inner)
        if isinstance(json_obj, dict):
            tool = json_obj.get("tool") or json_obj.get("name") or json_obj.get("action")
            args = json_obj.get("args") or json_obj.get("arguments") or json_obj.get("parameters") or {}
            if tool:
                return normalize_tool_call(tool, args)

        # Check function style inside XML: fetch_news("defence")
        fn_inner = re.search(r'([a-zA-Z0-9_]+)\s*\((.*?)\)', inner)
        if fn_inner:
            tname = fn_inner.group(1)
            raw_arg = fn_inner.group(2).replace('"', '').replace("'", "").strip()
            return normalize_tool_call(tname, {"category": raw_arg} if "news" in tname else {"arg": raw_arg})

        tool_name_match = re.match(r'^([a-zA-Z0-9_\-]+)', inner)
        if tool_name_match:
            tname = tool_name_match.group(1).lower()
            if tname in ["fetch_news", "browser", "read_file", "run_command"]:
                return normalize_tool_call(tname, {"category": "defence"} if "defence" in inner.lower() else {"category": "tech"})

    # 2. JSON format: {"tool": "browser", "args": {"url": "..."}}
    json_obj = repair_tool_json(text)
    if isinstance(json_obj, dict):
        tool = json_obj.get("tool") or json_obj.get("name") or json_obj.get("action")
        args = json_obj.get("args") or json_obj.get("arguments") or json_obj.get("parameters") or {}
        if not args and any(k not in ["tool", "name", "action"] for k in json_obj):
            args = {k: v for k, v in json_obj.items() if k not in ["tool", "name", "action"]}
        if tool:
            return normalize_tool_call(tool, args)

    # 3. Direct function string format: browser(url="...") or fetch_news("defence")
    fn_match = re.search(r'([a-zA-Z0-9_]+)\s*\(\s*(?:([a-zA-Z0-9_]+)\s*=\s*)?["\']([^"\']+)["\']\s*\)', text)
    if fn_match:
        tool_name = fn_match.group(1).lower()
        if tool_name in ["browser", "chrome", "open_url", "navigate", "read_file", "view_file", "run_command", "shell", "fetch_news", "search_web"]:
            arg_name = fn_match.group(2) or ("category" if "news" in tool_name else "url" if any(x in tool_name for x in ["browser", "url", "chrome"]) else "path" if "file" in tool_name else "command")
            val = fn_match.group(3)
            return normalize_tool_call(tool_name, {arg_name: val})

    return None, {}

# --- Local Tools Execution with Observation Compiler & Deterministic Verifier ---
def execute_tool(tool_name, args, verifier=None):
    if verifier is None:
        verifier = DeterministicVerifier()
        
    tool_name = tool_name.lower().strip()
    
    if tool_name in ["read_file", "view_file", "cat"]:
        path = args.get("path") or args.get("file") or args.get("target") or args.get("arg") or ""
        if not path:
            return "Error: Missing 'path' argument.", False
        target_path = os.path.abspath(os.path.join(ROOT_DIR, path)) if not os.path.isabs(path) else path
        v_res = verifier.verify_file_exists(target_path, min_bytes=0)
        if not v_res.passed:
            return f"Error: File '{path}' does not exist.", False
        try:
            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(2000)
            comp = ObservationCompiler.compile_filesystem(target_path, content)
            return comp.format_block(), True
        except Exception as e:
            return f"Error reading file: {e}", False

    elif tool_name in ["run_command", "shell", "exec"]:
        cmd = args.get("command") or args.get("cmd") or args.get("arg") or ""
        if not cmd:
            return "Error: Missing 'command' argument.", False
        try:
            res = subprocess.run(
                cmd, shell=True, cwd=ROOT_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=15
            )
            v_res = verifier.verify_exit_code(res.returncode, expected=0)
            comp = ObservationCompiler.compile_terminal(cmd, res.returncode, res.stdout, res.stderr)
            return comp.format_block(), v_res.passed
        except Exception as e:
            return f"Error running command: {e}", False

    elif tool_name in ["browser", "chrome", "open_url", "navigate"]:
        url = args.get("url") or args.get("target") or args.get("link") or args.get("arg") or ""
        if not url:
            return "Error: Missing 'url' argument.", False
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        try:
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                return "Error: Expected an HTTP(S) URL with a hostname.", False
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 PotatoClaw/3.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                html = resp.read(262144).decode('utf-8', errors='ignore')
                title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
                title = title_match.group(1).strip() if title_match else url
                text = re.sub(r'<[^>]+>', ' ', html)
                snippet = " ".join(text.split())[:350]
                comp = ObservationCompiler.compile_browser(url, title, snippet)
                return comp.summary, True
        except Exception as e:
            comp = ObservationCompiler.compile_browser(url, url, f"Could not fetch full body: {e}")
            return comp.summary, False

    elif tool_name in ["fetch_news", "news"]:
        cat = args.get("category") or "tech"
        if cat in ["defense", "defence"]: cat = "defence"
        arts = fetch_category_news(cat, max_items=2)
        if arts:
            lines = [f"Found {len(arts)} breaking stories in {cat.upper()}:"]
            for a in arts:
                lines.append(f"• {a['title']}\n  Source: {a['source']} | Link: {a['link']}")
            return "\n".join(lines), True
        return f"No breaking news found for category '{cat}'. Try 'tech', 'defence', or 'physics'.", False

    return f"Unknown tool: {tool_name}", False

# --- Model Health & Query ---
def check_model_server():
    try:
        req = urllib.request.Request(SPARK_HEALTH_URL)
        with urllib.request.urlopen(req, timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False

def call_potato_agent(messages, max_tokens=250, temperature=0.1):
    """
    Calls local Spark-X2.5-4B server with strict reasoning separation.
    Suppresses internal chain-of-thought monologues from reaching the user.
    """
    payload = {
        "model": MODEL_ID,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    t0 = time.time()
    try:
        req = urllib.request.Request(
            SPARK_API_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            elapsed = time.time() - t0
            msg = data['choices'][0]['message']
            raw_content = (msg.get('content') or '').strip()
            reasoning = (msg.get('reasoning_content') or '').strip()
            
            # Drop complete and truncated thought blocks, never display reasoning.
            raw_content = re.sub(r'<think>.*?(?:</think>|$)', '', raw_content, flags=re.DOTALL | re.IGNORECASE).strip()
            if "</think>" in raw_content:
                raw_content = raw_content.split("</think>")[-1].strip()
                
            if raw_content:
                content = raw_content
            elif reasoning:
                # If content is empty, model ran out of tokens while thinking.
                # Check if reasoning contained an intended tool call!
                t_name, t_args = extract_tool_call(reasoning)
                if t_name:
                    content = json.dumps({"tool": t_name, "args": t_args})
                else:
                    content = "The model did not finish an answer. Please try a shorter request."
            else:
                content = "Understood. How can I assist you further?"
            
            usage = data.get('usage', {})
            return {
                "success": True,
                "content": content,
                "elapsed": elapsed,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0)
            }
    except Exception as e:
        elapsed = time.time() - t0
        return {
            "success": False,
            "error": str(e),
            "elapsed": elapsed,
            "content": f"[Error connecting to Spark model server: {e}]"
        }

def build_system_prompt_v3(bwm_block="", tools_enabled=True):
    base = "You are PotatoAI 🥔, an ultra-fast local computer agent powered by PotatoClaw V3 architecture."
    rules = [
        "Be concise, clear, and direct in 1-2 sentences.",
        "CRITICAL: Output your response directly. Do NOT output internal monologues, thinking steps, or self-dialogue.",
    ]
    if tools_enabled:
        rules.append("You have tools: browser(url), read_file(path), run_command(command), fetch_news(category).")
        rules.append("To call a tool, output ONLY: `{\"tool\": \"tool_name\", \"args\": {\"param\": \"val\"}}`.")
        rules.append("Example: User: read README.md -> {\"tool\": \"read_file\", \"args\": {\"path\": \"README.md\"}}")
        rules.append("Example: User: get defence news -> {\"tool\": \"fetch_news\", \"args\": {\"category\": \"defence\"}}")
    
    prompt = f"{base}\n" + "\n".join(f"- {r}" for r in rules)
    if bwm_block:
        prompt += f"\n\n{bwm_block}"
    return prompt

def get_system_stats():
    vram = "N/A"
    try:
        cmd = ['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        if r.returncode == 0:
            parts = [x.strip() for x in r.stdout.strip().split(',')]
            vram = f"{parts[0]} / {parts[1]} MiB"
    except Exception:
        pass

    ram = "N/A"
    try:
        import psutil
        mem = psutil.virtual_memory()
        used = round((mem.total - mem.available) / (1024 * 1024 * 1024), 2)
        tot = round(mem.total / (1024 * 1024 * 1024), 2)
        ram = f"{used} / {tot} GB ({mem.percent}%)"
    except Exception:
        pass

    return {"vram": vram, "ram": ram}

# --- Interactive Chat Loop with Rule Zero & V3 Architecture ---
def run_interactive_chat():
    bwm = BoundedWorkingMemory(max_total_chars=850)
    verifier = DeterministicVerifier()
    failure_store = FailureMemoryStore()
    loop_detector = LoopDetector(max_identical_repeats=3)
    tools_enabled = True
    history = []
    
    print(f"\n{CYAN}{BOLD}==================================================================={RESET}")
    print(f"{CYAN}{BOLD}   🥔 POTATOCLAW V3 AI AGENT CHAT (GRAPH-LLM & BWM ARCHITECTURE)  {RESET}")
    print(f"{CYAN}{BOLD}==================================================================={RESET}")
    print(f" {DIM}Hardware: GTX 1650 (4GB VRAM) | Context: 2048 Tokens | Zero Cloud{RESET}")
    print(f" {DIM}Rule Zero: Direct tool execution enabled (0.05s latency){RESET}")
    
    server_online = check_model_server()
    if server_online:
        print(f" {GREEN}[✔] Local Model Server: ONLINE (http://127.0.0.1:11435/v1){RESET}")
    else:
        print(f" {YELLOW}[!] Local Model Server: OFFLINE{RESET}")
        print(f" {DIM}    Tip: Start the model server in PowerShell with:{RESET}")
        print(f"    {BOLD}.\\scripts\\start-spark-potato.ps1{RESET}\n")

    print(f"{DIM} Commands: /reset, /stats, /bwm, /tools, /news [cat], /help, /exit{RESET}")
    print(f"{CYAN}-------------------------------------------------------------------{RESET}\n")

    while True:
        try:
            user_input = input(f"{GREEN}{BOLD}You 👤 > {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{CYAN}Goodbye! 🥔{RESET}")
            break

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in ["/exit", "/quit", "/q", "exit", "quit"]:
            print(f"\n{CYAN}Exiting Potato AI Agent Chat. Keep crunching! 🥔{RESET}")
            break

        elif cmd in ["/reset", "/clear", "/c"]:
            bwm.clear()
            history.clear()
            loop_detector.reset()
            purge_all_caches(verbose=False)
            reset_llama_server_kv_cache()
            print(f"{YELLOW}[✔] PotatoClaw V3 BWM, loop memory, and KV slots cleared. Fresh start!{RESET}\n")
            continue

        elif cmd in ["/stats", "/s"]:
            stats = get_system_stats()
            b_block = bwm.format_prompt_block()
            print(f"\n{CYAN}--- PotatoClaw V3 System & Architectural Stats ---{RESET}")
            print(f" GPU VRAM       : {stats['vram']}")
            print(f" System RAM     : {stats['ram']}")
            print(f" Context Budget : Hard cap <= 2048 Tokens")
            print(f" BWM Active Size: {len(b_block)} / 850 chars")
            print(f" Protected Facts: {len(bwm.protected_keys)}")
            print(f" Loop Breaker   : Active (Max 3 repeats)")
            print(f" History Turns  : {len(history)} turns active\n")
            continue

        elif cmd in ["/bwm", "/bmw", "/memory"]:
            b_block = bwm.format_prompt_block()
            print(f"\n{CYAN}--- PotatoClaw V3 Bounded Working Memory (BWM) ---{RESET}")
            print(b_block if b_block else "BWM State is currently empty.")
            print(f"Budget: {len(b_block)} / 850 characters (Strictly Bounded)\n")
            continue

        elif cmd in ["/tools", "/t"]:
            tools_enabled = not tools_enabled
            state_str = "ENABLED" if tools_enabled else "DISABLED"
            print(f"{YELLOW}[✔] Tool execution is now {state_str}.{RESET}\n")
            continue

        elif cmd.startswith("/news"):
            parts = user_input.split()
            cat = parts[1].lower() if len(parts) > 1 else "tech"
            if cat not in ["tech", "defence", "physics"]:
                cat = "tech"
            print(f"\n{CYAN}[*] Fetching breaking stories in '{cat.upper()}'...{RESET}")
            arts = fetch_category_news(cat, max_items=2)
            if arts:
                for a in arts:
                    print(f" {BOLD}• {a['title']}{RESET}")
                    print(f"   {DIM}Source: {a['source']} | URL: {a['link']}{RESET}")
            else:
                print(f" [!] No stories found.")
            print()
            continue

        elif cmd in ["/help", "/h", "/?"]:
            print(f"\n{CYAN}--- Potato AI V3 Chat Commands ---{RESET}")
            print(f"  {BOLD}/reset{RESET}       : Clear BWM state and reset model KV memory slot")
            print(f"  {BOLD}/stats{RESET}       : Display VRAM, RAM, and BWM context stats")
            print(f"  {BOLD}/bwm{RESET}         : Inspect active Bounded Working Memory block")
            print(f"  {BOLD}/tools{RESET}       : Toggle agent tool calling (run_command, read_file, news)")
            print(f"  {BOLD}/news [cat]{RESET}  : Query breaking news (tech / defence / physics)")
            print(f"  {BOLD}/exit{RESET}        : Exit chat\n")
            continue

        # RULE ZERO FAST-PATH: Intercept direct tool commands before neural invocation
        direct_tool, direct_args = intercept_direct_action(user_input)
        if direct_tool and tools_enabled:
            t0_fast = time.time()
            print(f"\n{YELLOW}⚙️ Executing Tool (Rule Zero Direct): {BOLD}{direct_tool}{RESET} with args: {direct_args}")
            tool_result, is_verified = execute_tool(direct_tool, direct_args, verifier=verifier)
            ver_badge = f"{GREEN}[✔ VERIFIED]{RESET}" if is_verified else f"{YELLOW}[FAILED]{RESET}"
            print(f"{DIM}Observation ({len(tool_result)} chars) {ver_badge}:{RESET}\n{tool_result}")
            
            bwm.add_fact(f"Completed {direct_tool}: {tool_result[:60]}")
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": f"Here is what was found:\n{tool_result[:250]}"})
            lat_ms = round((time.time() - t0_fast) * 1000)
            print(f"\n{DIM}[{lat_ms}ms | 0 tokens (Rule Zero)]{RESET}\n")
            continue

        # Add user turn to BWM
        bwm.add_fact(f"User asked: {user_input[:80]}")

        # Build Context with BWM prompt block (keep last 2 conversational turns only)
        bwm_block = bwm.format_prompt_block()
        sys_prompt = build_system_prompt_v3(bwm_block, tools_enabled)
        
        recent_history = history[-2:]
        messages = [{"role": "system", "content": sys_prompt}]
        messages.extend(recent_history)
        messages.append({"role": "user", "content": user_input})

        print(f"\n{CYAN}{BOLD}PotatoAI 🥔 > {RESET}", end="", flush=True)
        resp = call_potato_agent(messages)

        if not resp["success"]:
            print(f"{RED}{resp['content']}{RESET}\n")
            continue

        agent_text = resp["content"]
        
        # Tool Handling with V3 Loop Detector and Verifier
        tool_call_handled = False
        if tools_enabled:
            tool_name, tool_args = extract_tool_call(agent_text)
            if tool_name:
                is_loop, loop_msg = loop_detector.record_action(tool_name, tool_args)
                if is_loop:
                    print(f"\n{RED}🛑 LOOP DETECTED: {loop_msg}{RESET}")
                    bwm.add_protected_fact(f"LOOP DETECTED on {tool_name}. Halting repeat.")
                else:
                    print(f"\n{YELLOW}⚙️ Executing Tool (V3 Verified): {BOLD}{tool_name}{RESET} with args: {tool_args}")
                    tool_result, is_verified = execute_tool(tool_name, tool_args, verifier=verifier)
                    ver_badge = f"{GREEN}[✔ VERIFIED]{RESET}" if is_verified else f"{YELLOW}[FAILED]{RESET}"
                    print(f"{DIM}Observation ({len(tool_result)} chars) {ver_badge}:{RESET}\n{tool_result}")
                    
                    if is_verified:
                        bwm.add_fact(f"Completed {tool_name}: {tool_result[:60]}")
                    else:
                        failure_store.record_failure("chat_turn", f"{tool_name}({tool_args})", tool_result[:80])
                        bwm.add_fact(f"Tool {tool_name} failed: {tool_result[:60]}")
                    
                    clean_agent_call = re.sub(r'<tool_call>.*?</tool_call>', '', agent_text, flags=re.DOTALL).strip()
                    if not clean_agent_call or clean_agent_call == "<tool_call>":
                        clean_agent_call = f"I executed {tool_name} with {tool_args}."
                        
                    follow_up_msgs = [
                        {"role": "system", "content": build_system_prompt_v3(bwm.format_prompt_block(), False)},
                        {"role": "user", "content": user_input},
                        {"role": "assistant", "content": clean_agent_call},
                        {"role": "user", "content": f"Tool output was:\n{tool_result}\nProvide a concise 1-2 sentence summary to the user."}
                    ]
                    print(f"\n{CYAN}{BOLD}PotatoAI 🥔 > {RESET}", end="", flush=True)
                    final_resp = call_potato_agent(follow_up_msgs)
                    if final_resp["success"]:
                        agent_text = final_resp["content"]
                        print(agent_text)
                        tool_call_handled = True
                    
        if not tool_call_handled:
            clean_display = re.sub(r'<tool_call>.*?</tool_call>', '', agent_text, flags=re.DOTALL).strip()
            if clean_display == "<tool_call>" or not clean_display:
                clean_display = "I am ready. Please specify what you would like me to do."
            print(clean_display)

        ms = round(resp['elapsed'] * 1000)
        toks = resp.get('total_tokens', 0)
        tok_info = f" | {toks} tokens" if toks > 0 else ""
        print(f"\n{DIM}[{ms}ms{tok_info}]{RESET}\n")

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": agent_text})

def test_single_turn(prompt):
    """Executes a single test turn without entering interactive mode."""
    bwm = BoundedWorkingMemory()
    bwm.add_fact(prompt)
    sys_prompt = build_system_prompt_v3(bwm.format_prompt_block(), True)
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": prompt}
    ]
    resp = call_potato_agent(messages)
    print(json.dumps({
        "success": resp["success"],
        "content": resp["content"],
        "elapsed_sec": resp["elapsed"],
        "total_tokens": resp.get("total_tokens", 0)
    }, indent=2))
    return resp["success"]

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        prompt = sys.argv[2] if len(sys.argv) > 2 else "Hello PotatoAI, who are you?"
        test_single_turn(prompt)
    else:
        run_interactive_chat()
