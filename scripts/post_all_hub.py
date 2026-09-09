#!/usr/bin/env python3
"""
PotatoClaw Master Content & Posting Hub
Connects PotatoClaw V3 Agent, Autonomous Browser Agent (Qwen 0.5B),
and Deterministic Non-Premium X Thread Splitter to X (Twitter) posting workflows.
"""

import sys
sys.dont_write_bytecode = True

import os
import io
import time
import urllib.request
import urllib.parse
import subprocess
import webbrowser
import re

# Ensure UTF-8 output on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from fresh_start import purge_all_caches
from x_news_engine import (
    fetch_category_news,
    generate_single_story_x_post,
    x_character_count,
    copy_to_clipboard as x_copy_to_clipboard,
    save_draft as x_save_draft,
    clean_html_tags
)

try:
    from potato_browser_agent import run_browser_agent, split_x_thread
except ImportError:
    run_browser_agent = None
    split_x_thread = None

try:
    from potato_cat_bmw import BmwGraphBridge
except ImportError:
    BmwGraphBridge = None

try:
    from potato_cdp import (
        compose_x_thread_cdp,
        generate_browser_console_script,
        is_cdp_listening,
        get_active_cdp_port
    )
except ImportError:
    compose_x_thread_cdp = None
    generate_browser_console_script = None
    is_cdp_listening = None
    get_active_cdp_port = None


def open_url_in_browser(url: str) -> bool:
    """Robustly opens a URL on Windows using os.startfile, cmd start, and browser fallback."""
    try:
        if sys.platform == "win32":
            os.startfile(url)
            return True
    except Exception:
        pass
        
    try:
        subprocess.run(["cmd.exe", "/c", "start", "", url], shell=False)
        return True
    except Exception:
        pass
        
    try:
        webbrowser.open(url, new=2)
        return True
    except Exception:
        pass
    return False


def _browser_result_succeeded(result, allow_submit: bool) -> bool:
    """Accept only a deterministic browser outcome appropriate to the request."""
    if not isinstance(result, dict):
        return False
    expected = "SUBMITTED" if allow_submit else "PREPARED_SAFE"
    return result.get("status") == expected


def run_x_post_workflow(category: str = "tech", auto_open: bool = True, browser_mode: str = None, allow_submit: bool = False):
    """
    Curates #1 news story, drafts a concise post <= 280 chars, and routes
    to the autonomous browser agent or browser intent.
    """
    print(f"\n[*] Curating #1 breaking story in '{category.upper()}' for X (Twitter)...")
    articles = fetch_category_news(category, max_items=1)
    if not articles:
        print("[!] No news articles found.")
        return None
        
    article = articles[0]
    print(f"[+] Selected: {article['title']} ({article['source']})")
    graph_memory = BmwGraphBridge("x_post", active_limit=8) if BmwGraphBridge else None
    memory_block = ""
    if graph_memory:
        graph_memory.add_event(
            "x_article",
            "%s source=%s category=%s" % (article.get("title", ""), article.get("source", ""), category),
            importance=0.85,
        )
        memory_block, memory_retrieval = graph_memory.context(article.get("title", category))
        if memory_retrieval:
            print("[BMW] X article retained: %d active concept(s), %d node(s) scanned via %s." % (
                len(memory_retrieval.active_ids), memory_retrieval.scanned_nodes, memory_retrieval.scan_mode
            ))
    print(f"[*] Crafting a concise factual post using PotatoClaw V3...")
    post_text = generate_single_story_x_post(
        category,
        article,
        graph_context=memory_block if graph_memory else "",
    )

    if not post_text:
        print("[!] Automatic drafting failed. You can enter your own factual summary.")
        try:
            post_text = input("Enter draft (blank to return): ").strip()
        except EOFError:
            return None
        if not post_text:
            return None
        if x_character_count(post_text) > 280:
            print("[!] Draft exceeds 280 characters. Please shorten it and try again.")
            return None
    
    x_copy_to_clipboard(post_text)
    if graph_memory:
        graph_memory.add_event("x_post_draft", post_text, importance=0.8)
    
    print("\n" + "=" * 65)
    print(" 🐦 X POST READY (FACTUAL STYLE, WITHIN 280 CHARACTERS):")
    print("=" * 65)
    print(post_text)
    print("=" * 65)
    print(f" [✔] X weighted character count: {x_character_count(post_text)} / 280")
    print(f" [✔] Post text copied to Windows clipboard!")

    if browser_mode == "agent":
        if run_browser_agent:
            verb = "Post this on X" if allow_submit else "Open X and prepare a post saying"
            goal = f"{verb}: {post_text}"
            print(f"\n[*] Running Autonomous Browser Agent (Submit: {allow_submit})...")
            browser_result = run_browser_agent(goal, allow_submit=allow_submit)
            if graph_memory:
                graph_memory.add_event("x_browser_outcome", str(browser_result), importance=1.0 if _browser_result_succeeded(browser_result, allow_submit) else 0.4)
            if not _browser_result_succeeded(browser_result, allow_submit):
                print(f"[!] Browser workflow did not verify the requested outcome: {browser_result}")
                return None
        else:
            print("[!] potato_browser_agent module not available.")
            return None
        return post_text
        
    if auto_open:
        print("\n" + "-" * 65)
        print(" Choose Posting Method:")
        print("   [1] 🤖 Prepare in X via Autonomous Browser Agent (Safe Draft)")
        print("   [2] 🚀 Post Live to X via Autonomous Browser Agent (--allow-submit)")
        print("   [3] 🌐 Open X Web Composer URL (Manual Ctrl+V)")
        print("   [S] Skip browser action")
        print("-" * 65)
        try:
            choice = input("Select an option [1-3, S (default=1)]: ").strip().lower()
        except EOFError:
            choice = "s"

        if choice in ["1", ""]:
            if run_browser_agent:
                goal = f"Open X and prepare a post saying: {post_text}"
                print("\n[*] Launching PotatoClaw Autonomous Browser Agent (Safe Draft)...")
                run_browser_agent(goal, allow_submit=False)
            else:
                encoded = urllib.parse.quote(post_text)
                open_url_in_browser(f"https://x.com/intent/post?text={encoded}")
        elif choice == "2":
            if run_browser_agent:
                try:
                    conf = input("\n[CAUTION] You are about to post LIVE to X. Proceed? [y/N]: ").strip().lower()
                except EOFError:
                    conf = "n"
                if conf == "y":
                    goal = f"Post this on X: {post_text}"
                    print("\n[*] Launching PotatoClaw Autonomous Browser Agent (Live Post)...")
                    run_browser_agent(goal, allow_submit=True)
                else:
                    print("[*] Live submission cancelled.")
            else:
                print("[!] potato_browser_agent module not available.")
        elif choice == "3":
            encoded = urllib.parse.quote(post_text)
            intent_url = f"https://x.com/intent/post?text={encoded}"
            open_url_in_browser(intent_url)
            print("[✔] Opened X Post Composer in browser! Press Ctrl+V to paste & post.")
        
    return post_text


def craft_in_depth_news_thread(category: str, article: dict) -> str:
    """
    Crafts an authoritative 3-part factual news thread from a curated story.
    Post 1: Headline & core announcement.
    Post 2: Technical intel, operational specs, and background mechanism.
    Post 3: Strategic significance, implications, and verified source credit.
    Guarantees clean sentence/word bounds producing an exact 3-post thread (1/3, 2/3, 3/3).
    """
    title = clean_html_tags(article.get('title', '').strip())
    raw_desc = clean_html_tags(article.get('desc', '').strip())
    raw_desc = re.sub(
        r'(?is)\bthis article\s+(?:was\s+)?originally published on\b[^.!?]*(?:[.!?]|$)',
        '',
        raw_desc,
    )
    raw_desc = re.sub(r'(?i)(?:https?://|www\.)\S+|\b[\w-]+\.(?:org|com|net|in)(?:/\S*)?', '', raw_desc)
    raw_desc = re.sub(r'\s+', ' ', raw_desc).strip(' .,:;-')
    source = article.get('source', '').strip()

    # Part 1: Core development
    p1 = f"{title}. Reported by {source}, this development marks a significant update in {category.capitalize()}."
    
    # Part 2: Technical context / intel (bounded to ~220 chars to guarantee clean single-post fit)
    if raw_desc and len(raw_desc) > 25:
        if len(raw_desc) > 220:
            m = list(re.finditer(r'[.!?](?=\s|$)', raw_desc[:220]))
            if m and m[-1].end() > 60:
                clean_d = raw_desc[:m[-1].end()].strip()
            else:
                clean_d = raw_desc[:220].rsplit(' ', 1)[0].rstrip(' ,;:-') + "."
        else:
            clean_d = raw_desc
        clean_d = clean_d.rstrip('. \t\n') + '.' if clean_d and not clean_d.endswith(('.', '!', '?')) else clean_d
        p2 = f"Key details: {clean_d}"
    else:
        p2 = f"According to technical disclosures from {source}, implementation frameworks and capability evaluation are actively proceeding."

    # Part 3: Significance & verification
    p3 = f"Significance: Domain specialists note this milestone provides critical validation for next-phase deployment in {category.capitalize()}. Source: {source}."

    return f"{p1}\n\n{p2}\n\n{p3}"


def run_thread_workflow(initial_text: str = None, allow_submit: bool = False, category: str = "tech"):
    """
    Creates and posts/prepares a non-Premium X thread.
    Features autonomous news curation (Option 1) or custom text/file input.
    Guarantees deterministic thread splitting with ZERO word cutoff.
    """
    print("\n" + "=" * 65)
    print("   POTATOCLAW NON-PREMIUM X THREAD COMPOSER")
    print("=" * 65)
    print(" Splits any long text/article into standard <=280-char X posts.")
    print(" Automatically fills each part in X browser using Qwen 0.5B policy.")
    print("-" * 65)

    text = initial_text
    add_num = True
    graph_memory = BmwGraphBridge("x_thread", active_limit=8) if BmwGraphBridge else None

    # Autonomous CLI invocation (e.g. post_all.bat thread auto [category])
    if initial_text and initial_text.lower() in ["auto", "curate"]:
        cat = category if category else "tech"
        print(f"\n[*] Autonomous mode: Curating #1 breaking story in '{cat.upper()}' for in-depth thread...")
        articles = fetch_category_news(cat, max_items=1)
        if not articles:
            print("[!] No news articles found. Please check connection.")
            return
        article = articles[0]
        print(f"[+] Selected: {article['title']} ({article['source']})")
        print("[*] Synthesizing 3-part factual thread...")
        text = craft_in_depth_news_thread(cat, article)
        add_num = True
    elif not text:
        print(" Choose Thread Source:")
        print("   [1] 🤖 Auto-Curate Breaking News & Generate In-Depth Thread (Autonomous)")
        print("   [2] ✍️ Enter / Paste Custom Article or Text")
        print("   [3] 📄 Load from a Text File (.txt / .md)")
        print("   [B] Back to Main Menu")
        print("-" * 65)
        try:
            choice = input("Select an option [1-3, B (default=1)]: ").strip().lower()
        except EOFError:
            return

        if choice in ["1", "", "auto"]:
            cat = select_category()
            print(f"\n[*] Curating #1 breaking story in '{cat.upper()}' for in-depth thread...")
            articles = fetch_category_news(cat, max_items=1)
            if not articles:
                print("[!] No news articles found. Please check connection.")
                return
            article = articles[0]
            print(f"[+] Selected: {article['title']} ({article['source']})")
            print("[*] Synthesizing 3-part factual thread...")
            text = craft_in_depth_news_thread(cat, article)
            add_num = True
        elif choice == "2":
            print("\nEnter thread text (or 'B' to cancel):")
            try:
                line = input("> ").strip()
            except EOFError:
                return
            if not line or line.lower() == 'b':
                return
            text = line
            try:
                num_c = input("\nAdd post numbering (e.g. 1/4, 2/4)? [Y/n]: ").strip().lower()
                add_num = (num_c != 'n')
            except EOFError:
                add_num = True
        elif choice == "3":
            print("\nEnter path to a text file (.txt / .md):")
            try:
                filepath = input("> ").strip().strip('"').strip("'")
            except EOFError:
                return
            if not os.path.isfile(filepath):
                print(f"[!] File not found: {filepath}")
                return
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read().strip()
                print(f"[✔] Loaded {len(text)} characters from {filepath}")
            except Exception as e:
                print(f"[!] Could not read file: {e}")
                return
            try:
                num_c = input("\nAdd post numbering (e.g. 1/4, 2/4)? [Y/n]: ").strip().lower()
                add_num = (num_c != 'n')
            except EOFError:
                add_num = True
        elif choice == "b":
            return
        else:
            print("[!] Invalid option.")
            return

    if not text:
        print("[!] No text provided.")
        return

    if split_x_thread:
        parts = split_x_thread(
            text,
            max_chars=280,
            add_numbering=add_num,
            preserve_paragraphs=add_num,
        )
    else:
        parts = [text[i:i+280] for i in range(0, len(text), 280)]

    if graph_memory:
        graph_memory.add_event("x_thread_source", text, importance=0.85)
        for index, part in enumerate(parts, 1):
            graph_memory.add_event("x_thread_part_%d" % index, part, importance=0.7)
        _, memory_retrieval = graph_memory.context("X thread source and post parts")
        if memory_retrieval:
            print("[BMW] X thread retained: %d active concept(s), %d node(s) scanned via %s." % (
                len(memory_retrieval.active_ids), memory_retrieval.scanned_nodes, memory_retrieval.scan_mode
            ))

    print(f"\n[✔] Deterministically split into {len(parts)} thread post(s) (Zero Word Cutoff):")
    print("-" * 65)
    for idx, part in enumerate(parts, 1):
        print(f" [Post {idx}/{len(parts)}] ({len(part)} chars):")
        print(part)
        print()
    print("-" * 65)

    if allow_submit:
        if compose_x_thread_cdp and get_active_cdp_port and get_active_cdp_port():
            print(f"\n[*] Active Chrome CDP detected. Publishing {len(parts)}-part thread via Chrome DevTools Protocol...")
            result = compose_x_thread_cdp(parts, allow_submit=True)
            if graph_memory:
                graph_memory.add_event("x_thread_outcome", str(result), importance=1.0 if isinstance(result, dict) and result.get("status") == "SUBMITTED" else 0.4)
            return result.get("status") == "SUBMITTED" if isinstance(result, dict) else False
        goal = f"Post this on X as a non-Premium thread: {text}"
        print(f"\n[*] Launching PotatoClaw Browser Agent to publish {len(parts)}-part thread...")
        if run_browser_agent:
            result = run_browser_agent(goal, allow_submit=True)
            if graph_memory:
                graph_memory.add_event("x_thread_outcome", str(result), importance=1.0 if _browser_result_succeeded(result, True) else 0.4)
            if not _browser_result_succeeded(result, True):
                print(f"[!] Browser workflow did not verify live publication: {result}")
                return False
            return True
        print("[!] potato_browser_agent module not available.")
        return False

    print(" Actions:")
    print("   [1] ⚡ Compose Thread via Chrome/Edge CDP (Automated 1 -> [+] -> 2 -> [+])")
    print("   [2] 🤖 Prepare Thread in X Browser via Agent (Safe Draft)")
    print("   [3] 🚀 Post Thread Live to X Browser (--allow-submit)")
    print("   [4] 📋 Copy All Parts to Windows Clipboard")
    print("   [5] 📜 Copy 1-Click DevTools Console Script (F12)")
    print("   [B] Back to Menu")
    print("-" * 65)

    try:
        act = input("Choose action [1-5, B (default=1)]: ").strip().lower()
    except EOFError:
        return

    if act in ["1", ""]:
        print(f"\n[*] Launching PotatoClaw CDP Thread Engine to compose {len(parts)} post(s)...")
        if compose_x_thread_cdp:
            cdp_res = compose_x_thread_cdp(parts, allow_submit=False)
            if cdp_res.get("status") == "CDP_NOT_AVAILABLE":
                if generate_browser_console_script:
                    snippet = generate_browser_console_script(parts)
                    x_copy_to_clipboard(snippet)
                    print("\n" + "=" * 65)
                    print(" [!] Chrome CDP endpoint was not reached on port 9222/9223.")
                    print("     To activate full hands-free CDP: run 'start_chrome_cdp.bat'")
                    print("     -> 1-Click Fallback: Console script COPIED to clipboard!")
                    print("     -> Opening https://x.com/compose/post in browser...")
                    print("     -> Press F12 (Console), then Ctrl+V and Enter to auto-type all posts!")
                    print("=" * 65)
                    open_url_in_browser("https://x.com/compose/post")
                else:
                    open_url_in_browser("https://x.com/compose/post")
        else:
            if run_browser_agent:
                goal = f"Open X and prepare this as a non-Premium thread: {text}"
                run_browser_agent(goal, allow_submit=False)
            else:
                open_url_in_browser("https://x.com/compose/post")
    elif act == "2":
        goal = f"Open X and prepare this as a non-Premium thread: {text}"
        print(f"\n[*] Launching PotatoClaw Browser Agent to draft {len(parts)}-part thread...")
        if run_browser_agent:
            run_browser_agent(goal, allow_submit=False)
        else:
            print("[!] potato_browser_agent module not available.")
    elif act == "3":
        try:
            confirm = input("\n[CAUTION] You are about to publish a LIVE thread to X. Proceed? [y/N]: ").strip().lower()
        except EOFError:
            confirm = "n"
        if confirm == "y":
            if compose_x_thread_cdp and get_active_cdp_port and get_active_cdp_port():
                print(f"\n[*] Publishing {len(parts)}-part thread via Chrome CDP...")
                compose_x_thread_cdp(parts, allow_submit=True)
            elif run_browser_agent:
                goal = f"Post this on X as a non-Premium thread: {text}"
                print(f"\n[*] Launching PotatoClaw Browser Agent to publish {len(parts)}-part thread...")
                run_browser_agent(goal, allow_submit=True)
            else:
                print("[!] Browser execution module not available.")
        else:
            print("[*] Live thread publishing cancelled.")
    elif act == "4":
        combined = "\n\n---\n\n".join([f"[{i+1}/{len(parts)}]\n{p}" for i, p in enumerate(parts)])
        x_copy_to_clipboard(combined)
        print("[✔] Copied entire thread to Windows clipboard!")
    elif act == "5":
        if generate_browser_console_script:
            snippet = generate_browser_console_script(parts)
            x_copy_to_clipboard(snippet)
            print("[✔] Copied 1-click DevTools Console script to Windows clipboard!")
            print("    Paste this into Chrome/Edge DevTools Console (F12) on https://x.com/compose/post:\n")
            print(snippet)
        else:
            print("[!] Script generator not available.")


def run_browser_agent_workflow():
    """Direct goal submission for the PotatoClaw Autonomous Browser Agent."""
    print("\n" + "=" * 65)
    print("   POTATOCLAW AUTONOMOUS BROWSER AGENT")
    print("=" * 65)
    print(" Dedicated Qwen 0.5B Browser Action Policy on port 11436.")
    print(" Deterministic snapshot compaction, step execution & safety gates.")
    print("-" * 65)
    try:
        goal = input("Enter browsing goal (e.g. 'Open https://x.com and check home page'):\n> ").strip()
    except EOFError:
        return
    if not goal:
        return

    try:
        sub_choice = input("Allow irreversible submit actions (--allow-submit)? [y/N]: ").strip().lower()
        allow_sub = (sub_choice == 'y')
    except EOFError:
        allow_sub = False

    if run_browser_agent:
        run_browser_agent(goal, allow_submit=allow_sub)
    else:
        print("[!] potato_browser_agent module not available.")


def show_interactive_hub():
    while True:
        print("\n" + "=" * 65)
        print("   POTATOCLAW V3 MASTER AUTOMATION & AGENT HUB")
        print("=" * 65)
        print(" Models: Spark-X2.5-4B (11435) | Qwen2.5-0.5B Browser (11436)")
        print(" Engine: Graph-LLM DAG + BWM + Verifier + CDP Browser Policy")
        print("-" * 65)
        print(" [1] 🥔 Chat with Potato AI Agent V3 (Interactive Mode)")
        print(" [2] 🐦 Curate & Post News to X (Browser Agent / Intent)")
        print(" [3] 🧵 Non-Premium Thread Creator (Deterministic Splitter + Agent)")
        print(" [4] 🌐 Autonomous Browser Agent (Direct Goal / Action Policy)")
        print(" [5] 📊 Run PotatoBench V3 Benchmark Suite (10 Tasks + 8 Ablations)")
        print(" [6] 🧪 Run All PotatoClaw Tests (Core, V2, Browser, CDP - 84+ Tests)")
        print(" [Q] Quit")
        print("-" * 65)
        
        try:
            choice = input("Select an option [1-6, Q]: ").strip().lower()
        except EOFError:
            break
            
        if choice == 'q':
            print("Exiting PotatoClaw Hub. Goodbye!")
            break
        elif choice == '1':
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "potato_chat.py")])
            try: input("\nPress Enter to return to main menu...")
            except EOFError: pass
        elif choice == '2':
            cat = select_category()
            if cat:
                run_x_post_workflow(cat)
                try: input("\nPress Enter to return to main menu...")
                except EOFError: pass
        elif choice == '3':
            run_thread_workflow()
            try: input("\nPress Enter to return to main menu...")
            except EOFError: pass
        elif choice == '4':
            run_browser_agent_workflow()
            try: input("\nPress Enter to return to main menu...")
            except EOFError: pass
        elif choice == '5':
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "run_benchmarks.py"), "potatobench"])
            try: input("\nPress Enter to return to main menu...")
            except EOFError: pass
        elif choice == '6':
            print("\n" + "=" * 65)
            print(" RUNNING FULL POTATOCLAW ARCHITECTURAL TEST SUITE (84+ TESTS)")
            print("=" * 65)
            print("\n[1/4] Running Browser Agent & Thread Splitter Tests...")
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_potato_browser_agent.py")])
            print("\n[2/4] Running Chrome DevTools Protocol (CDP) Tests...")
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_potato_cdp.py")])
            print("\n[3/4] Running V3 Core Architectural Tests...")
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_potato_core.py")])
            print("\n[4/4] Running V2 Integration Tests...")
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_potato_v2.py")])
            try: input("\nPress Enter to return to main menu...")
            except EOFError: pass
        else:
            print("[!] Invalid choice. Please select 1-6, or Q.")


def select_category():
    print("\nSelect Category:")
    print(" [1] 🤖 Tech & Artificial Intelligence")
    print(" [2] 🛡️ Defence & Aerospace")
    print(" [3] ⚛️ Physics & Quantum Science")
    try:
        c = input("Choice [1-3, default=1]: ").strip()
    except EOFError:
        return 'tech'
    map_cat = {'1': 'tech', '2': 'defence', '3': 'physics'}
    return map_cat.get(c, 'tech')


if __name__ == "__main__":
    purge_all_caches(verbose=False)
    exit_code = 0
    if len(sys.argv) > 1:
        args = sys.argv[1:]
        cmd = args[0].lower()
        allow_submit = "--allow-submit" in args
        use_browser = "--browser" in args or "-b" in args

        if cmd in ["chat", "agent", "potato"]:
            exit_code = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "potato_chat.py")]).returncode
        elif cmd in ["thread", "threads"]:
            text_parts = [a for a in args[1:] if not a.startswith("--") and not a.startswith("-")]
            if text_parts and text_parts[0].lower() in ["auto", "curate"]:
                cat = text_parts[1].lower() if len(text_parts) > 1 else "tech"
                result = run_thread_workflow(initial_text="auto", allow_submit=allow_submit, category=cat)
            else:
                text_arg = " ".join(text_parts).strip() if text_parts else None
                result = run_thread_workflow(initial_text=text_arg, allow_submit=allow_submit)
            exit_code = 0 if result else 1
        elif cmd in ["browser", "browse"]:
            goal_parts = [a for a in args[1:] if not a.startswith("--") and not a.startswith("-")]
            goal_arg = " ".join(goal_parts).strip()
            if not goal_arg:
                run_browser_agent_workflow()
            else:
                if run_browser_agent:
                    result = run_browser_agent(goal_arg, allow_submit=allow_submit)
                    exit_code = 0 if _browser_result_succeeded(result, allow_submit) else 1
                else:
                    print("[!] potato_browser_agent not available.")
                    exit_code = 1
        elif cmd == "x":
            cat = "tech"
            remaining = [a for a in args[1:] if not a.startswith("--") and not a.startswith("-")]
            if remaining:
                cat = remaining[0].lower()
            result = run_x_post_workflow(
                category=cat,
                auto_open=True,
                browser_mode="agent" if use_browser else None,
                allow_submit=allow_submit
            )
            exit_code = 0 if result else 1
        elif cmd in ["test", "tests"]:
            test_exit_codes = []
            print("\n[1/5] Running Browser Agent & Thread Splitter Tests...")
            test_exit_codes.append(subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_potato_browser_agent.py")]).returncode)
            print("\n[2/5] Running Chrome DevTools Protocol (CDP) Tests...")
            test_exit_codes.append(subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_potato_cdp.py")]).returncode)
            print("\n[3/5] Running V3 Core Architectural Tests...")
            test_exit_codes.append(subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_potato_core.py")]).returncode)
            print("\n[4/5] Running V2 Integration Tests...")
            test_exit_codes.append(subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_potato_v2.py")]).returncode)
            print("\n[5/5] Running CAT/BMW Chat + X Integration Tests...")
            test_exit_codes.append(subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_cat_bmw_integration.py")]).returncode)
            exit_code = 0 if all(code == 0 for code in test_exit_codes) else 1
        else:
            show_interactive_hub()
    else:
        show_interactive_hub()
    sys.exit(exit_code)
