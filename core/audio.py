import shutil
from pathlib import Path

from core.common import format_size, format_time, to_seconds, unique_path
from core.media import probe, run_ffmpeg

AUDIO_ALLOWED = (
    ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus",
    ".wma", ".aiff", ".aif", ".amr", ".mka",
)
AUDIO_FORMATS = ["mp3", "m4a", "ogg", "opus", "wav", "flac", "aac", "aiff"]
LOSSY = (".mp3", ".m4a", ".aac", ".ogg", ".opus")


def codec_args(ext, kbps=192):
    """The ffmpeg codec settings for an audio format."""
    kbps = f"{int(kbps)}k"
    table = {
        ".mp3": ["-c:a", "libmp3lame", "-b:a", kbps],
        ".m4a": ["-c:a", "aac", "-b:a", kbps],
        ".aac": ["-c:a", "aac", "-b:a", kbps],
        ".ogg": ["-c:a", "libvorbis", "-b:a", kbps],
        ".opus": ["-c:a", "libopus", "-b:a", kbps],
        ".wav": ["-c:a", "pcm_s16le"],
        ".flac": ["-c:a", "flac"],
        ".aiff": ["-c:a", "pcm_s16be"],
    }
    if ext not in table:
        raise ValueError(f"Can't write {ext} audio.")
    return table[ext]


def _folder(output_folder):
    folder = Path(output_folder)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _atempo(factor):
    """ffmpeg's atempo only takes 0.5 to 2 at a time, so chain several."""
    steps = []
    while factor > 2.0:
        steps.append(2.0)
        factor /= 2.0
    while factor < 0.5:
        steps.append(0.5)
        factor /= 0.5
    steps.append(factor)
    return ",".join(f"atempo={s:.5f}" for s in steps)


def convert_audio(input_path, output_folder, fmt, kbps=192, progress=None, cancel=None):
    ext = "." + fmt.lstrip(".").lower()
    input_path = Path(input_path)
    codec = codec_args(ext, kbps)
    duration = probe(input_path)["duration"]

    new_path = unique_path(_folder(output_folder) / (input_path.stem + ext))
    run_ffmpeg(
        ["-i", str(input_path), "-vn", "-map", "0:a:0", "-map_metadata", "0",
         *codec, str(new_path)],
        total_seconds=duration, progress=progress, cancel=cancel, output=new_path,
    )
    return new_path


def trim_audio(input_path, output_folder, start, end, progress=None, cancel=None):
    start_s, end_s = to_seconds(start), to_seconds(end)
    if end_s <= start_s:
        raise ValueError("end must be after start")

    input_path = Path(input_path)
    duration = probe(input_path)["duration"]
    if duration and start_s >= duration:
        raise ValueError("start is past the end of the audio")
    if duration:
        end_s = min(end_s, duration)

    new_path = unique_path(
        _folder(output_folder) / f"{input_path.stem}_trimmed{input_path.suffix}"
    )
    run_ffmpeg(
        ["-ss", str(start), "-to", str(end), "-i", str(input_path),
         "-vn", "-map", "0:a:0", "-c", "copy", str(new_path)],
        total_seconds=end_s - start_s, progress=progress, cancel=cancel,
        output=new_path,
    )
    return new_path


def merge_audio(paths, output_folder, output_name="merged", fmt="mp3", kbps=192,
                progress=None, cancel=None):
    paths = [Path(p) for p in paths]
    if len(paths) < 2:
        raise ValueError("need at least 2 audio files")
    for p in paths:
        if not p.exists():
            raise FileNotFoundError(f"not found: {p}")

    ext = "." + fmt.lstrip(".").lower()
    codec = codec_args(ext, kbps)
    total = sum(probe(p)["duration"] for p in paths)

    args = []
    for p in paths:
        args += ["-i", str(p)]

    filters = []
    for i in range(len(paths)):
        filters.append(
            f"[{i}:a:0]aresample=44100,"
            f"aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]"
        )
    joined = "".join(f"[a{i}]" for i in range(len(paths)))
    filters.append(f"{joined}concat=n={len(paths)}:v=0:a=1[out]")

    new_path = unique_path(_folder(output_folder) / (Path(output_name).stem + ext))
    args += ["-filter_complex", ";".join(filters), "-map", "[out]", *codec,
             str(new_path)]
    run_ffmpeg(args, total_seconds=total, progress=progress, cancel=cancel,
               output=new_path)
    return new_path


def _same_format(input_path):
    """Keep the file's format if we can write it, otherwise use MP3."""
    ext = Path(input_path).suffix.lower()
    try:
        codec_args(ext)
        return ext
    except ValueError:
        return ".mp3"


def change_volume(input_path, output_folder, db=0.0, normalize=False,
                  kbps=192, progress=None, cancel=None):
    input_path = Path(input_path)
    if normalize:
        audio_filter = "loudnorm=I=-16:TP=-1.5:LRA=11"
        tag = "normalized"
    else:
        if abs(db) < 0.05:
            raise ValueError("Volume change is 0 dB, so nothing would change.")
        audio_filter = f"volume={db:.1f}dB"
        tag = f"{db:+.0f}dB"

    ext = _same_format(input_path)
    duration = probe(input_path)["duration"]
    new_path = unique_path(_folder(output_folder) / f"{input_path.stem}_{tag}{ext}")
    run_ffmpeg(
        ["-i", str(input_path), "-vn", "-map", "0:a:0", "-af", audio_filter,
         *codec_args(ext, kbps), str(new_path)],
        total_seconds=duration, progress=progress, cancel=cancel, output=new_path,
    )
    return new_path


def change_speed_audio(input_path, output_folder, factor=1.0, kbps=192,
                       progress=None, cancel=None):
    if not 0.25 <= factor <= 4:
        raise ValueError("Speed must be between 0.25x and 4x.")
    if abs(factor - 1.0) < 0.01:
        raise ValueError("Speed is 1x, so nothing would change.")

    input_path = Path(input_path)
    ext = _same_format(input_path)
    duration = probe(input_path)["duration"]
    new_path = unique_path(
        _folder(output_folder) / f"{input_path.stem}_{factor:g}x{ext}"
    )
    run_ffmpeg(
        ["-i", str(input_path), "-vn", "-map", "0:a:0", "-af", _atempo(factor),
         *codec_args(ext, kbps), str(new_path)],
        total_seconds=duration / factor, progress=progress, cancel=cancel,
        output=new_path,
    )
    return new_path


def describe_audio(path):
    info = probe(path)
    parts = []
    if info["duration"]:
        parts.append(format_time(info["duration"]))
    if info["acodec"]:
        parts.append(info["acodec"].upper())
    if info["bit_rate"]:
        parts.append(f"{info['bit_rate'] // 1000} kbps")
    if info["sample_rate"]:
        parts.append(f"{int(info['sample_rate']) / 1000:g} kHz")
    parts.append(format_size(info["size"]))
    return " \u00b7 ".join(parts)

def fade_audio(input_path, output_folder, fade_in=0.0, fade_out=0.0,
               kbps=192, progress=None, cancel=None):
    input_path = Path(input_path)
    duration = probe(input_path)["duration"]
    if fade_in <= 0 and fade_out <= 0:
        raise ValueError("Give at least one fade length.")

    filters = []
    if fade_in > 0:
        filters.append(f"afade=t=in:st=0:d={fade_in:.2f}")
    if fade_out > 0:
        if duration and fade_out >= duration:
            raise ValueError("Fade out is longer than the file.")
        start = (duration - fade_out) if duration else 0.0
        filters.append(f"afade=t=out:st={start:.2f}:d={fade_out:.2f}")

    ext = _same_format(input_path)
    new_path = unique_path(_folder(output_folder) / f"{input_path.stem}_faded{ext}")
    run_ffmpeg(
        ["-i", str(input_path), "-vn", "-map", "0:a:0",
         "-af", ",".join(filters), *codec_args(ext, kbps), str(new_path)],
        total_seconds=duration, progress=progress, cancel=cancel, output=new_path,
    )
    return new_path


def trim_silence(input_path, output_folder, threshold_db=-40.0, min_silence=0.5,
                 kbps=192, progress=None, cancel=None):
    input_path = Path(input_path)
    duration = probe(input_path)["duration"]
    if not -80 <= threshold_db <= -10:
        raise ValueError("Threshold should be between -80 and -10 dB.")
    if not 0.1 <= min_silence <= 10:
        raise ValueError("Minimum silence must be between 0.1 and 10 seconds.")

    one = (
        f"silenceremove=start_periods=1:start_threshold={threshold_db}dB:"
        f"start_duration={min_silence:.2f}"
    )
    chain = f"{one},areverse,{one},areverse"

    ext = _same_format(input_path)
    new_path = unique_path(_folder(output_folder) / f"{input_path.stem}_trimmed{ext}")
    run_ffmpeg(
        ["-i", str(input_path), "-vn", "-map", "0:a:0",
         "-af", chain, *codec_args(ext, kbps), str(new_path)],
        total_seconds=duration, progress=progress, cancel=cancel, output=new_path,
    )
    return new_path
