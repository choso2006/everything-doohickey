import io
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from core.appdata import open_path
from core.common import Cancelled
from core.tools import find_tool, require_tool

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _delete_quietly(path):
    if path is None:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def run_ffmpeg(args, total_seconds=None, progress=None, cancel=None, output=None):
    """Run ffmpeg, report progress (0 to 1), honour cancel, clean up on failure."""
    command = [
        require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin",
        "-y", "-progress", "pipe:1", "-nostats", *args,
    ]
    cancelled = False

    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as error_log:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=error_log,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=NO_WINDOW,
        )
        try:
            for line in process.stdout:
                if cancel and cancel():
                    cancelled = True
                    process.terminate()
                    break
                if progress and total_seconds:
                    key, _, value = line.strip().partition("=")
                    if key == "out_time_ms" and value.lstrip("-").isdigit():
                        done_seconds = max(0, int(value)) / 1_000_000
                        progress(min(done_seconds / total_seconds, 1.0))
        except BaseException:
            process.kill()
            process.wait()
            _delete_quietly(output)
            raise

        process.wait()
        error_log.seek(0)
        message = error_log.read().strip()

    if cancelled:
        _delete_quietly(output)
        raise Cancelled()
    if process.returncode != 0:
        _delete_quietly(output)
        raise RuntimeError(message or "ffmpeg failed")
    if progress:
        progress(1.0)


def run_ffprobe(args):
    command = [require_tool("ffprobe"), "-hide_banner", "-loglevel", "error", *args]
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8",
        errors="replace", creationflags=NO_WINDOW,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    return result.stdout


def parse_fraction(text):
    try:
        if "/" in text:
            top, bottom = text.split("/")
            return float(top) / float(bottom)
        return float(text)
    except (ValueError, ZeroDivisionError):
        return 0.0


def probe(path):
    """Everything we care about in a media file, as a plain dictionary."""
    path = Path(path)
    output = run_ffprobe(["-show_streams", "-show_format", "-of", "json", str(path)])
    data = json.loads(output)
    streams = data.get("streams", [])

    video = next(
        (s for s in streams
         if s.get("codec_type") == "video"
         and not s.get("disposition", {}).get("attached_pic")),
        None,
    )
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = data.get("format", {})

    duration = 0.0
    for source in (fmt, video or {}, audio or {}):
        try:
            duration = float(source.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        if duration > 0:
            break

    info = {
        "has_video": video is not None,
        "has_audio": audio is not None,
        "duration": duration,
        "size": int(fmt.get("size") or path.stat().st_size),
        "bit_rate": int(fmt.get("bit_rate") or 0),
        "width": None, "height": None, "fps": 0.0, "vcodec": None,
        "acodec": audio["codec_name"] if audio else None,
        "sample_rate": audio.get("sample_rate") if audio else None,
        "channels": audio.get("channels") if audio else None,
    }
    if video:
        fps_text = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
        info.update(
            width=video.get("width"), height=video.get("height"),
            fps=parse_fraction(fps_text), vcodec=video.get("codec_name"),
        )
    return info


def get_duration(path):
    try:
        return probe(path)["duration"]
    except (RuntimeError, ValueError, KeyError):
        return 0.0


def grab_frame(path, seconds, width=640):
    """One frame of a video as a PIL image (used by the preview panel).

    Asking for a moment at or past the end falls back to the last readable frame.
    """
    seconds = max(0.0, float(seconds))
    ffmpeg = require_tool("ffmpeg")

    def attempt(at):
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-ss", f"{at:.3f}", "-i", str(path), "-an", "-sn",
            "-frames:v", "1", "-vf", f"scale='min({int(width)},iw)':-2",
            "-f", "image2pipe", "-vcodec", "png", "-",
        ]
        result = subprocess.run(
            command, capture_output=True, timeout=45, creationflags=NO_WINDOW
        )
        return result.stdout

    data = attempt(seconds)
    if not data:
        duration = get_duration(path)
        for back in (0.5, 1.5):
            at = max(0.0, min(seconds, duration) - back) if duration else max(0.0, seconds - back)
            data = attempt(at)
            if data:
                break
    if not data:
        raise ValueError("Couldn't read a picture from this video.")
    return Image.open(io.BytesIO(data)).convert("RGB")


def grab_waveform(path, width=520, height=120):
    """A picture of an audio file's waveform."""
    command = [
        require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin",
        "-i", str(path), "-filter_complex",
        f"aformat=channel_layouts=mono,showwavespic=s={int(width)}x{int(height)}:colors=#3f8f84",
        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-",
    ]
    result = subprocess.run(
        command, capture_output=True, timeout=120, creationflags=NO_WINDOW
    )
    if not result.stdout:
        raise ValueError("Couldn't draw the sound wave for this file.")
    return Image.open(io.BytesIO(result.stdout)).convert("RGBA")


_player = None


def stop_player():
    global _player
    if _player is not None and _player.poll() is None:
        _player.terminate()
    _player = None


def play_media(path, start=None, end=None, audio_only=False):
    """Play a file in a separate ffplay window (falls back to the default player)."""
    global _player
    stop_player()

    ffplay = find_tool("ffplay")
    if ffplay is None:
        open_path(path)
        return False

    command = [ffplay, "-hide_banner", "-loglevel", "error", "-autoexit",
               "-window_title", Path(path).name]
    if audio_only:
        command += ["-nodisp"]
    else:
        command += ["-x", "960"]
    if start is not None:
        command += ["-ss", f"{float(start):.3f}"]
        if end is not None and float(end) > float(start):
            command += ["-t", f"{float(end) - float(start):.3f}"]
    command.append(str(path))

    _player = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True
