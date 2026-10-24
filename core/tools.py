import os
import shutil
import sys
from pathlib import Path


class ToolMissing(Exception):
    pass


FFMPEG_HINT = (
    "ffmpeg isn't installed or can't be found. Install it with "
    "'winget install Gyan.FFmpeg' (Windows) or 'brew install ffmpeg' (Mac), "
    "then fully close and reopen the app."
)
HINTS = {
    "ffmpeg": FFMPEG_HINT,
    "ffprobe": FFMPEG_HINT,
    "ffplay": FFMPEG_HINT,
    "soffice": (
        "LibreOffice isn't installed or can't be found. Install it from "
        "libreoffice.org, then fully close and reopen the app."
    ),
    "tesseract": (
        "Tesseract OCR isn't installed. Install it with "
        "'winget install UB-Mannheim.TesseractOCR' (Windows) or 'brew install tesseract' (Mac), "
        "then fully close and reopen the app."
    ),
        "mpv": (
        "The in-app video player needs mpv. Install it with "
        "'winget install mpv' (Windows) or 'brew install mpv' (Mac), "
        "then fully close and reopen the app."
    ),
}


def app_dir():
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def _extra_folders(name):
    folders = []

    if sys.platform == "darwin":
        folders.extend([Path("/opt/homebrew/bin"), Path("/usr/local/bin")])
        if name == "mpv":
            folders.append(Path("/Applications/mpv.app/Contents/MacOS"))
        return folders

    if os.name != "nt":
        return folders

    local = os.environ.get("LOCALAPPDATA")
    if local:
        winget = Path(local) / "Microsoft" / "WinGet"
        folders.append(winget / "Links")
        packages = winget / "Packages"
        if packages.is_dir():
            for package in packages.glob("Gyan.FFmpeg*"):
                folders.extend(package.glob("ffmpeg-*/bin"))
            for package in packages.glob("shinchiro.mpv*"):
                folders.extend(package.glob("mpv*"))

    if name == "soffice":
        for env in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(env)
            if base:
                folders.append(Path(base) / "LibreOffice" / "program")

    if name == "tesseract":
        for env in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(env)
            if base:
                folders.append(Path(base) / "Tesseract-OCR")
        if local:
            folders.append(Path(local) / "Programs" / "Tesseract-OCR")

    if name == "mpv":
        for env in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(env)
            if base:
                folders.append(Path(base) / "MPV Player")
        if local:
            folders.append(Path(local) / "Programs" / "MPV Player")

    return folders

def find_tool(name):
    exe = name + (".exe" if os.name == "nt" else "")
    own_folders = [app_dir() / "bin", Path(sys.executable).parent / "bin"]
    for folder in own_folders + _extra_folders(name):
        candidate = folder / exe
        if candidate.is_file():
            return str(candidate)
    return shutil.which(name)


def require_tool(name):
    path = find_tool(name)
    if path is None:
        raise ToolMissing(HINTS.get(name, f"{name} wasn't found."))
    return path


def tool_status():
    return {name: find_tool(name)
            for name in ("ffmpeg", "ffprobe", "ffplay", "soffice",
                         "tesseract", "brew", "mpv")}