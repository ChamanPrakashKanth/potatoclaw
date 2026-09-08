#!/usr/bin/env python3
"""
PotatoClaw CDP Bridge for WSL2 Mirrored Networking.
Listens on 0.0.0.0:9222 so WSL OpenClaw Gateway can connect to Windows Edge/Chrome CDP on 127.0.0.1:9223.
"""
import os
import sys
import time
import socket
import select
import subprocess
import urllib.request
import json

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
TARGET_PORT = 9223
LISTEN_PORT = 9222
USER_DATA_DIR = os.path.expandvars(r"%LOCALAPPDATA%\OpenClaw\BrowserCDP")

def is_target_ready():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{TARGET_PORT}/json/version", timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False

def ensure_browser():
    if is_target_ready():
        return True
    
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    browser_bin = EDGE_PATH if os.path.exists(EDGE_PATH) else CHROME_PATH
    args = [
        browser_bin,
        f"--remote-debugging-port={TARGET_PORT}",
        f"--user-data-dir={USER_DATA_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ]
    subprocess.Popen(args)
    for _ in range(20):
        time.sleep(0.5)
        if is_target_ready():
            return True
    return False

def handle_client(client_sock):
    try:
        target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        target_sock.connect(("127.0.0.1", TARGET_PORT))
    except Exception as e:
        client_sock.close()
        return

    sockets = [client_sock, target_sock]
    try:
        while True:
            r, _, _ = select.select(sockets, [], sockets, 60)
            if not r:
                break
            for s in r:
                data = s.recv(65536)
                if not data:
                    return
                if s is client_sock:
                    # Rewrite Host header port from 9222 to 9223 if present
                    if b"Host: 127.0.0.1:9222" in data:
                        data = data.replace(b"Host: 127.0.0.1:9222", f"Host: 127.0.0.1:{TARGET_PORT}".encode())
                    elif b"Host: localhost:9222" in data:
                        data = data.replace(b"Host: localhost:9222", f"Host: 127.0.0.1:{TARGET_PORT}".encode())
                    target_sock.sendall(data)
                else:
                    # Rewrite response URLs from 9223 back to 9222
                    if f":{TARGET_PORT}".encode() in data:
                        data = data.replace(f":{TARGET_PORT}".encode(), f":{LISTEN_PORT}".encode())
                    client_sock.sendall(data)
    except Exception:
        pass
    finally:
        client_sock.close()
        target_sock.close()

def main():
    print(f"[CDP Bridge] Ensuring browser on port {TARGET_PORT}...")
    if not ensure_browser():
        print(f"[!] Failed to launch browser on port {TARGET_PORT}")
        sys.exit(1)
    print(f"[CDP Bridge] Browser ready on port {TARGET_PORT}")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", LISTEN_PORT))
    server.listen(64)
    print(f"[CDP Bridge] Listening on 0.0.0.0:{LISTEN_PORT} -> 127.0.0.1:{TARGET_PORT}")

    import threading
    while True:
        try:
            client, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(client,), daemon=True)
            t.start()
        except KeyboardInterrupt:
            break
        except Exception as e:
            time.sleep(0.1)

if __name__ == "__main__":
    main()
