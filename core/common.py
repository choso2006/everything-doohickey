from pathlib import Path

RESERVED = {"CON", "PRN", "AUX", "NUL"}
RESERVED |= {f"COM{i}" for i in range(1, 10)}
RESERVED |= {f"LPT{i}" for i in range(1, 10)}


class Cancelled(Exception):
    """Raised inside a job when the user presses Cancel."""


def unique_path(path):
    """Return `path`, or 'name (1).ext', 'name (2).ext'... if it's taken."""
    path = Path(path)
    if not path.exists():
        return path

    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def clean_name(text, default, strip_exts=()):
    """Turn whatever the user typed into a safe Windows file name (no extension)."""
    bad = '<>:"/\\|?*'
    name = "".join(c for c in str(text) if c not in bad and ord(c) >= 32).strip()
    for ext in strip_exts:
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
            break
    name = name.strip(" .")
    if not name or name.upper() in RESERVED:
        return default
    return name


def format_size(num_bytes):
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


def format_time(seconds):
    """83.4 -> '1:23', 3723 -> '1:02:03'"""
    seconds = max(0, int(round(float(seconds))))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_stamp(seconds):
    """83.456 -> '0:01:23.45' (the format the Trim boxes use)."""
    centis = int(max(0.0, float(seconds)) * 100)
    hours, rest = divmod(centis, 360000)
    minutes, rest = divmod(rest, 6000)
    return f"{hours}:{minutes:02d}:{rest / 100:05.2f}"


def to_seconds(text):
    """'45', '1:30' or '1:02:03.5' -> seconds as a number."""
    parts = str(text).strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"bad time: {text}")
    try:
        numbers = [float(p) for p in parts]
    except ValueError:
        raise ValueError(f"bad time: {text}")
    if any(n < 0 for n in numbers):
        raise ValueError("time can't be negative")

    seconds = 0
    for n in numbers:
        seconds = seconds * 60 + n
    return seconds
