#!/usr/bin/env python3
"""
PotatoClaw Master Content & Posting Hub
Connects PotatoClaw V2 BMW Agent to X (Twitter) single-story news posting workflows,
benchmarks, and architectural test suites.
"""

import sys
import os
import io
import time
import urllib.request
import urllib.parse
import subprocess
import webbrowser

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
    copy_to_clipboard as x_copy_to_clipboard,
    save_draft as x_save_draft
)

def open_url_in_browser(url):
    """Robustly opens a URL on Windows using os.startfile, cmd start, and chrome fallback."""
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

def run_x_post_workflow(category="tech", auto_open=True):
    print(f"\n[*] Curating #1 breaking story in '{category.upper()}' for X (Twitter)...")
    articles = fetch_category_news(category, max_items=1)
    if not articles:
        print("[!] No news articles found.")
        return None
        
    article = articles[0]
    print(f"[+] Selected: {article['title']} ({article['source']})")
    print(f"[*] Crafting tweet using PotatoClaw V2 BMW model...")
    post_text = generate_single_story_x_post(category, article)
    
    draft_file = x_save_draft(post_text, category, article['title'])
    x_copy_to_clipboard(post_text)
    
    print("\n" + "=" * 65)
    print(" 🐦 X (TWITTER) POST READY (STRICTLY UNDER 280 CHARACTERS):")
    print("=" * 65)
    print(post_text)
    print("=" * 65)
    print(f" [✔] Post text copied to Windows clipboard!")
    if draft_file:
        print(f" [✔] Draft saved to: {draft_file}")
        
    if auto_open:
        try:
            choice = input("\nOpen X Web Composer now? [Y/n]: ").strip().lower()
            if choice != 'n':
                encoded = urllib.parse.quote(post_text)
                intent_url = f"https://x.com/intent/post?text={encoded}"
                open_url_in_browser(intent_url)
                print("[✔] Opened X Post Composer in browser! Press Ctrl+V to paste & post.")
        except EOFError:
            pass
        
    return post_text

def show_interactive_hub():
    while True:
        print("\n" + "=" * 65)
        print("   POTATOCLAW MASTER POSTING & CONTENT AUTOMATION HUB")
        print("=" * 65)
        print(" Model: Spark-X2.5-4B (Q4_K_M) | GPU: GTX 1650 | Context: 2048")
        print("-" * 65)
        print(" [1] 🐦 Post Single-Story News to X (Tech / Defence / Physics)")
        print(" [2] 📊 Run PotatoClaw V2 Benchmark Suite")
        print(" [3] 🧪 Run PotatoClaw V2 Architectural Tests")
        print(" [Q] Quit")
        print("-" * 65)
        
        try:
            choice = input("Select an option [1-3, Q]: ").strip().lower()
        except EOFError:
            break
            
        if choice == 'q':
            print("Exiting PotatoClaw Hub. Goodbye!")
            break
        elif choice == '1':
            cat = select_category()
            if cat:
                run_x_post_workflow(cat)
                try: input("\nPress Enter to return to main menu...")
                except EOFError: pass
        elif choice == '2':
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "run_benchmarks.py"), "potato_v2"])
            try: input("\nPress Enter to return to main menu...")
            except EOFError: pass
        elif choice == '3':
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_potato_v2.py")])
            try: input("\nPress Enter to return to main menu...")
            except EOFError: pass
        else:
            print("[!] Invalid choice. Please select 1, 2, 3, or Q.")

def select_category():
    print("\nSelect Category:")
    print(" [1] 🤖 Tech & Artificial Intelligence")
    print(" [2] 🛡️ Defence & Aerospace")
    print(" [3] ⚛️ Physics & Quantum Science")
    c = input("Choice [1-3, default=1]: ").strip()
    map_cat = {'1': 'tech', '2': 'defence', '3': 'physics'}
    return map_cat.get(c, 'tech')

if __name__ == "__main__":
    purge_all_caches(verbose=True)
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        cat = sys.argv[2].lower() if len(sys.argv) > 2 else "tech"
        if cmd == "x":
            run_x_post_workflow(cat)
        else:
            show_interactive_hub()
    else:
        show_interactive_hub()
