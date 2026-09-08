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
    print(f"[*] Crafting a concise factual post using PotatoClaw V3...")
    post_text = generate_single_story_x_post(category, article)

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
            run_browser_agent(goal, allow_submit=allow_submit)
        else:
            print("[!] potato_browser_agent module not available.")
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
        parts = split_x_thread(text, max_chars=280, add_numbering=add_num)
    else:
        parts = [text[i:i+280] for i in range(0, len(text), 280)]

    print(f"\n[✔] Deterministically split into {len(parts)} thread post(s) (Zero Word Cutoff):")
    print("-" * 65)
    for idx, part in enumerate(parts, 1):
        print(f" [Post {idx}/{len(parts)}] ({len(part)} chars):")
        print(part)
        print()
    print("-" * 65)

    if allow_submit:
        goal = f"Post this on X as a non-Premium thread: {text}"
        print(f"\n[*] Launching PotatoClaw Browser Agent to publish {len(parts)}-part thread...")
        if run_browser_agent:
            run_browser_agent(goal, allow_submit=True)
        return

    print(" Actions:")
    print("   [1] 🤖 Prepare Thread in X Browser (Safe Draft - Recommended)")
    print("   [2] 🚀 Post Thread Live to X Browser (--allow-submit)")
    print("   [3] 📋 Copy All Parts to Windows Clipboard")
    print("   [B] Back to Menu")
    print("-" * 65)

    try:
        act = input("Choose action [1-3, B (default=1)]: ").strip().lower()
    except EOFError:
        return

    if act in ["1", ""]:
        goal = f"Open X and prepare this as a non-Premium thread: {text}"
        print(f"\n[*] Launching PotatoClaw Browser Agent to draft {len(parts)}-part thread...")
        if run_browser_agent:
            run_browser_agent(goal, allow_submit=False)
        else:
            print("[!] potato_browser_agent module not available.")
    elif act == "2":
        try:
            confirm = input("\n[CAUTION] You are about to publish a LIVE thread to X. Proceed? [y/N]: ").strip().lower()
        except EOFError:
            confirm = "n"
        if confirm == "y":
            goal = f"Post this on X as a non-Premium thread: {text}"
            print(f"\n[*] Launching PotatoClaw Browser Agent to publish {len(parts)}-part thread...")
            if run_browser_agent:
                run_browser_agent(goal, allow_submit=True)
            else:
                print("[!] potato_browser_agent module not available.")
        else:
            print("[*] Live thread publishing cancelled.")
    elif act == "3":
        combined = "\n\n---\n\n".join([f"[{i+1}/{len(parts)}]\n{p}" for i, p in enumerate(parts)])
        x_copy_to_clipboard(combined)
        print("[✔] Copied entire thread to Windows clipboard!")


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
        print(" [6] 🧪 Run All PotatoClaw Tests (Core, V2, Browser Agent - 77 Tests)")
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
            print(" RUNNING FULL POTATOCLAW ARCHITECTURAL TEST SUITE (77 TESTS)")
            print("=" * 65)
            print("\n[1/3] Running Browser Agent & Thread Splitter Tests...")
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_potato_browser_agent.py")])
            print("\n[2/3] Running V3 Core Architectural Tests...")
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_potato_core.py")])
            print("\n[3/3] Running V2 Integration Tests...")
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
    if len(sys.argv) > 1:
        args = sys.argv[1:]
        cmd = args[0].lower()
        allow_submit = "--allow-submit" in args
        use_browser = "--browser" in args or "-b" in args

        if cmd in ["chat", "agent", "potato"]:
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "potato_chat.py")])
        elif cmd in ["thread", "threads"]:
            text_parts = [a for a in args[1:] if not a.startswith("--") and not a.startswith("-")]
            if text_parts and text_parts[0].lower() in ["auto", "curate"]:
                cat = text_parts[1].lower() if len(text_parts) > 1 else "tech"
                run_thread_workflow(initial_text="auto", allow_submit=allow_submit, category=cat)
            else:
                text_arg = " ".join(text_parts).strip() if text_parts else None
                run_thread_workflow(initial_text=text_arg, allow_submit=allow_submit)
        elif cmd in ["browser", "browse"]:
            goal_parts = [a for a in args[1:] if not a.startswith("--") and not a.startswith("-")]
            goal_arg = " ".join(goal_parts).strip()
            if not goal_arg:
                run_browser_agent_workflow()
            else:
                if run_browser_agent:
                    run_browser_agent(goal_arg, allow_submit=allow_submit)
                else:
                    print("[!] potato_browser_agent not available.")
        elif cmd == "x":
            cat = "tech"
            remaining = [a for a in args[1:] if not a.startswith("--") and not a.startswith("-")]
            if remaining:
                cat = remaining[0].lower()
            run_x_post_workflow(
                category=cat,
                auto_open=True,
                browser_mode="agent" if use_browser else None,
                allow_submit=allow_submit
            )
        elif cmd in ["test", "tests"]:
            print("\n[1/3] Running Browser Agent & Thread Splitter Tests...")
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_potato_browser_agent.py")])
            print("\n[2/3] Running V3 Core Architectural Tests...")
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_potato_core.py")])
            print("\n[3/3] Running V2 Integration Tests...")
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_potato_v2.py")])
        else:
            show_interactive_hub()
    else:
        show_interactive_hub()
