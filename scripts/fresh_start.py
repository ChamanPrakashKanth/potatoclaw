#!/usr/bin/env python3
"""
PotatoClaw Fresh Start & Zero-Cache Engine
Instantly purges old news drafts, temporary video renders, python bytecode,
and resets local LLM KV memory slot cache before every new run.
"""

import sys
sys.dont_write_bytecode = True

import os
import io
import shutil
import glob
import urllib.request
import subprocess

# Ensure UTF-8 output on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DRAFTS_DIR = os.path.join(ROOT_DIR, "news_drafts")
MEDIA_DIR = os.path.join(ROOT_DIR, "media_output")
SPARK_API_URL = "http://127.0.0.1:11435"
QWEN_API_URL = "http://127.0.0.1:11436"

def clean_directory(dir_path, label=""):
    """Removes all files inside a directory without deleting the directory itself."""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
        return 0
        
    count = 0
    for item in os.listdir(dir_path):
        item_path = os.path.join(dir_path, item)
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path)
                count += 1
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path, ignore_errors=True)
                count += 1
        except Exception:
            pass
            
    if count > 0 and label:
        print(f" [🧹] Purged {count} old files in {label}")
    return count

def clean_pycache():
    """Fast pycache cleaner targeting scripts, src, benchmarks and root (skipping node_modules and .git)."""
    count = 0
    target_dirs = [
        ROOT_DIR,
        os.path.join(ROOT_DIR, "scripts"),
        os.path.join(ROOT_DIR, "src"),
        os.path.join(ROOT_DIR, "benchmarks")
    ]
    for target in target_dirs:
        if os.path.exists(target):
            for root, dirs, files in os.walk(target):
                if "node_modules" in dirs:
                    dirs.remove("node_modules")
                if ".git" in dirs:
                    dirs.remove(".git")
                for d in list(dirs):
                    if d == "__pycache__":
                        try:
                            shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                            dirs.remove(d)
                            count += 1
                        except Exception:
                            pass
                for f in files:
                    if f.endswith((".pyc", ".pyo")):
                        try:
                            os.unlink(os.path.join(root, f))
                            count += 1
                        except Exception:
                            pass
    return count

def reset_llama_server_kv_cache():
    """Signals local llama-servers (Spark & Qwen) to release all cached slots and reset context."""
    for api_url in [SPARK_API_URL, QWEN_API_URL]:
        try:
            url = f"{api_url}/slots/0?action=release"
            req = urllib.request.Request(url, data=b"", headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=1) as resp:
                pass
        except Exception:
            pass
    return True

def purge_all_caches(verbose=True):
    if verbose:
        print(" [🧹] PotatoClaw Fresh Start: Purging old drafts, media, and KV cache...")
        
    # 1. Clean news drafts
    d_count = clean_directory(DRAFTS_DIR, "news_drafts/")
    
    # 2. Clean media output
    m_count = clean_directory(MEDIA_DIR, "media_output/")
    
    # 3. Clean python bytecode
    p_count = clean_pycache()
    
    # 4. Release local model server KV slot
    reset_llama_server_kv_cache()
    
    if verbose:
        print(" [✔] Ready: Zero-cache fresh state initialized for new run.\n")
        
    return {
        "drafts_cleared": d_count,
        "media_cleared": m_count,
        "pycache_cleared": p_count
    }

if __name__ == "__main__":
    purge_all_caches(verbose=True)
