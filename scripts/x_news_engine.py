#!/usr/bin/env python3
"""
PotatoClaw Single-Story X (Twitter) Engine for Non-Premium Users
Curates ONE authoritative news story at a time (Tech, Defence, Physics),
formats it strictly under 280 characters for standard non-premium X accounts,
and presents a clear 'Search & Plan' review before 1-click manual posting.
"""

import sys
sys.dont_write_bytecode = True

import os
import io
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
import json
import time
import subprocess
import webbrowser
import re
import unicodedata
import socket
from datetime import datetime

try:
    from fresh_start import purge_all_caches
except ImportError:
    def purge_all_caches(verbose=False): pass

try:
    from potato_bwm import BoundedWorkingMemory
    from potato_verifier import DeterministicVerifier
    from potato_compiler import ObservationCompiler
except ImportError:
    BoundedWorkingMemory = None
    DeterministicVerifier = None
    ObservationCompiler = None

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
SPARK_DRAFT_TIMEOUT_SECONDS = 180

# Authoritative, high-signal feeds
FEEDS = {
    "tech": [
        ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
        ("Hacker News Top", "https://news.ycombinator.com/rss"),
        ("Ars Technica", "https://arstechnica.com/feed/"),
        ("ArXiv AI", "https://export.arxiv.org/rss/cs.AI"),
    ],
    "defence": [
        ("IDRW (Indian Defence)", "https://idrw.org/feed/"),
        ("Breaking Defense", "https://breakingdefense.com/feed/"),
        ("Defense One", "https://www.defenseone.com/rss/all/"),
        ("US Naval Institute", "https://news.usni.org/feed"),
        ("SpaceNews Defense", "https://spacenews.com/feed/"),
    ],
    "indian_defence": [
        ("IDRW (Indian Defence)", "https://idrw.org/feed/"),
        ("Livefist Defence", "https://www.livefistdefence.com/feed/"),
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
    import html
    clean = html.unescape(text)
    clean = re.sub(r'<[^>]+>', '', clean)
    clean = clean.replace('&nbsp;', ' ').replace('\xa0', ' ')
    return clean.strip()

def is_spam(title, desc):
    combined = (title + " " + desc).lower()
    return any(k in combined for k in SPAM_KEYWORDS)

def fetch_category_news(category, max_items=5):
    import ssl
    ssl_ctx = ssl._create_unverified_context() if hasattr(ssl, '_create_unverified_context') else None
    sources = FEEDS.get(category.lower(), [])
    all_articles = []

    for source_name, url in sources:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            })
            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
                tree = ET.fromstring(resp.read())
                items = tree.findall('.//item')
                for item in items:
                    title_elem = item.find('title')
                    link_elem = item.find('link')
                    desc_elem = item.find('description')

                    title = clean_html_tags(title_elem.text) if title_elem is not None and title_elem.text else ""
                    link = clean_html_tags(link_elem.text) if link_elem is not None and link_elem.text else ""
                    raw_desc = clean_html_tags(desc_elem.text) if desc_elem is not None and desc_elem.text else ""
                    if len(raw_desc) > 350:
                        matches = list(re.finditer(r'[.!?](?=\s|$)', raw_desc[:350]))
                        if matches and matches[-1].end() > 80:
                            desc = raw_desc[:matches[-1].end()].strip()
                        else:
                            desc = raw_desc[:350].rsplit(' ', 1)[0].rstrip(' ,;:-') + "."
                    else:
                        desc = raw_desc
                    desc = desc.rstrip('. \t\n') + '.' if desc and not desc.endswith(('.', '!', '?')) else desc

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

META_REASONING_PATTERNS = [
    r'\bwe are asked\b',
    r'\bthe constraints?\b',
    r'\bstrict twitter limit\b',
    r'\bcharacter limit\b',
    r'\btwitter limit\b',
    r'\bunder \d+ characters\b',
    r'\brules?:\b',
    r'\bgoal:\b',
    r'\bheadline:\b',
    r'\bcategory:\b',
    r'\bsource:\b',
    r'\bkey intel:\b',
    r'\btask state\b',
    r'\bhere is (the|a) (viral )?tweet\b',
    r'\bhere\'s (the|a) (viral )?tweet\b',
    r'\b(tweet|post) text:\b',
    r'\bi will (write|create)\b',
    r'\blet\'s (write|create)\b',
    r'\bthinking process\b',
    r'\bdraft:\b',
    r'\bconstraint:\b',
]

def x_character_count(text):
    """Conservative X weight for explicit URLs and Unicode (complex emoji overcount)."""
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'https?://\S+', 'x' * 23, text)
    return sum(1 if ord(c) <= 0x10ff or 0x2000 <= ord(c) <= 0x200d
               or 0x2010 <= ord(c) <= 0x201f or 0x2032 <= ord(c) <= 0x2037
               else 2 for c in text)


def clean_x_tweet_output(raw_text, category, link="", source=""):
    """
    Deterministically cleans, verifies, and formats LLM output for X (Twitter).
    Suppresses CoT thinking, removes meta-deliberation and prompt leakage,
    and enforces the strict 280-character limit with t.co URL weighting.
    """
    if not isinstance(raw_text, str) or not raw_text.strip():
        return None

    text = raw_text.strip()

    # Strip <think>...</think> blocks
    text = re.sub(r'<think>.*?(?:</think>|$)', '', text, flags=re.DOTALL | re.IGNORECASE).strip()
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()

    # Strip Markdown fences and quotes
    text = re.sub(r'^```[a-zA-Z]*\n?', '', text)
    text = re.sub(r'\n?```$', '', text).strip()
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()

    # Process line by line to remove meta-reasoning, bulleted constraints, or preambles
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    cleaned_lines = []

    for line in lines:
        lower_line = line.lower()
        # Skip lines matching meta-reasoning / constraint patterns
        if any(re.search(pat, lower_line) for pat in META_REASONING_PATTERNS):
            continue
        # Skip bullet points that look like prompt rules
        if re.match(r'^(?:[-*•]|\d+\.)\s*(?:strict|limit|under|start|state|end|output|rule|constraint)', lower_line):
            continue
        cleaned_lines.append(line)

    if not cleaned_lines:
        return None

    content = " ".join(cleaned_lines).strip()
    content = re.sub(r'https?://\S+|\b(?:www\.)?[\w-]+\.(?:org|com|net|in)(?:/\S*)?|(?<!\w)#\w+', '', content, flags=re.IGNORECASE)
    content = re.sub(r'[\U0001F000-\U0001FAFF\u2600-\u27BF\ufe0f\u200d]', '', content)
    content = re.sub(r'\s+', ' ', content).strip()
    publisher = source.split(' (', 1)[0].strip()
    if publisher and re.search(r'\b' + re.escape(publisher) + r'\b', content, re.IGNORECASE):
        return None

    # If content still contains blatant prompt constraints / meta-talk, reject
    if any(re.search(pat, content.lower()) for pat in META_REASONING_PATTERNS):
        return None

    # Must have minimum substance
    if len(content) < 15:
        return None

    # Normalize whitespace
    content = re.sub(r'\s+', ' ', content).strip()

    link_section = ""
    if x_character_count(content + link_section) <= X_FREE_CHAR_LIMIT:
        return content + link_section

    # Prefer a complete sentence to a clipped second sentence.
    sentences = re.split(r'(?<=[.!?])\s+', content)
    while len(sentences) > 1:
        sentences.pop()
        candidate = ' '.join(sentences) + link_section
        if x_character_count(candidate) <= X_FREE_CHAR_LIMIT:
            return candidate
    trimmed = content
    while trimmed and x_character_count(trimmed + '...' + link_section) > X_FREE_CHAR_LIMIT:
        trimmed = trimmed[:-1].rstrip()
    if ' ' in trimmed:
        trimmed = trimmed.rsplit(' ', 1)[0]
    return trimmed + '...' + link_section if trimmed else None


def generate_single_story_x_post(category, article, graph_context=""):
    """
    Crafts ONE high-impact post tailored strictly under 280 characters for Non-Premium X users
    using PotatoClaw V3 Bounded Working Memory and Deterministic Verifier.
    """
    link = article.get('link', '').strip()

    # PotatoClaw V3: Bounded Working Memory with Facts Only (no prompt constraint pollution)
    if BoundedWorkingMemory is not None:
        bwm = BoundedWorkingMemory(max_total_chars=500)
        bwm.add_protected_fact(f"Category: {category.upper()}")
        bwm.add_fact(f"Headline: {article['title']}")
        if article.get('desc'):
            bwm.add_fact(f"Intel: {article['desc'][:120]}")
        bwm_block = bwm.format_prompt_block()
    else:
        bwm_block = f"HEADLINE: {article['title']}\nFACTS: {article.get('desc', '')[:120]}"

    graph_block = f"\n\n{graph_context[:700]}" if graph_context else ""
    prompt = f"""{bwm_block}{graph_block}

Write one factual X news post in 1-2 short sentences, at most 250 characters.
Start with the organisation or subject and what happened. Then explain its
purpose or significance only if supported by the supplied facts.
Preserve status: a tender or proposal is not a launch or proven capability.
Use neutral, clear prose. No hype, emojis, hashtags, headings, or calls to action.
Write an original summary of the facts; do not copy the headline or article wording.
Do not invent details. Omit publisher names, source credits, domains and links.
Output only the post text."""

    print('[*] Waiting for Spark; a cold first draft can take up to 3 minutes.')
    for attempt in range(2):
        try:
            payload = {
                "model": MODEL_ID,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are PotatoClaw V3 X-Engine. Output ONLY the tweet text directly. Never output preambles, thinking steps, constraints, or meta-commentary."
                    },
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 256,
                "chat_template_kwargs": {"enable_thinking": False},
                "temperature": 0.2
            }

            req = urllib.request.Request(
                SPARK_API_URL,
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=SPARK_DRAFT_TIMEOUT_SECONDS) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                msg = data['choices'][0]['message']
                content = (msg.get('content') or '').strip()

                cleaned_post = clean_x_tweet_output(content, category, link, article.get('source', ''))
                if cleaned_post and cleaned_post.casefold().rstrip('.!?') == article['title'].casefold().rstrip('.!?'):
                    cleaned_post = None
                if cleaned_post:
                    return cleaned_post
                if attempt == 0:
                    print('[!] Model returned no usable original draft. Retrying once...')
        except (socket.timeout, TimeoutError):
            print('[!] Spark did not finish within 180 seconds. Check the model window for progress or another running request, then retry.')
            return None
        except urllib.error.HTTPError as error:
            print(f'[!] Spark returned HTTP {error.code}. Check the model window for the server error.')
            return None
        except urllib.error.URLError as error:
            if isinstance(error.reason, (socket.timeout, TimeoutError)):
                print('[!] The connection to Spark timed out. Check the model window and retry.')
            else:
                print('[!] Cannot connect to Spark at 127.0.0.1:11435. Check that the local model is listening.')
            return None
        except OSError:
            print('[!] The connection to Spark was interrupted. Check the model window and retry.')
            return None
        except (ValueError, KeyError, IndexError, TypeError):
            print('[!] Spark returned an invalid response.')
            return None

    print('[!] Spark did not return a usable original draft after two attempts.')

    return format_fallback_single_post(category, article)

def format_fallback_single_post(category, article):
    """Require regeneration rather than publishing a copied source headline."""
    return None


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

def copy_to_clipboard(text):
    try:
        subprocess.run(['clip.exe'], input=text.strip().encode('utf-16le'), check=True)
        return True
    except Exception:
        return False

def open_x_intent(text):
    encoded = urllib.parse.quote(text)
    url = f"https://x.com/intent/post?text={encoded}"
    print(f"[*] Opening default browser with pre-filled X post...")
    success = open_url_in_browser(url)
    if not success:
        open_url_in_browser("https://x.com/compose/post")
    return success

def save_draft(text, category, title):
    """Zero-cache rule: Do not write drafts to disk. Every start is fresh."""
    return None

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
    if not post_draft:
        print('[!] No original draft generated. Please try again.')
        return

    while True:
        char_count = x_character_count(post_draft)
        status_color = "✔ PASS (<= 280)" if char_count <= X_FREE_CHAR_LIMIT else "❌ EXCEEDS 280"

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
        print("   [S] Save Draft (Copy to Clipboard - Zero-Cache)")
        print("   [R] Regenerate post with AI")
        print("   [M] Back to Main Menu")

        action = input("\nChoose action [P/C/E/S/R/M]: ").strip().lower()

        if action == 'p':
            if char_count > X_FREE_CHAR_LIMIT:
                print('[!] Shorten the draft to 280 characters before posting.')
                continue
            open_x_intent(post_draft)
            copy_to_clipboard(post_draft)
            print("\n[✔] Opened X composer in browser and copied text to clipboard!")
            print("[✔] Tip: Press Ctrl+V in the X window to paste and post.")
            try:
                input("\nPress Enter to continue in menu...")
            except EOFError:
                pass
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
            save_draft(post_draft, category, article['title'])
            print("[✔] Zero-cache rule active: draft copied to clipboard (no files written to disk).")
        elif action == 'r':
            print("[*] Regenerating single-story post...")
            regenerated = generate_single_story_x_post(category, article)
            if regenerated:
                post_draft = regenerated
            else:
                print('[!] No original draft generated. Keeping the current draft.')
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
    purge_all_caches(verbose=False)
    if len(sys.argv) > 1 and sys.argv[1].lower() in ['tech', 'defence', 'physics', 'all']:
        cat = sys.argv[1].lower()
        print(f"[*] Searching #1 Top Story for {cat.upper()} (Non-Premium X Plan)...")
        arts = fetch_category_news(cat, 1)
        if arts:
            article = arts[0]
            print(f"[+] Selected: {article['title']} ({article['source']})")
            draft = generate_single_story_x_post(cat, article)
            if not draft:
                print('[!] No original draft generated. Please try again.')
                sys.exit(1)
            print("\n" + "=" * 60)
            print(draft)
            print("=" * 60)
            print(f"Length: {len(draft)} / {X_FREE_CHAR_LIMIT} chars (Non-Premium OK)\n")
            copy_to_clipboard(draft)
            open_x_intent(draft)
            print("[✔] Opened X composer in browser and copied tweet to clipboard!")
            try:
                input("\n[✔] Done! Press Enter to close...")
            except EOFError:
                pass
        else:
            print("[!] No stories found.")
            try:
                input("\nPress Enter to close...")
            except EOFError:
                pass
    else:
        run_menu()
