import os
import sys
import json
import time
import urllib.request
import urllib.error

# ─────────────────────────────────────────────
#  CONFIG  — edit only these if needed
# ─────────────────────────────────────────────
GITHUB_USER   = "BAJISANTOKYO"
GITHUB_REPO   = "ClaudeAI-Community"
GITHUB_BRANCH = "main"
GITHUB_FOLDER = "OpenClaude"          # folder inside the repo
INSTALL_NAME  = "OpenClaude"          # name of the folder created in Documents
# ─────────────────────────────────────────────

API_BASE  = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents"
RAW_BASE  = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}"

DOCS_PATH = os.path.join(os.path.expanduser("~"), "Documents", INSTALL_NAME)


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    print("=" * 54)
    print("   OpenClaude Extension Installer")
    print("   github.com/BAJISANTOKYO/ClaudeAI-Community")
    print("=" * 54)
    print()


def progress_bar(done, total, width=40):
    pct  = done / total if total else 1
    fill = int(width * pct)
    bar  = "█" * fill + "░" * (width - fill)
    return f"[{bar}] {done}/{total}"


def fetch_file_list(folder_path):
    """Return list of (name, download_url) for all files in a repo folder (recursive)."""
    url = f"{API_BASE}/{folder_path}?ref={GITHUB_BRANCH}"
    req = urllib.request.Request(url, headers={"User-Agent": "OpenClaude-Installer/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            items = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"\n  [ERROR] GitHub API returned HTTP {e.code}")
        print(f"          Make sure the '{GITHUB_FOLDER}' folder exists in the repo.")
        input("\n  Press Enter to exit...")
        sys.exit(1)
    except Exception as e:
        print(f"\n  [ERROR] Could not reach GitHub: {e}")
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
        headers={"User-Agent": "OpenClaude-Installer/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    with open(dest_path, "wb") as f:
        f.write(data)


def main():
    clear()
    banner()

    print(f"  Destination  : {DOCS_PATH}")
    print(f"  Repository   : github.com/{GITHUB_USER}/{GITHUB_REPO}")
    print(f"  Source folder: /{GITHUB_FOLDER} (branch: {GITHUB_BRANCH})")
    print()
    print("  Fetching file list from GitHub...")

    files = fetch_file_list(GITHUB_FOLDER)

    if not files:
        print("\n  [ERROR] No files found in the OpenClaude folder.")
        input("  Press Enter to exit...")
        sys.exit(1)

    total   = len(files)
    done    = 0
    failed  = []

    print(f"  Found {total} file(s). Starting download...\n")
    time.sleep(0.5)

    for repo_path, dl_url in files:
        # Strip the leading folder name to get relative path inside install dir
        rel_path  = os.path.relpath(repo_path, GITHUB_FOLDER)
        dest_path = os.path.join(DOCS_PATH, rel_path)

        fname = os.path.basename(repo_path)
        print(f"  ↓  {fname:<30}  {progress_bar(done, total)}", end="\r")

        try:
            download_file(dl_url, dest_path)
            done += 1
        except Exception as e:
            failed.append((fname, str(e)))
            done += 1

    # Final status line
    print(f"  ✔  Done!{' ' * 40}  {progress_bar(done, total)}")
    print()

    if failed:
        print(f"  [WARNING] {len(failed)} file(s) failed to download:")
        for name, err in failed:
            print(f"    - {name}: {err}")
    else:
        print("  All files downloaded successfully!")

    print()
    print("═" * 54)
    print("  HOW TO LOAD IN CHROME:")
    print("  1. Open Chrome → chrome://extensions")
    print("  2. Enable 'Developer mode' (top right toggle)")
    print("  3. Click 'Load unpacked'")
    print(f"  4. Select this folder:")
    print(f"     {DOCS_PATH}")
    print("═" * 54)
    print()
    input("  Press Enter to exit...")


if __name__ == "__main__":
    main()
