import datetime
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path


def data_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            path = Path(base) / "Convertor"
        else:
            path = Path.home() / "AppData" / "Roaming" / "Convertor"
    elif sys.platform == "darwin":
        # MacOS standard path
        path = Path.home() / "Library" / "Application Support" / "Convertor"
    else:
        # Linux standard path
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        path = Path(base) / "Convertor"
        
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_exception(context=""):
    """Append the current error to log.txt so problems can be diagnosed later."""
    try:
        log = data_dir() / "log.txt"
        if log.exists() and log.stat().st_size > 500_000:
            log.unlink()
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"\n[{stamp}] {context}\n")
            f.write(traceback.format_exc())
    except OSError:
        pass


def load_config():
    try:
        return json.loads((data_dir() / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(data):
    try:
        path = data_dir() / "settings.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp.replace(path)
    except OSError:
        pass


def open_path(path):
    """Open a file or folder in whatever app Windows, Mac, or Linux uses for it."""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True
    except OSError:
        return False