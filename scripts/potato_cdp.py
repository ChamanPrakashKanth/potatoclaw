#!/usr/bin/env python3
"""
PotatoClaw Chrome DevTools Protocol (CDP) Engine
Deterministic, zero-dependency pure Python CDP client for automated X (Twitter) thread creation.
Connects directly to Chrome/Edge debugging port (9222/9223).
Automates the exact user workflow:
  1. Types Post 1 into tweetTextarea_0
  2. Clicks the [+] 'Add post' button (addButton)
  3. Types Post 2 into tweetTextarea_1
  4. Clicks [+], types Post 3
  5. Clicks [+], types Post 4
  6. Clicks [+], types Post 5 (and up to all news / thread posts)
  7. Enforces the PotatoClaw Submit Gate (holds draft safely unless allow_submit=True)
"""

import sys
sys.dont_write_bytecode = True

import os
import re
import ssl
import json
import time
import socket
import struct
import base64
import argparse
import subprocess
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple

# Windows UTF-8 stdout configuration
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

DEFAULT_CDP_PORT = 9222
FALLBACK_CDP_PORT = 9223

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
]

DEV_PROFILE_DIR = os.path.expandvars(r"%LOCALAPPDATA%\OpenClaw\BrowserCDP")


def copy_to_clipboard(text: str) -> bool:
    """Copies text to the Windows clipboard deterministically."""
    try:
        subprocess.run(['clip.exe'], input=text.strip().encode('utf-16le'), check=True)
        return True
    except Exception:
        pass
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text.strip())
        root.update()
        root.destroy()
        return True
    except Exception:
        return False


def open_url_direct(url: str) -> bool:
    """Direct zero-hang URL opening using native OS commands."""
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
        import webbrowser
        webbrowser.open(url, new=2)
        return True
    except Exception:
        return False


# =====================================================================
# 1. Pure Python Minimal RFC 6455 WebSocket Client
# =====================================================================

class MiniCDP:
    """
    Standard-library-only RFC 6455 WebSocket client for Chrome DevTools Protocol.
    Requires zero external pip packages.
    """
    def __init__(self, ws_url: str, timeout: float = 12.0):
        self.ws_url = ws_url
        self.timeout = timeout
        self.sock = None
        self._msg_id = 0
        self._connect()

    def _connect(self):
        parsed = urllib.parse.urlparse(self.ws_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)

        raw_sock = socket.create_connection((host, port), timeout=self.timeout)
        if parsed.scheme == "wss":
            ctx = ssl.create_default_context()
            self.sock = ctx.wrap_socket(raw_sock, server_hostname=host)
        else:
            self.sock = raw_sock

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parsed.path
        if parsed.query:
            path += "?" + parsed.query
        headers = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(headers.encode("ascii"))

        # Read HTTP handshake response
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(1024)
            if not chunk:
                raise ConnectionError("CDP WebSocket handshake failed: EOF")
            resp += chunk

        status_line = resp.split(b"\r\n")[0].decode("ascii", errors="replace")
        if " 101 " not in status_line:
            raise ConnectionError(f"CDP WebSocket handshake rejected: {status_line}")

    def send_raw_frame(self, opcode: int, payload: bytes):
        """Encodes and sends an RFC 6455 frame with client-side masking."""
        mask = os.urandom(4)
        length = len(payload)
        header = bytearray([0x80 | (opcode & 0x0F)])  # FIN=1
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack(">H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack(">Q", length))
        header.extend(mask)
        masked = bytearray(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(header + masked)

    def send_frame(self, text: str):
        """Sends a text frame (opcode 0x1)."""
        self.send_raw_frame(0x1, text.encode("utf-8"))

    def recv_frame(self) -> str:
        """Receives and decodes one RFC 6455 WebSocket frame."""
        try:
            header = self._recv_exact(2)
        except Exception:
            return ""
        opcode = header[0] & 0x0F
        has_mask = bool(header[1] & 0x80)
        payload_len = header[1] & 0x7F

        if payload_len == 126:
            payload_len = struct.unpack(">H", self._recv_exact(2))[0]
        elif payload_len == 127:
            payload_len = struct.unpack(">Q", self._recv_exact(8))[0]

        if has_mask:
            mask = self._recv_exact(4)
            data = self._recv_exact(payload_len)
            data = bytearray(b ^ mask[i % 4] for i, b in enumerate(data))
        else:
            data = self._recv_exact(payload_len)

        if opcode == 0x9:  # Ping frame -> reply with Pong
            try:
                self.send_raw_frame(0xA, data)
            except Exception:
                pass
            return self.recv_frame()

        if opcode == 0x8:  # Close frame
            return ""
        return data.decode("utf-8", errors="replace")

    def _recv_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("CDP WebSocket closed prematurely")
            buf.extend(chunk)
        return bytes(buf)

    def call(self, method: str, params: dict = None) -> dict:
        """Calls a CDP method and waits for its matching response."""
        self._msg_id += 1
        msg_id = self._msg_id
        req = {"id": msg_id, "method": method, "params": params or {}}
        self.send_frame(json.dumps(req))

        deadline = time.time() + self.timeout
        while time.time() < deadline:
            raw = self.recv_frame()
            if not raw:
                break
            try:
                resp = json.loads(raw)
                if resp.get("id") == msg_id:
                    return resp
            except json.JSONDecodeError:
                pass
        return {}

    def eval(self, js_expr: str) -> Any:
        """Evaluates a JavaScript expression in the page context via Runtime.evaluate."""
        resp = self.call("Runtime.evaluate", {
            "expression": js_expr,
            "returnByValue": True,
            "awaitPromise": True
        })
        result = resp.get("result", {}).get("result", {})
        return result.get("value")

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass


# =====================================================================
# 2. Browser Discovery & Launching
# =====================================================================

def is_cdp_listening(port: int = DEFAULT_CDP_PORT) -> bool:
    """Checks if a Chrome/Edge CDP endpoint is responding on the given port."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/json/version")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False

def get_active_cdp_port() -> Optional[int]:
    """Returns the port where CDP is listening, checking 9222 then 9223."""
    for p in [DEFAULT_CDP_PORT, FALLBACK_CDP_PORT]:
        if is_cdp_listening(p):
            return p
    return None

def launch_debug_browser(port: int = DEFAULT_CDP_PORT) -> bool:
    """Launches Chrome or Edge with remote debugging enabled."""
    if is_cdp_listening(port):
        return True

    browser_exe = None
    for path in CHROME_PATHS:
        if os.path.exists(path):
            browser_exe = path
            break

    if not browser_exe:
        print("[CDP] No supported browser executable found for auto-launch.")
        return False

    os.makedirs(DEV_PROFILE_DIR, exist_ok=True)
    args = [
        browser_exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={DEV_PROFILE_DIR}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        "https://x.com/compose/post"
    ]

    print(f"[CDP] Starting debug browser on port {port}...")
    try:
        if sys.platform == "win32":
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
            subprocess.Popen(args, creationflags=flags)
        else:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        for _ in range(15):
            time.sleep(0.5)
            if is_cdp_listening(port):
                print(f"[CDP] Successfully connected to browser on port {port}.")
                return True
    except Exception as e:
        print(f"[CDP] Failed to launch browser: {e}")

    return False


# =====================================================================
# 3. Tab Discovery & Selection
# =====================================================================

def get_tabs(port: int = DEFAULT_CDP_PORT) -> List[Dict[str, Any]]:
    """Fetches list of all active browser tabs via CDP /json/list."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/json/list")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

def get_or_create_x_tab(port: int = DEFAULT_CDP_PORT) -> Optional[str]:
    """
    Finds an existing X (Twitter) compose or home tab, or creates a new one at https://x.com/compose/post.
    Returns the WebSocket debugger URL for the target.
    """
    tabs = get_tabs(port)

    # 1. Prefer an existing compose tab
    for tab in tabs:
        if tab.get("type") == "page":
            url = tab.get("url", "").lower()
            if "x.com/compose" in url or "twitter.com/compose" in url:
                return tab.get("webSocketDebuggerUrl")

    # 2. Prefer any x.com tab
    for tab in tabs:
        if tab.get("type") == "page":
            url = tab.get("url", "").lower()
            if "x.com" in url or "twitter.com" in url:
                return tab.get("webSocketDebuggerUrl")

    # 3. Create a new tab on x.com/compose/post
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?https://x.com/compose/post", method="PUT")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("webSocketDebuggerUrl")
    except Exception:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?https://x.com/compose/post")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("webSocketDebuggerUrl")
        except Exception as e:
            print(f"[CDP] Could not create new tab: {e}")

    # Fallback to first available page tab
    for tab in tabs:
        if tab.get("type") == "page" and tab.get("webSocketDebuggerUrl"):
            return tab.get("webSocketDebuggerUrl")

    return None


# =====================================================================
# 4. Automated Thread Composer: Write -> Click [+] -> Write -> Click [+]
# =====================================================================

JS_ENSURE_COMPOSE = """
(() => {
    if (window.location.href.indexOf('compose') === -1) {
        let newPostBtn = document.querySelector('[data-testid="SideNav_NewTweet_Button"]') ||
                         document.querySelector('[aria-label="Post"]');
        if (newPostBtn) newPostBtn.click();
    }
    return Boolean(document.querySelector('[data-testid^="tweetTextarea_"], [role="textbox"]'));
})()
"""

def generate_focus_and_select_script(index: int) -> str:
    """Generates JS to focus tweetTextarea_{index} and prepare it for typing."""
    return f"""
    (() => {{
        let box = document.querySelector('[data-testid="tweetTextarea_{index}"]');
        if (!box) {{
            let boxes = Array.from(document.querySelectorAll('[role="textbox"]'));
            if (boxes.length > {index}) {{
                box = boxes[{index}];
            }} else if (boxes.length > 0) {{
                box = boxes[boxes.length - 1];
            }}
        }}
        if (!box) return false;
        box.focus();
        document.execCommand('selectAll', false, null);
        return true;
    }})()
    """

def generate_type_script(index: int, text: str) -> str:
    """Generates JS to focus tweetTextarea_{index} and insert text with React/Draft.js event dispatch."""
    clean_json_text = json.dumps(text)
    return f"""
    (() => {{
        let box = document.querySelector('[data-testid="tweetTextarea_{index}"]');
        if (!box) {{
            let boxes = Array.from(document.querySelectorAll('[role="textbox"]'));
            if (boxes.length > {index}) {{
                box = boxes[{index}];
            }} else if (boxes.length > 0) {{
                box = boxes[boxes.length - 1];
            }}
        }}
        if (!box) return {{ success: false, reason: "box_not_found" }};

        box.focus();
        document.execCommand('selectAll', false, null);
        let inserted = document.execCommand('insertText', false, {clean_json_text});

        if (!inserted || !box.textContent.trim()) {{
            box.textContent = {clean_json_text};
            box.dispatchEvent(new InputEvent('input', {{ bubbles: true, data: {clean_json_text}, inputType: 'insertText' }}));
            box.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}

        return {{ success: true, text_len: box.textContent.length }};
    }})()
    """

JS_CLICK_ADD_BUTTON = """
(() => {
    let btn = document.querySelector('[data-testid="addButton"]');

    if (!btn) {
        btn = document.querySelector('button[aria-label*="Add post"], button[aria-label*="Add another post"]');
    }

    if (!btn) {
        let btns = Array.from(document.querySelectorAll('button'));
        btn = btns.find(b => {
            let label = (b.getAttribute('aria-label') || '').toLowerCase();
            return label.includes('add') || label.includes('plus');
        });
    }

    if (btn) {
        btn.click();
        return { success: true };
    }
    return { success: false, reason: "add_button_not_found" };
})()
"""

JS_CLICK_POST_ALL = """
(() => {
    let btn = document.querySelector('[data-testid="tweetButton"]') ||
              document.querySelector('[data-testid="tweetButtonInline"]');
    if (!btn) {
        let btns = Array.from(document.querySelectorAll('button'));
        btn = btns.find(b => {
            let t = (b.innerText || '').toLowerCase();
            let a = (b.getAttribute('aria-label') || '').toLowerCase();
            return t.includes('post all') || t === 'post' || a.includes('post all');
        });
    }
    if (btn) {
        btn.click();
        return { success: true };
    }
    return { success: false, reason: "submit_button_not_found" };
})()
"""

JS_READ_COMPOSER_STATE = """
(() => {
    const boxes = Array.from(document.querySelectorAll('[data-testid^="tweetTextarea_"], [role="textbox"]'));
    const labels = Array.from(document.querySelectorAll('button')).map(button => ({
        text: (button.innerText || '').trim().toLowerCase(),
        aria: (button.getAttribute('aria-label') || '').trim().toLowerCase(),
    }));
    const addPostVisible = labels.some(({ text, aria }) =>
        text.includes('add post') || aria.includes('add post') || aria.includes('add another post') || aria.includes('plus'))
    );
    const submitVisible = labels.some(({ text, aria }) =>
        text.includes('post all') || aria.includes('post all')
    );
    const bodyText = (document.body && document.body.innerText || '').toLowerCase();
    return {
        count: boxes.length,
        texts: boxes.map(box => (box.innerText || box.textContent || '').trim()),
        add_post_visible: addPostVisible,
        submit_visible: submitVisible,
        sent: bodyText.includes('your post was sent') || bodyText.includes('your posts were sent'),
    };
})()
"""


def compose_x_thread_cdp(
    thread_parts: List[str],
    allow_submit: bool = False,
    port: Optional[int] = None
) -> Dict[str, Any]:
    """
    Automates multi-part X thread creation via Chrome DevTools Protocol:
      - Types post 1 (e.g. 1/5 or 1/1)
      - Clicks the [+] 'Add post' button
      - Types post 2 (e.g. 2/5 or 1/2)
      - Clicks [+], types post 3, 4, 5... up to all parts
      - Halts safely at Submit Gate unless allow_submit=True
    """
    if not thread_parts:
        return {"status": "ERROR", "message": "No thread parts provided."}

    if port:
        if not is_cdp_listening(port):
            return {
                "status": "CDP_NOT_AVAILABLE",
                "message": f"Chrome CDP is not active on port {port}."
            }
        cdp_port = port
    else:
        cdp_port = get_active_cdp_port()
        if not cdp_port:
            launched = launch_debug_browser(DEFAULT_CDP_PORT)
            if launched:
                cdp_port = DEFAULT_CDP_PORT
        if not cdp_port:
            return {
                "status": "CDP_NOT_AVAILABLE",
                "message": "Chrome CDP is not active on port 9222/9223. Please run start_chrome_cdp.bat."
            }

    ws_url = get_or_create_x_tab(cdp_port)
    if not ws_url:
        return {"status": "ERROR", "message": "Could not locate or open an X browser tab via CDP."}

    print(f"\n[CDP Thread Engine] Connected to Chrome tab on port {cdp_port}...")
    client = None
    try:
        client = MiniCDP(ws_url, timeout=12.0)

        def composer_state() -> Dict[str, Any]:
            state = client.eval(JS_READ_COMPOSER_STATE)
            return state if isinstance(state, dict) else {}

        def normalized_visible_text(value: Any) -> str:
            return re.sub(r"\s+", " ", str(value or "")).strip()

        # 1. Ensure on compose page
        current_url = client.eval("window.location.href") or ""
        if "x.com" not in current_url and "twitter.com" not in current_url:
            print("[CDP] Navigating tab to https://x.com/compose/post...")
            client.call("Page.navigate", {"url": "https://x.com/compose/post"})
            time.sleep(3.0)
        elif "compose" not in current_url:
            client.eval(JS_ENSURE_COMPOSE)
            time.sleep(1.0)

        # 2. Wait for first compose textbox to be ready
        ready = False
        for attempt in range(12):
            res = client.eval("Boolean(document.querySelector('[data-testid^=\"tweetTextarea_\"], [role=\"textbox\"]'))")
            if res:
                ready = True
                break
            time.sleep(0.8)

        if not ready:
            print("[CDP] Note: Textbox not immediately seen. Attempting navigation to https://x.com/compose/post...")
            client.call("Page.navigate", {"url": "https://x.com/compose/post"})
            time.sleep(2.5)

        total = len(thread_parts)
        print(f"[CDP Thread Engine] Writing {total} post(s) into X composer sequentially:")

        # 3. Sequencing Loop: Write post -> Click [+] -> Write post -> Click [+] ...
        filled_count = 0
        for idx, part_text in enumerate(thread_parts):
            post_num = idx + 1
            print(f"   [{post_num}/{total}] Typing post into box #{idx} ({len(part_text)} chars)...")

            # Try native CDP Input.insertText first for 100% natural keyboard events
            client.eval(generate_focus_and_select_script(idx))
            input_res = client.call("Input.insertText", {"text": part_text})

            # Verify if content was inserted, else use fallback DOM type script
            state = composer_state()
            visible_text = (state.get("texts") or [""])[idx] if idx < len(state.get("texts") or []) else ""

            if normalized_visible_text(visible_text) != normalized_visible_text(part_text):
                type_script = generate_type_script(idx, part_text)
                client.eval(type_script)

                state = composer_state()
                visible_text = (state.get("texts") or [""])[idx] if idx < len(state.get("texts") or []) else ""
            if normalized_visible_text(visible_text) != normalized_visible_text(part_text):
                return {
                    "status": "ERROR",
                    "message": f"Post {post_num}/{total} was not verified in composer state.",
                    "filled_parts": filled_count,
                }

            filled_count += 1

            # If there are subsequent posts, click the [+] 'Add post' button
            if post_num < total:
                time.sleep(0.5)
                print(f"   [+] Clicking 'Add post' (+) button to create box #{idx + 1}...")
                click_res = client.eval(JS_CLICK_ADD_BUTTON)
                expected_count = idx + 2
                for _ in range(10):
                    time.sleep(0.3)
                    state = composer_state()
                    if int(state.get("count", 0)) >= expected_count:
                        break
                else:
                    # Re-snapshot the visible state before any recovery click.
                    # A second click is allowed only when the refreshed DOM still
                    # exposes an Add post control; this avoids blind click loops.
                    print(f"   [!] Add post did not create box #{idx + 1}; visible state: {json.dumps(state, ensure_ascii=False)}")
                    if state.get("add_post_visible"):
                        print("   [*] Retrying Add post once after the refreshed composer snapshot...")
                        retry_res = client.eval(JS_CLICK_ADD_BUTTON)
                        for _ in range(10):
                            time.sleep(0.3)
                            state = composer_state()
                            if int(state.get("count", 0)) >= expected_count:
                                break
                        else:
                            return {
                                "status": "ERROR",
                                "message": f"Add post control did not expose composer box #{idx + 1} after recovery.",
                                "filled_parts": filled_count,
                                "visible_state": state,
                            }
                    else:
                        return {
                            "status": "ERROR",
                            "message": f"Add post control disappeared before composer box #{idx + 1} could be created.",
                            "filled_parts": filled_count,
                            "visible_state": state,
                        }

        print(f"\n[✔] Successfully typed all {filled_count}/{total} post(s) into X composer!")

        final_state = composer_state()
        final_texts = final_state.get("texts") or []
        if int(final_state.get("count", 0)) != total or any(
            normalized_visible_text(final_texts[idx] if idx < len(final_texts) else "") != normalized_visible_text(part)
            for idx, part in enumerate(thread_parts)
        ):
            return {
                "status": "ERROR",
                "message": "Final composer verification did not match the expected thread parts.",
                "filled_parts": filled_count,
                "visible_state": final_state,
            }

        # 4. Submit Gate Enforcement
        if not allow_submit:
            print("=" * 65)
            print(" [SUBMIT SAFETY GATE TRIGGERED]")
            print(f" All {total} thread posts have been written and [+] linked in X.")
            print(" Submission held safely for your review. Click 'Post all' to publish.")
            print("=" * 65)
            return {
                "status": "PREPARED_SAFE",
                "message": f"Successfully drafted all {total} thread posts in X composer.",
                "parts": total
            }
        else:
            print("[CDP] Explicit --allow-submit granted: Clicking 'Post all'...")
            time.sleep(1.0)
            submit_res = client.eval(JS_CLICK_POST_ALL)
            if not submit_res or not submit_res.get("success"):
                return {"status": "ERROR", "message": "Post all control was not found after final draft verification."}
            for _ in range(10):
                time.sleep(0.5)
                submitted_state = composer_state()
                if submitted_state.get("sent"):
                    return {
                        "status": "SUBMITTED",
                        "message": f"Submitted all {total} posts live to X and verified the sent confirmation.",
                        "parts": total
                    }
            return {
                "status": "SUBMIT_UNVERIFIED",
                "message": "Post all was activated, but X did not expose a sent confirmation in the verification window.",
                "parts": total
            }

    except Exception as e:
        print(f"[CDP] Error during thread composition: {e}")
        return {"status": "ERROR", "message": str(e)}
    finally:
        if client:
            client.close()


# =====================================================================
# 5. Console Fallback Script Generator (For Non-CDP Browsers)
# =====================================================================

def generate_browser_console_script(thread_parts: List[str]) -> str:
    """
    Generates a 1-click self-executing JavaScript snippet that the user can paste
    into DevTools Console (F12) on x.com to populate the thread automatically.
    """
    escaped_parts = json.dumps(thread_parts)
    return f"""
(() => {{
    const parts = {escaped_parts};
    let idx = 0;
    function typeNext() {{
        if (idx >= parts.length) {{
            console.log("PotatoClaw: All " + parts.length + " posts typed successfully!");
            return;
        }}
        let box = document.querySelector('[data-testid="tweetTextarea_' + idx + '"]');
        if (!box) {{
            let boxes = Array.from(document.querySelectorAll('[role="textbox"]'));
            box = boxes[idx] || boxes[boxes.length - 1];
        }}
        if (box) {{
            box.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, parts[idx]);
            idx++;
            if (idx < parts.length) {{
                setTimeout(() => {{
                    let addBtn = document.querySelector('[data-testid="addButton"]') ||
                                 document.querySelector('button[aria-label*="Add post"], button[aria-label*="Add another post"]');
                    if (addBtn) addBtn.click();
                    setTimeout(typeNext, 700);
                }}, 400);
            }}
        }} else {{
            console.error("PotatoClaw: Textbox not found for part " + (idx + 1));
        }}
    }}
    typeNext();
}})();
""".strip()


# =====================================================================
# 6. CLI Entrypoint
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="PotatoClaw Zero-Dependency Pure Python CDP Thread Engine for X")
    parser.add_argument("text", nargs="?", default=None, help="Thread text to compose, or 'auto' to curate #1 breaking news")
    parser.add_argument("--category", choices=["tech", "defence", "physics"], default="tech", help="Category for breaking news curation (default: tech)")
    parser.add_argument("--file", "-f", type=str, default=None, help="Path to text file (.txt/.md) to compose as a thread")
    parser.add_argument("--allow-submit", action="store_true", help="Submit live to X (default: hold safely at Submit Gate)")
    parser.add_argument("--port", type=int, default=None, help="CDP port (default: auto 9222/9223)")
    parser.add_argument("--no-numbering", action="store_true", help="Disable numbering (1/N, 2/N) on split thread parts")
    parser.add_argument("--console-script", action="store_true", help="Generate and copy 1-click browser console snippet (F12) to clipboard")
    args = parser.parse_args()

    # Import helper modules
    try:
        from potato_browser_agent import split_x_thread
    except ImportError:
        def split_x_thread(text, max_chars=280, add_numbering=False):
            return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]

    thread_text = args.text

    # Auto-curation mode
    if thread_text and thread_text.lower() in ["auto", "curate"]:
        try:
            from post_all_hub import craft_in_depth_news_thread
            from x_news_engine import fetch_category_news
            print(f"[*] Curating #1 breaking story in '{args.category.upper()}' for in-depth thread...")
            articles = fetch_category_news(args.category, max_items=1)
            if not articles:
                print("[!] No news articles found.")
                sys.exit(1)
            article = articles[0]
            print(f"[+] Selected: {article['title']} ({article['source']})")
            thread_text = craft_in_depth_news_thread(args.category, article)
        except Exception as e:
            print(f"[!] Could not curate breaking news: {e}")
            sys.exit(1)

    # File loading mode
    elif args.file:
        if not os.path.isfile(args.file):
            print(f"[!] File not found: {args.file}")
            sys.exit(1)
        try:
            with open(args.file, "r", encoding="utf-8", errors="replace") as f:
                thread_text = f.read().strip()
            print(f"[✔] Loaded {len(thread_text)} characters from {args.file}")
        except Exception as e:
            print(f"[!] Error reading file: {e}")
            sys.exit(1)

    # Fallback to interactive input if no text provided
    if not thread_text:
        try:
            thread_text = input("Enter text for X thread (or 'auto' for breaking news): ").strip()
        except EOFError:
            print("[!] No text provided.")
            sys.exit(1)
        if thread_text.lower() in ["auto", "curate"]:
            try:
                from post_all_hub import craft_in_depth_news_thread
                from x_news_engine import fetch_category_news
                articles = fetch_category_news("tech", max_items=1)
                thread_text = craft_in_depth_news_thread("tech", articles[0]) if articles else ""
            except Exception:
                pass

    if not thread_text:
        print("[!] No thread text provided.")
        sys.exit(1)

    # Split into parts
    parts = split_x_thread(thread_text, max_chars=280, add_numbering=not args.no_numbering)
    print(f"\n[✔] Deterministically split into {len(parts)} thread post(s) (Zero Word Cutoff):")
    print("-" * 65)
    for idx, p in enumerate(parts, 1):
        print(f" [Post {idx}/{len(parts)}] ({len(p)} chars):")
        print(p)
        print()
    print("-" * 65)

    # If user just wants the console script:
    if args.console_script:
        snippet = generate_browser_console_script(parts)
        copy_to_clipboard(snippet)
        print("\n[✔] 1-Click Browser Console Script copied to Windows clipboard!")
        print("    Paste this into Chrome/Edge DevTools Console (F12) on https://x.com/compose/post:\n")
        print(snippet)
        sys.exit(0)

    # Attempt direct CDP composition
    result = compose_x_thread_cdp(parts, allow_submit=args.allow_submit, port=args.port)

    if result.get("status") == "CDP_NOT_AVAILABLE":
        snippet = generate_browser_console_script(parts)
        copy_to_clipboard(snippet)
        print("\n" + "=" * 65)
        print(" [!] Chrome CDP endpoint was not reached on port 9222/9223.")
        print("     To activate full hands-free CDP: run 'start_chrome_cdp.bat'")
        print("     -> 1-Click Fallback: Console script COPIED to clipboard!")
        print("     -> Opening https://x.com/compose/post in browser...")
        print("     -> Press F12 (Console), then Ctrl+V and Enter to auto-type all posts!")
        print("=" * 65)
        open_url_direct("https://x.com/compose/post")
        sys.exit(0)
    elif result.get("status") in ["PREPARED_SAFE", "SUBMITTED"]:
        sys.exit(0)
    else:
        print(f"\n[!] CDP Thread Execution failed: {result.get('message')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
