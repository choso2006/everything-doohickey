import subprocess
import sys
from pathlib import Path

from core.tools import find_tool


class MPVError(Exception):
    pass


_current_process = None


def mpv_available():
    return find_tool("mpv") is not None


def mpv_version():
    exe = find_tool("mpv")
    if not exe:
        return None
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        out = subprocess.check_output(
            [exe, "--version"], text=True, timeout=3, creationflags=flags,
        )
        return out.splitlines()[0] if out else "mpv"
    except Exception:
        return "mpv (version check failed)"


def _kill_previous():
    global _current_process
    if _current_process and _current_process.poll() is None:
        try:
            _current_process.terminate()
            try:
                _current_process.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                _current_process.kill()
        except Exception:
            pass
    _current_process = None


def spawn_standalone(path, start=None, end=None):
    """Launch mpv in its own window with its built-in on-screen controls."""
    global _current_process

    _kill_previous()

    exe = find_tool("mpv")
    if not exe:
        raise MPVError(
            "mpv isn't installed. Run `py fetch_mpv.py` in the app folder "
            "to download it."
        )

    p = Path(path)
    if not p.exists():
        raise MPVError(f"File not found: {p.name}")

    try:
        from core.media import probe
        info = probe(p)
        if not info.get("has_video"):
            raise MPVError(f"{p.name} has no video track.")
    except MPVError:
        raise
    except Exception:
        pass  # probe failed — let mpv try anyway

    args = [
        exe,
        "--no-config",
        "--no-terminal",
        "--osc=yes",
        "--osd-bar=yes",
        "--volume=80",
        "--keep-open=yes",
        f"--title=Convertor · {p.name}",
    ]
    # --ontop is a Windows-only convenience; macOS handles window focus natively.
    if sys.platform == "win32":
        args.append("--ontop=yes")
    if start and float(start) > 0:
        args.append(f"--start={float(start)}")
    if end and float(end) > float(start or 0):
        args.append(f"--end={float(end)}")
    args.append(str(p))

    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        _current_process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
    except Exception as e:
        raise MPVError(f"Couldn't launch mpv: {e}")


def close_all():
    _kill_previous()