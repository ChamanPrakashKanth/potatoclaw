#!/usr/bin/env python3
"""
PotatoClaw Master Content & Posting Hub
Connects PotatoClaw V2 BMW Agent to X (Twitter) and YouTube Shorts posting workflows.
Supports 1-click single-story posts, 9:16 vertical video generation, dual posting,
and browser studio opening.
"""

import sys
import os
import io
import time
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

from x_news_engine import (
    fetch_category_news,
    generate_single_story_x_post,
    copy_to_clipboard as x_copy_to_clipboard,
    save_draft as x_save_draft
)
from shorts_generator import (
    create_shorts_video,
    generate_shorts_captions,
    open_video_in_folder,
    PEXELS_API_KEY
)

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
                webbrowser.open("https://x.com/compose/post")
                print("[✔] Opened https://x.com/compose/post in browser (Press Ctrl+V to paste & post).")
        except EOFError:
            pass
        
    return post_text

def run_shorts_workflow(category="tech", auto_open=True):
    print(f"\n[*] Curating #1 breaking story in '{category.upper()}' for YouTube Shorts...")
    articles = fetch_category_news(category, max_items=1)
    if not articles:
        print("[!] No news articles found.")
        return None
        
    article = articles[0]
    print(f"[+] Selected: {article['title']} ({article['source']})")
    print(f"[*] Generating 1080x1920 9:16 Vertical Video (Pexels + FFmpeg)...")
    
    video_path = create_shorts_video(category, article, PEXELS_API_KEY)
    if not video_path:
        print("[!] Failed to render Shorts video.")
        return None
        
    caption = generate_shorts_captions(category, article, video_path)
    x_copy_to_clipboard(caption)
    
    print("\n" + "=" * 65)
    print(" 🎬 YOUTUBE SHORTS VIDEO READY:")
    print("=" * 65)
    print(f" Video Path : {video_path}")
    print(f" Dimensions : 1080x1920 (9:16 Vertical HD Short)")
    print("-" * 65)
    print(" 📝 VIDEO TITLE & CAPTION (Copied to Clipboard):")
    print(caption)
    print("=" * 65)
    
    if auto_open:
        open_video_in_folder(video_path)
        try:
            choice = input("\nOpen YouTube Studio Upload in browser? [Y/n]: ").strip().lower()
            if choice != 'n':
                webbrowser.open("https://studio.youtube.com/channel/videos/upload?d=ud")
                print("[✔] Opened YouTube Studio in browser. Drag & drop the selected MP4 video!")
        except EOFError:
            pass
        
    return video_path

def run_dual_post_workflow(category="tech"):
    print("\n" + "=" * 65)
    print(f" ⚡ RUNNING DUAL POST WORKFLOW: X POST + YOUTUBE SHORTS ({category.upper()})")
    print("=" * 65)
    
    articles = fetch_category_news(category, max_items=1)
    if not articles:
        print("[!] No news articles found.")
        return
        
    article = articles[0]
    print(f"[+] Selected Story: {article['title']} ({article['source']})")
    
    # 1. Generate X post
    print(f"\n[Step 1/2] Generating X Post with PotatoClaw V2...")
    x_post = generate_single_story_x_post(category, article)
    x_save_draft(x_post, category, article['title'])
    print(f"[✔] X Post text created ({len(x_post)} chars).")
    
    # 2. Render Shorts video
    print(f"\n[Step 2/2] Rendering 1080x1920 YouTube Shorts Video...")
    video_path = create_shorts_video(category, article, PEXELS_API_KEY)
    caption = generate_shorts_captions(category, article, video_path)
    
    x_copy_to_clipboard(x_post)
    if video_path:
        open_video_in_folder(video_path)
        
    print("\n" + "=" * 65)
    print(" 🎉 DUAL POST ASSETS COMPLETE:")
    print("=" * 65)
    print(f" 🐦 X Post Text  : Copied to clipboard! Ready to paste.")
    print(f" 🎬 Video File   : {video_path}")
    print("=" * 65)
    
    act = input("Open browsers? [1: Both X & YouTube | 2: X only | 3: YouTube only | 4: Skip]: ").strip()
    if act in ['1', '']:
        webbrowser.open("https://x.com/compose/post")
        webbrowser.open("https://studio.youtube.com/channel/videos/upload?d=ud")
    elif act == '2':
        webbrowser.open("https://x.com/compose/post")
    elif act == '3':
        webbrowser.open("https://studio.youtube.com/channel/videos/upload?d=ud")

def show_interactive_hub():
    while True:
        print("\n" + "=" * 65)
        print("   POTATOCLAW MASTER POSTING & CONTENT AUTOMATION HUB")
        print("=" * 65)
        print(" Model: Spark-X2.5-4B (Q4_K_M) | GPU: GTX 1650 | Context: 2048")
        print("-" * 65)
        print(" [1] 🐦 Post Single-Story News to X (Tech / Defence / Physics)")
        print(" [2] 🎬 Create & Post YouTube Shorts (9:16 Vertical Video)")
        print(" [3] ⚡ Dual Post: Create BOTH (X Post + YouTube Short Video)")
        print(" [4] 📊 Run PotatoClaw V2 Benchmark Suite")
        print(" [5] 🧪 Run PotatoClaw V2 Architectural Tests")
        print(" [Q] Quit")
        print("-" * 65)
        
        try:
            choice = input("Select an option [1-5, Q]: ").strip().lower()
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
            cat = select_category()
            if cat:
                run_shorts_workflow(cat)
                try: input("\nPress Enter to return to main menu...")
                except EOFError: pass
        elif choice == '3':
            cat = select_category()
            if cat:
                run_dual_post_workflow(cat)
                try: input("\nPress Enter to return to main menu...")
                except EOFError: pass
        elif choice == '4':
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "run_benchmarks.py"), "potato_v2"])
            try: input("\nPress Enter to return to main menu...")
            except EOFError: pass
        elif choice == '5':
            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "test_potato_v2.py")])
            try: input("\nPress Enter to return to main menu...")
            except EOFError: pass
        else:
            print("[!] Invalid choice. Please select 1, 2, 3, 4, 5, or Q.")

def select_category():
    print("\nSelect Category:")
    print(" [1] 🤖 Tech & Artificial Intelligence")
    print(" [2] 🛡️ Defence & Aerospace")
    print(" [3] ⚛️ Physics & Quantum Science")
    c = input("Choice [1-3, default=1]: ").strip()
    map_cat = {'1': 'tech', '2': 'defence', '3': 'physics'}
    return map_cat.get(c, 'tech')

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        cat = sys.argv[2].lower() if len(sys.argv) > 2 else "tech"
        if cmd == "x":
            run_x_post_workflow(cat)
        elif cmd in ["shorts", "yt", "youtube"]:
            run_shorts_workflow(cat)
        elif cmd in ["all", "dual", "both"]:
            run_dual_post_workflow(cat)
        else:
            show_interactive_hub()
    else:
        show_interactive_hub()
