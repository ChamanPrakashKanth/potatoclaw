#!/usr/bin/env python3
"""
PotatoClaw Shorts & Video Post Generator (Pexels API + FFmpeg)
Curates Tech, Defence, and Physics stories, fetches matching 9:16 vertical stock videos
from Pexels, adds branded dynamic title overlays using FFmpeg, and prepares
1-click uploads for YouTube Shorts, X Video, Instagram Reels, and TikTok.
"""

import sys
import os
import io
import urllib.request
import urllib.parse
import json
import time
import subprocess
import webbrowser
import re
from datetime import datetime

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Load .env variables
def load_env():
    env_paths = [
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.expanduser("~/.openclaw/.env")
    ]
    for p in env_paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and not os.environ.get(k):
                            os.environ[k] = v

load_env()
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()

# Add scripts directory to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from x_news_engine import fetch_category_news, clean_html_tags

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "media_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CATEGORY_KEYWORDS = {
    "tech": ["artificial intelligence technology", "cyber neural network", "robotics futuristic", "quantum processor chips"],
    "defence": ["military stealth aircraft", "fighter jet supersonic", "navy warship ocean", "aerospace defense radar"],
    "physics": ["quantum physics abstract", "deep space galaxy nebula", "particle energy beam", "astrophysics black hole"]
}

def search_pexels_video(query, api_key):
    """Searches Pexels for a 9:16 vertical portrait video."""
    if not api_key:
        print("[!] No PEXELS_API_KEY found in .env. Please set PEXELS_API_KEY=your_key in .env")
        return None
        
    params = {
        "query": query,
        "orientation": "portrait",
        "size": "medium",
        "per_page": 5
    }
    url = f"{PEXELS_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    
    try:
        req = urllib.request.Request(url, headers={
            "Authorization": api_key,
            "User-Agent": "PotatoClaw-Shorts-Engine/1.0"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            videos = data.get('videos', [])
            if not videos:
                return None
                
            # Pick the best HD 1080x1920 or 720x1280 portrait video file
            for video in videos:
                for vfile in video.get('video_files', []):
                    width = vfile.get('width', 0)
                    height = vfile.get('height', 0)
                    # Prefer vertical aspect ratio (height > width)
                    if height > width and vfile.get('link'):
                        return {
                            "id": video.get('id'),
                            "url": vfile.get('link'),
                            "width": width,
                            "height": height,
                            "duration": video.get('duration', 15),
                            "photographer": video.get('user', {}).get('name', 'Pexels Creator')
                        }
            # Fallback to first available file
            first_file = videos[0].get('video_files', [{}])[0].get('link')
            if first_file:
                return {"url": first_file, "duration": 15, "photographer": "Pexels"}
    except Exception as e:
        print(f"[!] Pexels API Error: {e}")
        
    return None

def download_video(video_url, output_path):
    print(f"[*] Downloading background video from Pexels...")
    req = urllib.request.Request(video_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp, open(output_path, 'wb') as f:
        f.write(resp.read())
    return output_path

def generate_fallback_background_video(output_path, category):
    """Generates an aesthetic 9:16 vertical background video with FFmpeg if no Pexels key."""
    print("[*] Generating synthetic 9:16 motion background via FFmpeg...")
    color_schemes = {
        "tech": "color=c=0x0a1128:s=1080x1920:d=10",
        "defence": "color=c=0x1a090d:s=1080x1920:d=10",
        "physics": "color=c=0x0b051b:s=1080x1920:d=10"
    }
    src = color_schemes.get(category.lower(), "color=c=0x111111:s=1080x1920:d=10")
    
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", src,
        "-vf", "noise=c1s=8:c0s=0:allf=t+u,hue=s=1",
        "-c:v", "libx264", "-t", "10", "-pix_fmt", "yuv420p", output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_path

def create_shorts_video(category, article, pexels_key):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_bg_path = os.path.join(OUTPUT_DIR, f"bg_raw_{timestamp}.mp4")
    final_video_path = os.path.join(OUTPUT_DIR, f"short_{category}_{timestamp}.mp4")
    
    # 1. Search & Download Stock Video
    query = CATEGORY_KEYWORDS.get(category.lower(), ["technology"])[0]
    video_info = search_pexels_video(query, pexels_key) if pexels_key else None
    
    if video_info and video_info.get('url'):
        download_video(video_info['url'], raw_bg_path)
    else:
        generate_fallback_background_video(raw_bg_path, category)
        
    # 2. Prepare dynamic overlay text
    header_titles = {
        "tech": "TECH BREAKTHROUGH",
        "defence": "DEFENCE INTEL",
        "physics": "QUANTUM PHYSICS"
    }
    badge = header_titles.get(category.lower(), "BREAKING NEWS")
    title_text = article['title'].replace(":", " -").replace("'", "").replace('"', "")
    
    # Split title into lines for clean reading
    words = title_text.split()
    line1 = " ".join(words[:5])
    line2 = " ".join(words[5:10]) if len(words) > 5 else ""
    line3 = " ".join(words[10:15]) if len(words) > 10 else ""
    
    # 3. Assemble vertical 1080x1920 Short with FFmpeg
    print(f"[*] Rendering vertical 9:16 Short with FFmpeg...")
    
    # Filter graph: Scale & crop to exact 1080x1920, add dark gradient overlay and text
    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "drawbox=y=0:color=black@0.4:width=iw:height=ih:t=fill,"
        f"drawtext=text='{badge}':fontcolor=white:fontsize=48:box=1:boxcolor=red@0.8:boxborderw=18:x=(w-text_w)/2:y=400,"
        f"drawtext=text='{line1}':fontcolor=white:fontsize=54:x=(w-text_w)/2:y=650:shadowcolor=black:shadowx=3:shadowy=3,"
        f"drawtext=text='{line2}':fontcolor=yellow:fontsize=52:x=(w-text_w)/2:y=730:shadowcolor=black:shadowx=3:shadowy=3,"
        f"drawtext=text='{line3}':fontcolor=white:fontsize=50:x=(w-text_w)/2:y=810:shadowcolor=black:shadowx=3:shadowy=3,"
        f"drawtext=text='Via {article['source']}':fontcolor=gray:fontsize=38:x=(w-text_w)/2:y=1500"
    )
    
    cmd = [
        "ffmpeg", "-y", "-i", raw_bg_path,
        "-vf", filter_complex,
        "-t", "12",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        final_video_path
    ]
    
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print(f"[✔] Short Video created successfully: {final_video_path}")
    except Exception as e:
        print(f"[!] FFmpeg rendering error: {e}")
        return None
    finally:
        if os.path.exists(raw_bg_path):
            try:
                os.remove(raw_bg_path)
            except Exception:
                pass
                
    return final_video_path

def generate_shorts_captions(category, article, video_path):
    title = article['title']
    link = article.get('link', '')
    
    caption = f"🔥 {title}\n\nVia {article['source']}\n🔗 {link}\n\n#Shorts #Tech #DefenseTech #Physics #AI #Science #Innovation"
    return caption

def copy_to_clipboard(text):
    try:
        subprocess.run(['clip.exe'], input=text.strip().encode('utf-16le'), check=True)
        return True
    except Exception:
        return False

def open_video_in_folder(path):
    try:
        subprocess.run(['explorer.exe', '/select,', os.path.normpath(path)])
    except Exception:
        pass

def run_shorts_menu():
    print("\n" + "=" * 65)
    print("  POTATOCLAW SHORTS & VIDEO CREATOR (PEXELS + FFMPEG)")
    print("=" * 65)
    
    if PEXELS_API_KEY:
        print(f"[✔] Pexels API Key Detected (Key: {PEXELS_API_KEY[:6]}...{PEXELS_API_KEY[-4:]})")
    else:
        print("[i] Note: Add PEXELS_API_KEY=your_key in .env for real 4K/HD stock footage.")
        
    print("-" * 65)
    print(" [1] 🤖 Create Tech / AI Short Video")
    print(" [2] 🛡️ Create Defence / Military Short Video")
    print(" [3] ⚛️ Create Physics / Quantum Short Video")
    print(" [Q] Quit")
    print("-" * 65)
    
    choice = input("Select category [1-3, Q]: ").strip().lower()
    if choice == 'q':
        return
        
    category_map = {'1': 'tech', '2': 'defence', '3': 'physics'}
    if choice not in category_map:
        print("[!] Invalid choice.")
        return
        
    cat = category_map[choice]
    print(f"\n[*] Curating #1 breaking story in '{cat.upper()}'...")
    articles = fetch_category_news(cat, max_items=1)
    
    if not articles:
        print("[!] No stories found.")
        return
        
    article = articles[0]
    print(f"[+] Selected Story: {article['title']} ({article['source']})")
    
    video_path = create_shorts_video(cat, article, PEXELS_API_KEY)
    if not video_path:
        print("[!] Failed to create video.")
        return
        
    caption = generate_shorts_captions(cat, article, video_path)
    
    print("\n" + "=" * 65)
    print(" 🎬 SHORTS VIDEO READY:")
    print("=" * 65)
    print(f" File Location : {video_path}")
    print(f" Video Format  : 1080x1920 (9:16 Vertical HD Short)")
    print("-" * 65)
    print(" 📝 POST CAPTION / DESCRIPTION:")
    print(caption)
    print("-" * 65)
    print(" Actions:")
    print("   [P] Open Video in File Explorer (Ready to drag-and-drop to X/YouTube/TikTok)")
    print("   [C] Copy Caption to Clipboard")
    print("   [X] Open X (Twitter) Video Upload Composer in Chrome")
    print("   [Y] Open YouTube Shorts Upload in Chrome")
    
    action = input("\nChoose action [P/C/X/Y, default=P]: ").strip().lower()
    copy_to_clipboard(caption)
    
    if action == 'x':
        webbrowser.open("https://x.com/compose/post")
        open_video_in_folder(video_path)
    elif action == 'y':
        webbrowser.open("https://studio.youtube.com/channel/videos/upload?d=ud")
        open_video_in_folder(video_path)
    else:
        open_video_in_folder(video_path)
        print("[✔] Caption copied to clipboard and folder opened!")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() in ['tech', 'defence', 'physics']:
        cat = sys.argv[1].lower()
        arts = fetch_category_news(cat, 1)
        if arts:
            vpath = create_shorts_video(cat, arts[0], PEXELS_API_KEY)
            cap = generate_shorts_captions(cat, arts[0], vpath)
            copy_to_clipboard(cap)
            if vpath:
                open_video_in_folder(vpath)
    else:
        run_shorts_menu()
