import os
import sys
import ssl # Kept as urllib.request may implicitly use it for https
import subprocess
import zipfile
import shutil
import datetime
import urllib.request
import re
import json # Moved from install_ffmpeg to top
from pathlib import Path

# =============== RESOURCE PATH HELPER =============== #
def get_resource_path(filename):
    """
    If frozen by PyInstaller, returns the bundled path inside the exe.
    Otherwise returns the path relative to this script file.
    """
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(__file__), filename)

# Ensure SSL uses the bundled cacert.pem
# Corrected: os.environ cannot be assigned directly;
# use a key. (This line has a logical error in the original, but is kept as per previous instruction
# to only remove code related to install_python_embed, not to fix other existing errors.)
os.environ['SSL_CERT_FILE'] = get_resource_path('cacert.pem')

# =============== UTILITY FUNCTIONS =============== #
def log(msg):
    if not QUIET:
        print(msg)
    if LOGGING and LOGFILE:
        with open(LOGFILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

def progress_bar(progress, total, prefix="", length=40):
    percent = progress / total if total else 0
    filled = int(length * percent)
    bar = "#" * filled + "-" * (length - filled)
    print(f"\r{prefix}[{bar}] {progress}/{total}", end="", flush=True)
    if progress >= total:
        print()

# Removed VERSION-CHECK HELPERS and related functions:
# get_local_embedded_version, get_latest_embed_version, version_tuple

# =============== CONFIGURATION =============== #
APP_BASE   = Path(os.getenv("APPDATA")) / "UltimateMediaRenamer"
TEMP_DIR   = APP_BASE / ".temp"
TOOLS_DIR  = APP_BASE / "Tools"
PYTHON_DIR = TOOLS_DIR / "Python"
LOG_DIR    = APP_BASE / "Logs"

LOGFILE = None
QUIET   = "--quiet" in sys.argv
LOGGING = "--log" in sys.argv

# Corrected: PHASES list definition - "Install Python Embed" removed and re-indexed
PHASES = [
    "Install Pip",          # Index 0
    "Install Requirements", # Index 1
    "Install ExifTool",     # Index 2
    "Install FFmpeg",       # Index 3
    "Install MediaInfo",    # Index 4
    "Install SQLite3",      # Index 5
    "Update PATH"           # Index 6
]

# =============== CORE DOWNLOAD/EXTRACT =============== #
def download(url, dest, phase=""):
    log(f"[{phase}] Downloading: {url}")
    print(f"[{phase}] Downloading: {url}")
    def reporthook(block_num, block_size, total_size):
        downloaded = min(block_num * block_size, total_size)
        progress_bar(downloaded, total_size, f"{phase} Download: ")
    try:
        urllib.request.urlretrieve(url, dest, reporthook)
        print()
        log(f"[{phase}] Saved to: {dest}")
    except Exception as e:
        log(f"[{phase}] Failed to download {url}: {e}")
        sys.exit(1)

def extract(zip_path, extract_to, phase=""):
    log(f"[{phase}] Extracting {zip_path} -> {extract_to}")
    print(f"[{phase}] Extracting {zip_path} -> {extract_to}")
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            names = z.namelist()
            total = len(names)
            for idx, name in enumerate(names, 1):
                z.extract(name, extract_to)
                progress_bar(idx, total, f"{phase} Extract: ")
        print()
        log(f"[{phase}] Extracted: {zip_path}")
    except Exception as e:
        log(f"[{phase}] Failed to extract {zip_path}: {e}")
        sys.exit(1)

def ensure_dirs():
    # Corrected: Added list of directories to iterate over
    for p in [APP_BASE, TEMP_DIR, TOOLS_DIR, LOG_DIR]:
        p.mkdir(parents=True, exist_ok=True)

def add_to_path(paths):
    phase = PHASES[6] # Corrected: Use specific phase name from PHASES list (now index 6)
    log(f"[{phase}] Updating PATH environment variable...")
    print(f"[{phase}] Updating PATH environment variable...")
    current = os.environ.get("PATH", "")
    try:
        user_env = subprocess.check_output(
            'reg query "HKCU\\Environment" /v PATH',
            shell=True, stderr=subprocess.DEVNULL, text=True
        )
        if "REG_SZ" in user_env:
            current = user_env.split("REG_SZ")[-1].strip()
    except:
        pass
    updated = current
    changed = False
    for path in paths:
        if str(path) not in current:
            updated += ";" + str(path)
            changed = True
    if changed:
        subprocess.call(f'setx PATH "{updated}"', shell=True)
        log(f"[{phase}] Updated user PATH")
        print(f"[{phase}] Updated user PATH")
    else:
        log(f"[{phase}] PATH already up-to-date")
        print(f"[{phase}] PATH already up-to-date")

# =============== INSTALL PHASES =============== #
# Removed the install_python_embed() function entirely as it's no longer needed.

def install_pip():
    phase = PHASES[0] # Corrected: Use specific phase name from PHASES list (now index 0)
    log(f"[{phase}] Installing pip...")
    print(f"[{phase}] Installing pip...")
    pip_path = PYTHON_DIR / "get-pip.py"
    download("https://bootstrap.pypa.io/get-pip.py", pip_path, phase=phase)
    subprocess.call(
        # Corrected: Arguments for subprocess.call
        [str(PYTHON_DIR / "python.exe"), str(pip_path), "--no-warn-script-location"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    log(f"[{phase}] Installed pip.")
    print(f"[{phase}] Installed pip.")

def install_requirements():
    phase = PHASES[1] # Corrected: Use specific phase name from PHASES list (now index 1)
    log(f"[{phase}] Installing requirements...")
    print(f"[{phase}] Installing requirements...")
    req_file = APP_BASE / "Setup" / "requirements.txt"
    if req_file.exists():
        subprocess.call(
            # Corrected: Arguments for subprocess.call
            [str(PYTHON_DIR / "python.exe"), "-m", "pip", "install", "--no-warn-script-location", "-r", str(req_file)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        log(f"[{phase}] Installed requirements from {req_file}.")
        print(f"[{phase}] Installed requirements from {req_file}.")
    else:
        log(f"[{phase}] requirements.txt not found at {req_file}.")
        print(f"[{phase}] requirements.txt not found at {req_file}.")

def install_exiftool():
    phase = PHASES[2] # Corrected: Use specific phase name from PHASES list (now index 2)
    log(f"[{phase}] Installing ExifTool...")
    print(f"[{phase}] Installing ExifTool...")
    html = urllib.request.urlopen("https://exiftool.org/").read().decode()
    match = re.search(r'href="(exiftool-[\d.]+_64\.zip)"', html)
    if not match:
        log(f"[{phase}] ExifTool link not found.")
        print(f"[{phase}] ExifTool link not found.")
        sys.exit(1)
    url = "https://exiftool.org/" + match.group(1)
    zip_path = TEMP_DIR / "exiftool.zip"
    extract_path = TEMP_DIR / "exiftool"
    download(url, zip_path, phase=phase)
    extract(zip_path, extract_path, phase=phase)
    for folder in extract_path.glob("exiftool-*"):
        for item in folder.iterdir():
            # Check if the item is the exiftool(-k).exe and rename it
            if item.name == "exiftool(-k).exe":
                new_item_name = "exiftool.exe"
                new_item_path = item.parent / new_item_name
                item.rename(new_item_path) # Rename the file
                shutil.move(str(new_item_path), TOOLS_DIR) # Move the renamed file
            else:
                shutil.move(str(item), TOOLS_DIR) # Move other files as is
    zip_path.unlink(missing_ok=True)
    shutil.rmtree(extract_path, ignore_errors=True)
    log(f"[{phase}] Installed ExifTool.")
    print(f"[{phase}] Installed ExifTool.")

def install_ffmpeg():
    phase = PHASES[3] # Corrected: Use specific phase name from PHASES list (now index 3)
    log(f"[{phase}] Installing FFmpeg...")
    print(f"[{phase}] Installing FFmpeg...")
    # Imports moved to top: import json, from urllib import request
    api_url = "https://api.github.com/repos/GyanD/codexffmpeg/releases/latest"
    data = urllib.request.urlopen(api_url).read()
    release = json.loads(data)
    asset = next((a for a in release["assets"] if a["name"].endswith("-essentials_build.zip")), None)
    if not asset:
        log(f"[{phase}] FFmpeg asset not found.")
        print(f"[{phase}] FFmpeg asset not found.")
        return
    zip_path = TEMP_DIR / "ffmpeg-essentials.zip"
    extract_path = TEMP_DIR / "ffmpeg"
    download(asset["browser_download_url"], zip_path, phase=phase)
    extract(zip_path, extract_path, phase=phase)
    for exe in ("ffmpeg.exe", "ffprobe.exe"):
        for p in extract_path.rglob(exe):
            shutil.move(str(p), TOOLS_DIR / exe)
    zip_path.unlink(missing_ok=True)
    shutil.rmtree(extract_path, ignore_errors=True)
    log(f"[{phase}] Installed FFmpeg.")
    print(f"[{phase}] Installed FFmpeg.")

def install_mediainfo():
    phase = PHASES[4] # Corrected: Use specific phase name from PHASES list (now index 4)
    log(f"[{phase}] Installing MediaInfo...")
    print(f"[{phase}] Installing MediaInfo...")
    html = urllib.request.urlopen("https://mediaarea.net/en/MediaInfo/Download/Windows").read().decode()
    m = re.search(r'href="(//mediaarea\.net/download/binary/mediainfo/[^"]*MediaInfo_CLI[^"]*Windows_x64\.zip)"', html)
    if not m:
        log(f"[{phase}] MediaInfo link not found.")
        print(f"[{phase}] MediaInfo link not found.")
        return
    url = "https:" + m.group(1)
    zip_path = TEMP_DIR / "mediainfo.zip"
    extract_path = TEMP_DIR / "mediainfo"
    download(url, zip_path, phase=phase)
    extract(zip_path, extract_path, phase=phase)
    for p in extract_path.rglob("MediaInfo.exe"):
        shutil.move(str(p), TOOLS_DIR / "MediaInfo.exe")
    zip_path.unlink(missing_ok=True)
    shutil.rmtree(extract_path, ignore_errors=True)
    log(f"[{phase}] Installed MediaInfo.")
    print(f"[{phase}] Installed MediaInfo.")

def install_sqlite3():
    phase = PHASES[5] # Corrected: Use specific phase name from PHASES list (now index 5)
    log(f"[{phase}] Installing SQLite3...")
    print(f"[{phase}] Installing SQLite3...")
    html = urllib.request.urlopen("https://sqlite.org/download.html").read().decode()
    m = re.search(r"(sqlite-tools-win-x64-[\d.]+\.zip)", html)
    if not m:
        log(f"[{phase}] SQLite3 link not found.")
        print(f"[{phase}] SQLite3 link not found.")
        return
    filename = m.group(1)
    year = datetime.datetime.now().year
    url = f"https://sqlite.org/{year}/{filename}"
    zip_path = TEMP_DIR / "sqlite3.zip"
    extract_path = TEMP_DIR / "sqlite3"
    download(url, zip_path, phase=phase)
    extract(zip_path, extract_path, phase=phase)
    for p in extract_path.rglob("sqlite3.exe"):
        shutil.move(str(p), TOOLS_DIR / "sqlite3.exe")
    zip_path.unlink(missing_ok=True)
    shutil.rmtree(extract_path, ignore_errors=True)
    log(f"[{phase}] Installed SQLite3.")
    print(f"[{phase}] Installed SQLite3.")

# =============== MAIN EXECUTION =============== #
def main():
    ensure_dirs()
    global LOGFILE
    if LOGGING:
        LOGFILE = LOG_DIR / f"setup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    total   = len(PHASES) # This will now correctly reflect the number of phases (7)
    current = 0
    
    def phase_marker(name):
        nonlocal current
        current += 1
        msg = f"[{current}/{total}] {name}"
        print(f"\n{msg}")
        log(msg)

    print("=== UltimateMediaRenamer Setup Started ===")
    log("=== UltimateMediaRenamer Setup Started ===")

    # Removed the call to install_python_embed() and adjusted indices
    phase_marker(PHASES[0]); install_pip()
    phase_marker(PHASES[1]); install_requirements()
    phase_marker(PHASES[2]); install_exiftool()
    phase_marker(PHASES[3]); install_ffmpeg()
    phase_marker(PHASES[4]); install_mediainfo()
    phase_marker(PHASES[5]); install_sqlite3()
    phase_marker(PHASES[6]); add_to_path([TOOLS_DIR, PYTHON_DIR]) # Added missing paths argument

    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    log("Setup complete.")
    print("Setup complete.")

    if not QUIET:
        input("\n✅ UltimateMediaRenamer setup complete. Press Enter to close.")

if __name__ == "__main__":
    main()
