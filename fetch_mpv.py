"""Download mpv.exe into bin/ so the embedded player works from source.

Run:  py fetch_mpv.py

This is a dev-machine helper only. The GitHub Actions build downloads mpv
automatically for release users, so they never run this.
"""
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

BIN = Path(__file__).parent / "bin"
MPV = BIN / "mpv.exe"


def find_7z():
    """Find the full 7z.exe (7zr.exe can't handle BCJ2, which shinchiro uses)."""
    candidates = [
        shutil.which("7z"),
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def install_7zip():
    print("7-Zip not found. Installing silently (one-time, ~5 MB)...")
    result = subprocess.run(
        ["winget", "install", "--id", "7zip.7zip", "--exact",
         "--silent", "--accept-package-agreements", "--accept-source-agreements"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(
            "Couldn't install 7-Zip automatically.\n"
            "Install it from https://www.7-zip.org/ and rerun this script."
        )
    return find_7z()


def main():
    BIN.mkdir(exist_ok=True)
    if MPV.exists():
        print(f"Already have mpv: {MPV}")
        return

    print("Fetching latest mpv release from GitHub...")
    req = urllib.request.Request(
        "https://api.github.com/repos/shinchiro/mpv-winbuild-cmake/releases/latest",
        headers={"User-Agent": "convertor-fetch"},
    )
    with urllib.request.urlopen(req) as r:
        rel = json.load(r)

    asset = next(
        (a for a in rel["assets"]
         if a["name"].startswith("mpv-x86_64-v3-") and a["name"].endswith(".7z")),
        None,
    )
    if not asset:
        raise SystemExit("No mpv .7z asset in the latest release.")

    archive = BIN / "mpv.7z"
    if not archive.exists():
        size_mb = asset["size"] // 1024 // 1024
        print(f"Downloading {asset['name']} ({size_mb} MB)...")
        urllib.request.urlretrieve(asset["browser_download_url"], archive)
    else:
        print(f"Reusing existing {archive.name}")

    seven_zip = find_7z()
    if seven_zip is None:
        seven_zip = install_7zip()
    if seven_zip is None:
        raise SystemExit("Still couldn't find 7-Zip. Install manually from 7-zip.org.")

    print(f"Extracting with: {seven_zip}")
    extract_dir = BIN / "_mpv_tmp"
    extract_dir.mkdir(exist_ok=True)

    result = subprocess.run(
        [seven_zip, "x", str(archive), f"-o{extract_dir}", "-y"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"7-Zip failed:\n{result.stderr or result.stdout}")

    found = next(extract_dir.rglob("mpv.exe"), None)
    if not found:
        raise SystemExit("mpv.exe not found inside the archive.")

    shutil.move(str(found), str(MPV))
    archive.unlink()
    shutil.rmtree(extract_dir, ignore_errors=True)

    print(f"\nDone. mpv is at: {MPV}")
    print("Run `py main.py` and the video player will be the embedded one.")


if __name__ == "__main__":
    main()