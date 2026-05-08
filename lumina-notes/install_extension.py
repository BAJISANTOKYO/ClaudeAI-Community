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

# -- Windows Subprocess Silencing ---------------------------------------------
# Prevents flashing black cmd/powershell windows during background tasks
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

def run_silent(cmd, **kwargs):
    return subprocess.run(cmd, creationflags=CREATE_NO_WINDOW, **kwargs)

def popen_silent(cmd, **kwargs):
    return subprocess.Popen(cmd, creationflags=CREATE_NO_WINDOW, **kwargs)
# -----------------------------------------------------------------------------

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
    print()
    print("  " + "━" * 50)
    print("   ✨ Lumina Notes - Auto Extension Installer ✨")
    print("  " + "━" * 50)
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
        "ext_url": "edge://extensions/",
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
#  DEVELOPER MODE DETECTION  (screenshot pixel-colour scan)
# -----------------------------------------------------------------------------

def is_dev_mode_on():
    """
    Take a screenshot and scan for the Developer Mode toggle being ON.

    The toggle is a small coloured pill/checkbox in the top-right corner
    of the extensions page CONTENT area (below the browser toolbar).

    We deliberately scan only a narrow horizontal band at the very top of
    the page content (just beneath the browser chrome) to avoid false
    positives from Edge/Chrome's own blue toolbar buttons.

    Returns True  -> blue toggle detected  -> dev mode is ON  (skip)
    Returns False -> no blue toggle found  -> dev mode is OFF (enable it)
    """
    try:
        import pyautogui
        try:
            # pyrefly: ignore [missing-import]
            from PIL import Image as _PILImage  # noqa: confirm Pillow is present
        except ImportError:
            run_silent([sys.executable, "-m", "pip", "install", "Pillow", "-q"], capture_output=True)

        shot = pyautogui.screenshot().convert("RGB")   # always 3-channel
        sw_w, sw_h = shot.size

        # The extensions-page header (with the Dev Mode toggle) sits in roughly
        # y = 8%..20% of the screen height, right half of the screen.
        # We stay BELOW the browser toolbar (top ~8%) to avoid false positives.
        top    = int(sw_h * 0.08)
        bottom = int(sw_h * 0.22)
        left   = sw_w * 3 // 5          # right-ish: toggle is on the far right
        region = shot.crop((left, top, sw_w, bottom))
        region = region.convert("RGB")
        px     = region.load()
        rw, rh = region.size

        for y in range(0, rh, 1):       # every pixel row (band is small)
            for x in range(0, rw, 2):   # every other column
                r, g, b = px[x, y]
                # Edge toggle ON:   #0078D4 -> R 0-30,  G 100-145, B 195-225
                # Chrome toggle ON: #1A73E8 -> R 20-50, G 100-135, B 220-245
                edge_blue   = (r < 35  and 95  < g < 150 and 190 < b < 230)
                chrome_blue = (r < 55  and 95  < g < 145 and 215 < b < 250)
                if edge_blue or chrome_blue:
                    return True
        return False
    except Exception:
        return False   # on any error, assume OFF -> attempt to enable


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
        print("  -> Installing required dependency (pyautogui)...")
        run_silent([sys.executable, "-m", "pip", "install", "pyautogui", "-q"], capture_output=True)
        import pyautogui

    pyautogui.FAILSAFE = False
    pyautogui.PAUSE    = 0.05   # minimal global pause

    ext_url = profile["ext_url"]

    # 1. Open browser
    print(f"  -> Launching {profile['name']}...")
    popen_silent([exe_path])
    time.sleep(2.5)   # wait for browser window to appear

    # Click center of screen to guarantee keyboard focus on the browser window
    sw = pyautogui.size()
    pyautogui.click(sw.width // 2, sw.height // 2)
    time.sleep(0.3)

    # 2. Navigate to extensions page via address bar
    #    NOTE: pyautogui.typewrite() silently drops special chars like ':' and '/'
    #    so we copy the URL to clipboard and paste it instead.
    run_silent(
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
    time.sleep(3.0)   # wait for extensions page to fully load

    # Scroll to top to ensure the Dev Mode toggle is visible on screen
    pyautogui.hotkey("ctrl", "home")
    time.sleep(0.3)

    # 3. Check Developer Mode state — scan for the blue toggle tick
    dev_mode_on = is_dev_mode_on()
    if dev_mode_on:
        print("  [i] Developer mode already ON (blue toggle detected) — skipping.")
    else:
        print("  [i] Developer mode OFF — enabling now.")

    # 4. Enable Developer Mode (if needed)
    if not dev_mode_on:
        run_silent(["powershell", "-Command", "Set-Clipboard -Value 'Developer mode'"], capture_output=True)
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "v")   # Instant paste instead of typing
        time.sleep(0.3)
        pyautogui.press("esc")          # Close search bar
        time.sleep(0.2)
        pyautogui.press("tab")          # Move focus to the toggle switch
        time.sleep(0.2)
        pyautogui.press("space")        # Toggle Dev Mode ON
        time.sleep(0.8)

    # 5. Click Load unpacked
    # Copy "Load unpacked" to clipboard for instant pasting
    run_silent(["powershell", "-Command", "Set-Clipboard -Value 'Load unpacked'"], capture_output=True)
    time.sleep(0.2)
    
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "v")   # Instant paste instead of typing
    time.sleep(0.3)
    pyautogui.press("esc")       # Close search bar
    time.sleep(0.2)
    
    # Press Enter (and Space just in case) to click the highlighted button
    pyautogui.press("space")
    time.sleep(0.1)
    pyautogui.press("enter")
    time.sleep(2.5)   # HUGE wait to ensure file dialog is fully open and focused

    # 6. Select the extension folder via Windows file dialog
    run_silent(
        ["powershell", "-Command", f"Set-Clipboard -Value '{ext_path}'"],
        capture_output=True
    )
    time.sleep(0.5)   # Wait for clipboard to sync
    
    # Force focus on the 'Folder' input box at the bottom using Alt+N,
    # then paste the absolute path and press Enter to instantly select and close.
    pyautogui.hotkey("alt", "n")
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.5)
    pyautogui.press("enter")
    time.sleep(1.5)   # Wait for dialog to close and extension to load

    # 7. Close browser window
    # Hold Alt, press F4, release Alt to ensure the OS registers it reliably
    pyautogui.keyDown("alt")
    time.sleep(0.1)
    pyautogui.press("f4")
    time.sleep(0.1)
    pyautogui.keyUp("alt")
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
