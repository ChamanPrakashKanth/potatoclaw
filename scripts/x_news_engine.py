#!/usr/bin/env python3
"""
PotatoClaw Single-Story X (Twitter) Engine for Non-Premium Users
Curates ONE authoritative news story at a time (Tech, Defence, Physics),
formats it strictly under 280 characters for standard non-premium X accounts,
and presents a clear 'Search & Plan' review before 1-click manual posting.
"""

import sys
import os
import io
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import time
import subprocess
import webbrowser
import re
from datetime import datetime

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

SPARK_API_URL = "http://127.0.0.1:11435/v1/chat/completions"
MODEL_ID = "spark-x2.5-4b:latest"
X_FREE_CHAR_LIMIT = 280

# Authoritative, high-signal feeds
FEEDS = {
    "tech": [
        ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
        ("Hacker News Top", "https://news.ycombinator.com/rss"),
        ("Ars Technica", "https://arstechnica.com/feed/"),
        ("ArXiv AI", "https://export.arxiv.org/rss/cs.AI"),
    ],
    "defence": [
        ("Breaking Defense", "https://breakingdefense.com/feed/"),
        ("Defense One", "https://www.defenseone.com/rss/all/"),
        ("US Naval Institute", "https://news.usni.org/feed"),
        ("SpaceNews Defense", "https://spacenews.com/feed/"),
    ],
    "physics": [
        ("Phys.org Quantum", "https://phys.org/rss-feed/physics-news/quantum-physics/"),
        ("Physics World (IOP)", "https://physicsworld.com/feed/"),
        ("ArXiv Quantum Physics", "https://export.arxiv.org/rss/quant-ph"),
        ("Phys.org Physics", "https://phys.org/rss-feed/physics-news/"),
    ]
}

SPAM_KEYWORDS = [
    "how to get free", "top 10 tools", "best vpn", "discount", "coupon",
    "affiliate", "airdrop", "promo code", "seo vs", "free traffic",
    "review 2023", "review 2024", "review 2025", "price drop", "deal of the day"
]

def clean_html_tags(text):
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = clean.replace('&quot;', '"').replace('&amp;', '&').replace('&apos;', "'").replace('&#39;', "'").replace('&nbsp;', ' ')
    return clean.strip()

def is_spam(title, desc):
    combined = (title + " " + desc).lower()
    return any(k in combined for k in SPAM_KEYWORDS)

def fetch_category_news(category, max_items=5):
    sources = FEEDS.get(category.lower(), [])
    all_articles = []
    
    for source_name, url in sources:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            })
            with urllib.request.urlopen(req, timeout=6) as resp:
                tree = ET.fromstring(resp.read())
                items = tree.findall('.//item')
                for item in items:
                    title_elem = item.find('title')
                    link_elem = item.find('link')
                    desc_elem = item.find('description')
                    
                    title = clean_html_tags(title_elem.text) if title_elem is not None and title_elem.text else ""
                    link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                    desc = clean_html_tags(desc_elem.text)[:250] if desc_elem is not None and desc_elem.text else ""
                    
                    if not title or len(title) < 15 or is_spam(title, desc):
                        continue
                        
                    if not any(a['title'].lower() == title.lower() for a in all_articles):
                        all_articles.append({
                            "source": source_name,
                            "title": title,
                            "link": link,
                            "desc": desc
                        })
                        if len(all_articles) >= max_items:
                            break
        except Exception:
            pass
            
    return all_articles[:max_items]

def generate_single_story_x_post(category, article):
    """
    Crafts ONE high-impact post tailored strictly under 280 characters for Non-Premium X users
    using PotatoClaw V2 Bounded Working Memory.
    """
    link = article.get('link', '').strip()
    link_section = f"\n\n🔗 {link}" if link else ""
    
    prompt = f"""[TASK STATE (BMW)]
GOAL: Create ONE viral X (Twitter) post for this single story.
CATEGORY: {category.upper()}
HEADLINE: {article['title']}
SOURCE: {article['source']}
FACTS: {article['desc'][:160]}

RULES:
1. Under 210 characters text (plus link).
2. Start with an emoji hook (🚀 / 🛡️ / ⚛️).
3. State what happened and why it matters in 1-2 punchy sentences.
4. End with 2 hashtags e.g. #{category.capitalize()} #Tech.
5. Output ONLY the tweet text. No markdown fences."""

    try:
        payload = {
            "model": MODEL_ID,
            "messages": [
                {"role": "system", "content": "You are PotatoClaw V2 X-Engine. Output ONLY the single post text."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 100,
            "temperature": 0.2
        }
        
        req = urllib.request.Request(
            SPARK_API_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            msg = data['choices'][0]['message']
            content = (msg.get('content') or msg.get('reasoning_content') or '').strip()
            
            # Remove any thinking block if present
            if "</think>" in content:
                content = content.split("</think>")[-1].strip()
            content = content.replace("```json", "").replace("```", "").strip().strip('"')
            
            if content:
                # Append link if not already present
                if link and link not in content:
                    full_post = f"{content}{link_section}"
                else:
                    full_post = content
                    
                # Validate length (Twitter calculates URLs as 23 chars)
                effective_len = len(re.sub(r'https?://\S+', 'X'*23, full_post))
                if effective_len <= X_FREE_CHAR_LIMIT:
                    return full_post
    except Exception:
        pass
        
    return format_fallback_single_post(category, article)

def format_fallback_single_post(category, article):
    emojis = {
        "tech": "🚀 TECH BREAKTHROUGH",
        "defence": "🛡️ DEFENCE RADAR",
        "physics": "⚛️ QUANTUM / PHYSICS",
        "all": "⚡ BREAKING INTEL"
    }
    header = emojis.get(category.lower(), "🔥 LATEST")
    
    tags_map = {
        "tech": "#Tech #AI #DeepTech",
        "defence": "#DefenseTech #Military #Aerospace",
        "physics": "#Physics #Quantum #Science",
        "all": "#Tech #Physics #DefenseTech"
    }
    tags = tags_map.get(category.lower(), "#Tech #Innovation")
    
    title = article['title']
    link = article.get('link', '').strip()
    
    # Twitter counts any URL as 23 characters (t.co)
    # Target raw format:
    # {header}: {title}\n\n🔗 {link}\n\n{tags}
    link_section = f"🔗 {link}\n\n" if link else ""
    
    # Calculate character budget (reserving ~23 chars for Twitter t.co URL)
    url_weight = 23 if link else 0
    overhead = len(header) + 2 + len("\n\n🔗 \n\n") + len(tags) + url_weight
    max_title_len = X_FREE_CHAR_LIMIT - overhead
    
    if len(title) > max_title_len:
        title = title[:max_title_len].rsplit(' ', 1)[0] + "..."
        
    return f"{header}: {title}\n\n{link_section}{tags}"

def copy_to_clipboard(text):
    try:
        subprocess.run(['clip.exe'], input=text.strip().encode('utf-16le'), check=True)
        return True
    except Exception:
        return False

def open_x_intent(text):
    encoded = urllib.parse.quote(text)
    url = f"https://x.com/intent/post?text={encoded}"
    print(f"[*] Opening Chrome with pre-filled X post...")
    webbrowser.open(url)

def save_draft(text, category, title):
    drafts_dir = os.path.join(os.path.dirname(__file__), "..", "news_drafts")
    os.makedirs(drafts_dir, exist_ok=True)
    filename = f"x_single_{category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    path = os.path.join(drafts_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# X Single Post Draft - {category.upper()}\n\n")
        f.write(f"Source Headline: {title}\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("```text\n")
        f.write(text)
        f.write("\n```\n")
    return path

def display_plan_and_post(category, article):
    print("\n" + "=" * 65)
    print(" 📋 X SEARCH & POST PLAN (NON-PREMIUM USER)")
    print("=" * 65)
    print(f" Category   : {category.upper()}")
    print(f" Source     : {article['source']}")
    print(f" Headline   : {article['title']}")
    print(f" Source URL : {article.get('link', 'N/A')}")
    print("-" * 65)
    
    print("[*] Generating single-story tweet formatted for X (<= 280 chars)...")
    post_draft = generate_single_story_x_post(category, article)
    
    while True:
        char_count = len(post_draft)
        status_color = "✔ PASS (< 280)" if char_count <= X_FREE_CHAR_LIMIT else "❌ EXCEEDS 280"
        
        print("\n" + "-" * 65)
        print(" 📝 DRAFTED TWEET (SINGLE STORY):")
        print("-" * 65)
        print(post_draft)
        print("-" * 65)
        print(f" Character Count : {char_count} / {X_FREE_CHAR_LIMIT} chars [{status_color}]")
        print(" Plan Target     : Standard Non-Premium X (Twitter) Account")
        print("-" * 65)
        print(" Actions:")
        print("   [P] Post to X (Open Chrome with prefilled post)")
        print("   [C] Copy text to Clipboard")
        print("   [E] Edit tweet text manually")
        print("   [S] Save Draft to disk")
        print("   [R] Regenerate post with AI")
        print("   [M] Back to Main Menu")
        
        action = input("\nChoose action [P/C/E/S/R/M]: ").strip().lower()
        
        if action == 'p':
            open_x_intent(post_draft)
            copy_to_clipboard(post_draft)
            print("[✔] Opened X composer in browser and copied text to clipboard!")
        elif action == 'c':
            if copy_to_clipboard(post_draft):
                print("[✔] Copied to Windows clipboard successfully!")
            else:
                print("[!] Clipboard copy failed.")
        elif action == 'e':
            print("\nEnter your edited tweet text (press Enter to finish):")
            edited = input().strip()
            if edited:
                post_draft = edited
                print("[✔] Tweet text updated.")
        elif action == 's':
            saved_path = save_draft(post_draft, category, article['title'])
            print(f"[✔] Draft saved to: {saved_path}")
        elif action == 'r':
            print("[*] Regenerating single-story post...")
            post_draft = generate_single_story_x_post(category, article)
        elif action == 'm':
            break
        else:
            print("[!] Unknown action.")

def run_menu():
    while True:
        print("\n" + "=" * 65)
        print("  POTATOCLAW: SINGLE-STORY X ENGINE (NON-PREMIUM)")
        print("=" * 65)
        print(" [1] 🤖 Search Tech / AI (1 Top Story)")
        print(" [2] 🛡️ Search Defence / Aerospace (1 Top Story)")
        print(" [3] ⚛️ Search Physics / Quantum (1 Top Story)")
        print(" [Q] Quit")
        print("-" * 65)
        
        choice = input("Select an option [1-3, Q]: ").strip().lower()
        if choice == 'q':
            print("Exiting.")
            break
            
        category_map = {'1': 'tech', '2': 'defence', '3': 'physics'}
        if choice not in category_map:
            print("[!] Invalid option. Please choose 1, 2, 3, or Q.")
            continue
            
        cat = category_map[choice]
        print(f"\n[*] Searching latest authoritative news in '{cat.upper()}'...")
        articles = fetch_category_news(cat, max_items=4)
        
        if not articles:
            print("[!] No articles found. Please check internet connection.")
            continue
            
        print(f"\n[+] Top stories found:")
        for idx, a in enumerate(articles, 1):
            print(f"    [{idx}] {a['title']} ({a['source']})")
            
        story_idx = input(f"\nSelect story to Plan & Post [1-{len(articles)}, default=1]: ").strip()
        try:
            selected_article = articles[int(story_idx) - 1] if story_idx.isdigit() and 1 <= int(story_idx) <= len(articles) else articles[0]
        except Exception:
            selected_article = articles[0]
            
        display_plan_and_post(cat, selected_article)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() in ['tech', 'defence', 'physics', 'all']:
        cat = sys.argv[1].lower()
        print(f"[*] Searching #1 Top Story for {cat.upper()} (Non-Premium X Plan)...")
        arts = fetch_category_news(cat, 1)
        if arts:
            article = arts[0]
            print(f"[+] Selected: {article['title']} ({article['source']})")
            draft = generate_single_story_x_post(cat, article)
            print("\n" + "=" * 60)
            print(draft)
            print("=" * 60)
            print(f"Length: {len(draft)} / {X_FREE_CHAR_LIMIT} chars (Non-Premium OK)\n")
            copy_to_clipboard(draft)
            open_x_intent(draft)
        else:
            print("[!] No stories found.")
    else:
        run_menu()
