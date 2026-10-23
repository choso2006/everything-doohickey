import os
import shutil
import tempfile
from pathlib import Path

from core.audio import codec_args as audio_codec_args
from core.common import (
    Cancelled, format_size, format_time, to_seconds, unique_path,
)
from core.media import probe, run_ffmpeg

VIDEO_ALLOWED = (
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v",
    ".mpg", ".mpeg", ".3gp", ".ts", ".mts", ".m2ts", ".ogv", ".gif",
)
VIDEO_FORMATS = ["mp4", "mkv", "mov", "avi", "webm"]
EVEN_SCALE = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
HEIGHT_STEPS = (1080, 720, 480, 360, 240)


def _folder(output_folder):
    folder = Path(output_folder)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def scale_filter(max_height=None):
    """Even-sized output, optionally capped in height (never enlarges)."""
    if max_height:
        return f"scale=-2:'min({int(max_height)},2*trunc(ih/2))'"
    return EVEN_SCALE


def video_codec_args(ext, crf):
    if ext == ".webm":
        return [
            "-c:v", "libvpx-vp9", "-crf", str(int(crf) + 8), "-b:v", "0",
            "-row-mt", "1", "-cpu-used", "4", "-pix_fmt", "yuv420p",
            "-c:a", "libopus", "-b:a", "128k",
        ]
    audio = ["-c:a", "libmp3lame", "-b:a", "192k"] if ext == ".avi" else [
        "-c:a", "aac", "-b:a", "160k"]
    args = [
        "-vf", EVEN_SCALE, "-c:v", "libx264", "-preset", "medium",
        "-crf", str(int(crf)), "-pix_fmt", "yuv420p", *audio,
    ]
    if ext in (".mp4", ".mov", ".m4v"):
        args += ["-movflags", "+faststart"]
    return args


def convert_video(input_path, output_folder, target_format, crf=23,
                  fast_copy=False, progress=None, cancel=None):
    ext = "." + target_format.lstrip(".").lower()
    if ext[1:] not in VIDEO_FORMATS:
        raise ValueError(f"Can't write {ext} video.")

    input_path = Path(input_path)
    new_path = unique_path(_folder(output_folder) / (input_path.stem + ext))

    args = ["-i", str(input_path), "-map", "0:v:0", "-map", "0:a:0?", "-sn"]
    if fast_copy:
        args += ["-c", "copy"]
        if ext in (".mp4", ".mov", ".m4v"):
            args += ["-movflags", "+faststart"]
    else:
        args += video_codec_args(ext, crf)
    args.append(str(new_path))

    run_ffmpeg(
        args, total_seconds=probe(input_path)["duration"],
        progress=progress, cancel=cancel, output=new_path,
    )
    return new_path


def compress_video(input_path, output_folder, crf=26, max_height=None,
                   progress=None, cancel=None):
    input_path = Path(input_path)
    new_path = unique_path(_folder(output_folder) / f"{input_path.stem}_compressed.mp4")

    run_ffmpeg(
        ["-i", str(input_path), "-map", "0:v:0", "-map", "0:a:0?", "-sn",
         "-vf", scale_filter(max_height), "-c:v", "libx264", "-preset", "medium",
         "-crf", str(int(crf)), "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(new_path)],
        total_seconds=probe(input_path)["duration"],
        progress=progress, cancel=cancel, output=new_path,
    )
    return new_path


def suggest_height(video_kbps, width, height, fps):
    """Pick a resolution that a tight bitrate can still make look decent."""
    fps = min(fps or 30, 30)
    for candidate in (height,) + HEIGHT_STEPS:
        if candidate > height:
            continue
        new_width = width * candidate / height
        bits_per_pixel = video_kbps * 1000 / (new_width * candidate * fps)
        if bits_per_pixel >= 0.06:
            return candidate
    return HEIGHT_STEPS[-1] if height > HEIGHT_STEPS[-1] else height


def compress_video_to_size(input_path, output_folder, target_mb,
                           progress=None, cancel=None):
    """Two-pass encode aimed at a file size, e.g. 'under 25 MB'."""
    input_path = Path(input_path)
    info = probe(input_path)
    if not info["has_video"]:
        raise ValueError(f"{input_path.name} has no video.")
    duration = info["duration"]
    if duration <= 0:
        raise ValueError("Can't read how long this video is.")

    target_bytes = int(float(target_mb) * 1024 * 1024)
    if info["size"] <= target_bytes:
        # already small enough: hand back an untouched copy
        copy_path = unique_path(_folder(output_folder) / input_path.name)
        shutil.copyfile(input_path, copy_path)
        return copy_path

    audio_kbps = 128 if info["has_audio"] else 0
    total_kbps = target_bytes * 8 / duration / 1000 * 0.95
    video_kbps = total_kbps - audio_kbps
    if info["has_audio"] and video_kbps < 80:
        audio_kbps = 48
        video_kbps = total_kbps - audio_kbps
    if video_kbps < 25:
        raise ValueError(
            f"{target_mb:g} MB is too small for {format_time(duration)} of video. "
            "Pick a bigger size or trim it first."
        )

    height = suggest_height(video_kbps, info["width"], info["height"], info["fps"])
    vf = scale_filter(height if height < info["height"] else None)

    folder = _folder(output_folder)
    new_path = unique_path(folder / f"{input_path.stem}_{float(target_mb):g}MB.mp4")
    work = tempfile.mkdtemp(prefix="convertor_")
    passlog = str(Path(work) / "pass")

    def stage(start, span):
        if progress is None:
            return None
        return lambda f: progress(start + f * span)

    def encode(kbps):
        base = [
            "-i", str(input_path), "-map", "0:v:0", "-sn", "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-b:v", f"{int(kbps)}k",
            "-pix_fmt", "yuv420p", "-passlogfile", passlog,
        ]
        audio = ["-map", "0:a:0?", "-c:a", "aac", "-b:a", f"{audio_kbps}k"]
        run_ffmpeg(
            base + ["-pass", "2"] + audio + ["-movflags", "+faststart", str(new_path)],
            total_seconds=duration, progress=stage(0.4, 0.6), cancel=cancel,
            output=new_path,
        )
        return base

    try:
        first_pass = [
            "-i", str(input_path), "-map", "0:v:0", "-sn", "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-b:v", f"{int(video_kbps)}k",
            "-pix_fmt", "yuv420p", "-passlogfile", passlog, "-pass", "1",
            "-an", "-f", "null", os.devnull,
        ]
        run_ffmpeg(first_pass, total_seconds=duration, progress=stage(0.0, 0.4),
                   cancel=cancel)
        encode(video_kbps)

        size = new_path.stat().st_size
        if size > target_bytes:
            smaller = video_kbps * target_bytes / size * 0.96
            if smaller < 25:
                raise ValueError("Couldn't get it that small without ruining it.")
            encode(smaller)
            size = new_path.stat().st_size
            if size > target_bytes:
                new_path.unlink(missing_ok=True)
                raise ValueError(
                    f"Closest I could get was {format_size(size)}. "
                    "Try a slightly bigger target."
                )
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return new_path


def extract_audio(input_path, output_folder, fmt=".mp3", kbps=192,
                  progress=None, cancel=None):
    ext = "." + fmt.lstrip(".").lower()
    codec = audio_codec_args(ext, kbps)
    input_path = Path(input_path)
    info = probe(input_path)
    if not info["has_audio"]:
        raise ValueError("This video has no sound.")

    new_path = unique_path(_folder(output_folder) / (input_path.stem + ext))
    run_ffmpeg(
        ["-i", str(input_path), "-vn", "-map", "0:a:0", *codec, str(new_path)],
        total_seconds=info["duration"], progress=progress, cancel=cancel,
        output=new_path,
    )
    return new_path


def trim_video(input_path, output_folder, start, end, precise=False,
               progress=None, cancel=None):
    start_s = to_seconds(start)
    end_s = to_seconds(end)
    if end_s <= start_s:
        raise ValueError("end must be after start")

    input_path = Path(input_path)
    duration = probe(input_path)["duration"]
    if duration:
        if start_s >= duration:
            raise ValueError("start is past the end of the video")
        end_s = min(end_s, duration)

    new_path = unique_path(
        _folder(output_folder) / f"{input_path.stem}_trimmed{input_path.suffix}"
    )
    args = ["-ss", str(start), "-to", str(end), "-i", str(input_path)]
    if not precise:
        args += ["-c", "copy", "-avoid_negative_ts", "make_zero"]
    args.append(str(new_path))

    run_ffmpeg(
        args, total_seconds=end_s - start_s, progress=progress, cancel=cancel,
        output=new_path,
    )
    return new_path


def remove_audio(input_path, output_folder, progress=None, cancel=None):
    input_path = Path(input_path)
    new_path = unique_path(
        _folder(output_folder) / f"{input_path.stem}_silent{input_path.suffix}"
    )
    run_ffmpeg(
        ["-i", str(input_path), "-map", "0:v:0", "-sn", "-c", "copy", "-an",
         str(new_path)],
        total_seconds=probe(input_path)["duration"], progress=progress,
        cancel=cancel, output=new_path,
    )
    return new_path


def change_speed(input_path, output_folder, factor=2.0, progress=None, cancel=None):
    from core.audio import _atempo

    if not 0.25 <= factor <= 4:
        raise ValueError("Speed must be between 0.25x and 4x.")
    if abs(factor - 1.0) < 0.01:
        raise ValueError("Speed is 1x, so nothing would change.")

    input_path = Path(input_path)
    info = probe(input_path)
    new_path = unique_path(_folder(output_folder) / f"{input_path.stem}_{factor:g}x.mp4")

    video = f"[0:v:0]{EVEN_SCALE},setpts=PTS/{factor:.5f}[v]"
    if info["has_audio"]:
        graph = video + f";[0:a:0]{_atempo(factor)}[a]"
        maps = ["-map", "[v]", "-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    else:
        graph = video
        maps = ["-map", "[v]"]

    run_ffmpeg(
        ["-i", str(input_path), "-filter_complex", graph, *maps,
         "-c:v", "libx264", "-preset", "medium", "-crf", "22",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(new_path)],
        total_seconds=info["duration"] / factor, progress=progress,
        cancel=cancel, output=new_path,
    )
    return new_path


def rotate_video(input_path, output_folder, degrees=0, flip_h=False, flip_v=False,
                 progress=None, cancel=None):
    """degrees is clockwise: 0, 90, 180 or 270."""
    filters = {0: [], 90: ["transpose=1"], 180: ["hflip", "vflip"],
               270: ["transpose=2"]}
    if degrees not in filters:
        raise ValueError("Rotation must be 0, 90, 180 or 270.")
    chain = list(filters[degrees])
    if flip_h:
        chain.append("hflip")
    if flip_v:
        chain.append("vflip")
    if not chain:
        raise ValueError("Pick a rotation or a flip.")
    chain.append(EVEN_SCALE)

    input_path = Path(input_path)
    new_path = unique_path(_folder(output_folder) / f"{input_path.stem}_rotated.mp4")
    run_ffmpeg(
        ["-i", str(input_path), "-map", "0:v:0", "-map", "0:a:0?", "-sn",
         "-vf", ",".join(chain), "-c:v", "libx264", "-preset", "medium",
         "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "copy",
         "-movflags", "+faststart", str(new_path)],
        total_seconds=probe(input_path)["duration"], progress=progress,
        cancel=cancel, output=new_path,
    )
    return new_path


def video_to_gif(input_path, output_folder, fps=12, width=480, start=None,
                 end=None, progress=None, cancel=None):
    input_path = Path(input_path)
    info = probe(input_path)
    start_s = to_seconds(start) if start not in (None, "") else 0.0
    end_s = to_seconds(end) if end not in (None, "") else info["duration"]
    if info["duration"]:
        end_s = min(end_s, info["duration"])
    if end_s <= start_s:
        raise ValueError("end must be after start")
    if end_s - start_s > 120:
        raise ValueError("GIFs longer than 2 minutes get enormous. Use start and end to pick a shorter part.")

    new_path = unique_path(_folder(output_folder) / f"{input_path.stem}.gif")
    graph = (
        f"fps={int(fps)},scale='min({int(width)},iw)':-2:flags=lanczos,"
        "split[a][b];[a]palettegen=stats_mode=diff[p];"
        "[b][p]paletteuse=dither=bayer:bayer_scale=5"
    )
    run_ffmpeg(
        ["-ss", f"{start_s:.3f}", "-to", f"{end_s:.3f}", "-i", str(input_path),
         "-an", "-sn", "-vf", graph, "-loop", "0", str(new_path)],
        total_seconds=end_s - start_s, progress=progress, cancel=cancel,
        output=new_path,
    )
    return new_path


def screenshot(input_path, output_folder, at=0, fmt=".png", progress=None, cancel=None):
    ext = "." + fmt.lstrip(".").lower()
    if ext not in (".png", ".jpg"):
        raise ValueError("Pick PNG or JPG.")
    input_path = Path(input_path)
    at = to_seconds(at) if isinstance(at, str) else float(at)
    duration = probe(input_path)["duration"]
    if duration and at >= duration:
        raise ValueError("That time is past the end of the video.")

    stamp = format_time(at).replace(":", "-")
    new_path = unique_path(_folder(output_folder) / f"{input_path.stem}_{stamp}{ext}")
    quality = ["-q:v", "2"] if ext == ".jpg" else []
    run_ffmpeg(
        ["-ss", f"{at:.3f}", "-i", str(input_path), "-an", "-sn", "-frames:v", "1",
         *quality, str(new_path)],
        progress=progress, cancel=cancel, output=new_path,
    )
    if not new_path.exists():
        raise ValueError("Couldn't read a picture at that point.")
    return new_path


def extract_frames(input_path, output_folder, every=5.0, fmt=".png",
                   progress=None, cancel=None):
    """One picture every N seconds, saved in its own subfolder."""
    ext = "." + fmt.lstrip(".").lower()
    if ext not in (".png", ".jpg"):
        raise ValueError("Pick PNG or JPG.")
    if every < 0.1:
        raise ValueError("Pick at least 0.1 seconds between pictures.")

    input_path = Path(input_path)
    duration = probe(input_path)["duration"]
    if duration / every > 2000:
        raise ValueError("That would make over 2000 pictures. Use a bigger gap.")

    target = _folder(Path(output_folder) / input_path.stem)
    pattern = target / f"{input_path.stem}_%04d{ext}"
    quality = ["-q:v", "2"] if ext == ".jpg" else []
    run_ffmpeg(
        ["-i", str(input_path), "-an", "-sn", "-vf", f"fps=1/{every:g}",
         *quality, str(pattern)],
        total_seconds=duration, progress=progress, cancel=cancel,
    )
    made = sorted(target.glob(f"{input_path.stem}_*{ext}"))
    if not made:
        raise ValueError("No pictures were made.")
    return made


def merge_videos(video_paths, output_folder, output_name="merged",
                 reencode=False, resolution=(1280, 720), fps=30, crf=23,
                 progress=None, cancel=None):
    video_paths = [Path(p) for p in video_paths]
    if len(video_paths) < 2:
        raise ValueError("need at least 2 videos")
    for p in video_paths:
        if not p.exists():
            raise FileNotFoundError(f"not found: {p}")

    folder = _folder(output_folder)
    infos = [probe(p) for p in video_paths]
    for p, info in zip(video_paths, infos):
        if not info["has_video"]:
            raise ValueError(f"{p.name} has no video stream")
    total = sum(info["duration"] for info in infos)
    base = Path(output_name).stem or "merged"

    if reencode:
        return _merge_reencode(video_paths, infos, folder, base, resolution,
                               fps, crf, total, progress, cancel)
    return _merge_fast(video_paths, infos, folder, base, total, progress, cancel)


def _merge_fast(paths, infos, output_folder, base, total, progress, cancel):
    suffixes = {p.suffix.lower() for p in paths}
    if len(suffixes) > 1:
        raise ValueError(
            "fast merge needs every video in the same format, but got: "
            + ", ".join(sorted(suffixes)) + ". Tick Re-encode and try again"
        )

    keys = ("vcodec", "width", "height", "fps", "has_audio", "acodec", "sample_rate")

    def signature(info):
        return tuple(round(info[k], 2) if k == "fps" else info[k] for k in keys)

    mismatched = [
        p.name for p, info in zip(paths[1:], infos[1:])
        if signature(info) != signature(infos[0])
    ]
    if mismatched:
        raise ValueError(
            "these don't match the first video (codec, size, frame rate or audio): "
            + ", ".join(mismatched) + ". Tick Re-encode and try again"
        )

    new_path = unique_path(output_folder / (base + paths[0].suffix))

    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        for p in paths:
            safe = str(p.resolve()).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{safe}'\n")
        list_name = f.name

    try:
        run_ffmpeg(
            ["-f", "concat", "-safe", "0", "-i", list_name, "-c", "copy",
             str(new_path)],
            total_seconds=total, progress=progress, cancel=cancel, output=new_path,
        )
    finally:
        os.remove(list_name)
    return new_path


def _merge_reencode(paths, infos, output_folder, base, resolution, fps, crf,
                    total, progress, cancel):
    if resolution is None:
        width, height = infos[0]["width"], infos[0]["height"]
    else:
        width, height = resolution
    width -= width % 2
    height -= height % 2
    if width < 2 or height < 2:
        raise ValueError("resolution is too small")

    if fps is None:
        fps = round(infos[0]["fps"], 3) or 30
    if not 1 <= fps <= 120:
        raise ValueError("fps must be between 1 and 120")
    if not 0 <= crf <= 51:
        raise ValueError("crf must be between 0 and 51")

    args = []
    for p in paths:
        args += ["-i", str(p)]

    filters = []
    for i, (p, info) in enumerate(zip(paths, infos)):
        filters.append(
            f"[{i}:v:0]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"fps={fps},setpts=PTS-STARTPTS[v{i}]"
        )
        if info["has_audio"]:
            filters.append(
                f"[{i}:a:0]aresample=44100,"
                f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"asetpts=PTS-STARTPTS[a{i}]"
            )
        else:
            if info["duration"] <= 0:
                raise ValueError(f"can't read the length of {p.name}")
            filters.append(
                f"anullsrc=r=44100:cl=stereo,atrim=duration={info['duration']},"
                f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"asetpts=PTS-STARTPTS[a{i}]"
            )

    joined = "".join(f"[v{i}][a{i}]" for i in range(len(paths)))
    filters.append(f"{joined}concat=n={len(paths)}:v=1:a=1[v][a]")

    new_path = unique_path(output_folder / (base + ".mp4"))
    args += [
        "-filter_complex", ";".join(filters), "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(new_path),
    ]
    run_ffmpeg(args, total_seconds=total, progress=progress, cancel=cancel,
               output=new_path)
    return new_path


def describe_video(path):
    info = probe(path)
    parts = []
    if info["width"]:
        parts.append(f"{info['width']}x{info['height']}")
    if info["fps"]:
        parts.append(f"{info['fps']:.0f} fps")
    if info["duration"]:
        parts.append(format_time(info["duration"]))
    codecs = [c.upper() for c in (info["vcodec"], info["acodec"]) if c]
    if codecs:
        parts.append(" + ".join(codecs))
    elif not info["has_audio"]:
        parts.append("no sound")
    parts.append(format_size(info["size"]))
    return " \u00b7 ".join(parts)

ASPECT_RATIOS = {
    "Original": None,
    "1:1 square": (1, 1),
    "9:16 portrait": (9, 16),
    "16:9 landscape": (16, 9),
    "4:5 portrait": (4, 5),
    "4:3 classic": (4, 3),
    "3:4 portrait": (3, 4),
}


def crop_video(input_path, output_folder, aspect=(1, 1), mode="crop",
               progress=None, cancel=None):
    """mode='crop' cuts edges to the ratio; mode='pad' adds black bars."""
    input_path = Path(input_path)
    info = probe(input_path)
    w, h = info["width"], info["height"]
    if not w or not h:
        raise ValueError("Can't read the video size.")
    num, den = aspect

    if mode == "crop":
        if w / h > num / den:
            ch, cw = h, round(h * num / den)
        else:
            cw, ch = w, round(w * den / num)
        cw -= cw % 2
        ch -= ch % 2
        vf = f"crop={cw}:{ch}:(iw-{cw})/2:(ih-{ch})/2"
    elif mode == "pad":
        # Keep the original width if it's wider, or the original height if it's taller
        if w / h > num / den:
            ph = round(w * den / num)
            pw = w
        else:
            pw = round(h * num / den)
            ph = h
        pw -= pw % 2
        ph -= ph % 2
        vf = (
            f"scale={pw}:{ph}:force_original_aspect_ratio=decrease,"
            f"pad={pw}:{ph}:(ow-iw)/2:(oh-ih)/2,setsar=1"
        )
    else:
        raise ValueError("Pick crop or pad.")

    new_path = unique_path(_folder(output_folder) / f"{input_path.stem}_{num}x{den}.mp4")
    run_ffmpeg(
        ["-i", str(input_path), "-map", "0:v:0", "-map", "0:a:0?", "-sn",
         "-vf", vf + ",scale=trunc(iw/2)*2:trunc(ih/2)*2",
         "-c:v", "libx264", "-preset", "medium", "-crf", "22",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
         "-movflags", "+faststart", str(new_path)],
        total_seconds=info["duration"], progress=progress, cancel=cancel,
        output=new_path,
    )
    return new_path


def replace_audio(video_path, audio_path, output_folder, mix=False,
                  progress=None, cancel=None):
    """Swap (or mix) the video's sound for another audio file. Video is copied."""
    video_path = Path(video_path)
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"not found: {audio_path}")

    info = probe(video_path)
    new_path = unique_path(_folder(output_folder) / f"{video_path.stem}_newaudio.mp4")

    args = ["-i", str(video_path), "-i", str(audio_path)]
    if mix and info["has_audio"]:
        args += [
            "-filter_complex",
            "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0[a]",
            "-map", "0:v:0", "-map", "[a]",
        ]
    else:
        args += ["-map", "0:v:0", "-map", "1:a:0"]

    args += [
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart", str(new_path),
    ]
    run_ffmpeg(
        args, total_seconds=info["duration"], progress=progress, cancel=cancel,
        output=new_path,
    )
    return new_path
