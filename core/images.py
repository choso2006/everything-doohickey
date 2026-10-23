import io
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageSequence
from pillow_heif import register_heif_opener

from core.common import format_size, unique_path

register_heif_opener()
Image.MAX_IMAGE_PIXELS = 500_000_000

ALLOWED = (
    ".jpg", ".jpeg", ".png", ".webp", ".avif", ".bmp",
    ".tif", ".tiff", ".gif", ".ico", ".heic", ".heif",
)
OUTPUT_FORMATS = ["jpg", "png", "webp", "avif", "heic", "bmp", "tiff", "gif", "ico"]
ANIMATED_OUT = (".gif", ".webp", ".png")
QUALITY_FORMATS = (".jpg", ".jpeg", ".webp", ".avif", ".heic", ".heif")
EXIF_FORMATS = (".jpg", ".jpeg", ".png", ".webp", ".avif", ".heic", ".heif")
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
PIL_NAMES = {
    ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP",
    ".avif": "AVIF", ".heic": "HEIF", ".heif": "HEIF",
}
RESAMPLE = Image.Resampling.LANCZOS


def _folder(output_folder):
    folder = Path(output_folder)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


# ---------- reading ----------

def load_frames(path):
    """Return (frames, durations_ms, loop). Still images are one frame."""
    with Image.open(path) as src:
        if not getattr(src, "is_animated", False):
            frame = ImageOps.exif_transpose(src)
            frame.load()
            return [frame], [0], 0

        frames, durations = [], []
        for frame in ImageSequence.Iterator(src):
            durations.append(frame.info.get("duration", 100) or 100)
            frames.append(frame.copy())
        return frames, durations, src.info.get("loop", 0)


def read_exif(path):
    """The photo's metadata as bytes (rotation note removed), or None."""
    try:
        with Image.open(path) as src:
            exif = src.getexif()
            if not exif:
                return None
            for tag in (0x8769, 0x8825):
                try:
                    exif.get_ifd(tag)
                except Exception:
                    pass
            exif.pop(0x0112, None)
            return exif.tobytes()
    except Exception:
        return None


# ---------- colour modes ----------

def normalize(im):
    """Put any image into RGB, RGBA, L or LA so every format can take it."""
    if im.mode in ("RGB", "RGBA", "L", "LA"):
        return im
    if im.mode.startswith("I;16") or im.mode in ("I", "F"):
        return im.point(lambda i: i * (1 / 256)).convert("L")
    if im.mode == "P":
        return im.convert("RGBA" if "transparency" in im.info else "RGB")
    if im.mode in ("PA",):
        return im.convert("RGBA")
    if im.mode == "1":
        return im.convert("L")
    return im.convert("RGB")


def flatten_on_white(im):
    """JPEG can't be see-through, so put the picture on a white background."""
    im = normalize(im)
    if im.mode == "RGB":
        return im
    if im.mode == "L":
        return im.convert("RGB")
    rgba = im.convert("RGBA")
    background = Image.new("RGB", rgba.size, "white")
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def square_pad(im):
    side = max(im.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    rgba = im.convert("RGBA")
    canvas.paste(rgba, ((side - rgba.width) // 2, (side - rgba.height) // 2))
    return canvas


def prepare_for(ext, im):
    im = normalize(im)
    if ext in (".jpg", ".jpeg"):
        return flatten_on_white(im)
    if ext in (".webp", ".avif", ".heic", ".heif", ".ico", ".bmp", ".gif"):
        if im.mode == "L":
            return im.convert("RGB")
        if im.mode == "LA":
            return im.convert("RGBA")
    return im


# ---------- writing ----------

def finalize(ext, frames, quality=None, exif=None, optimize=False):
    """Get frames ready for a format and work out the save() settings."""
    frames = [prepare_for(ext, f) for f in frames]
    opts = {}

    if ext in (".jpg", ".jpeg"):
        opts.update(quality=int(quality or 92), optimize=True)
    elif ext == ".webp":
        opts["quality"] = int(quality or 90)
    elif ext in (".avif", ".heic", ".heif"):
        opts["quality"] = int(quality or 85)
    elif ext == ".png":
        if optimize:
            opts["optimize"] = True
    elif ext in (".tif", ".tiff"):
        opts["compression"] = "tiff_lzw"
    elif ext == ".gif":
        opts["optimize"] = True
    elif ext == ".ico":
        frames = [square_pad(frames[0])]
        side = frames[0].width
        opts["sizes"] = [(s, s) for s in ICO_SIZES if s <= side] or [(side, side)]

    if exif and ext in EXIF_FORMATS and len(frames) == 1:
        opts["exif"] = exif
    return frames, opts


def save_frames(frames, durations, loop, path, opts):
    path = Path(path)
    ext = path.suffix.lower()
    if len(frames) > 1 and ext in ANIMATED_OUT:
        extra = {"save_all": True, "append_images": frames[1:], "duration": durations}
        if loop is None:
            if ext != ".gif":
                extra["loop"] = 1
        else:
            extra["loop"] = loop
        if ext == ".gif":
            extra["disposal"] = 2
        frames[0].save(path, **extra, **opts)
    else:
        frames[0].save(path, **opts)


# ---------- actions ----------

def convert_image(input_path, output_folder, target_format, quality=None,
                  keep_metadata=False):
    ext = "." + target_format.lstrip(".").lower()
    if ext[1:] not in OUTPUT_FORMATS:
        raise ValueError(f"Can't write {ext} files.")

    input_path = Path(input_path)
    frames, durations, loop = load_frames(input_path)
    exif = read_exif(input_path) if keep_metadata else None
    frames, opts = finalize(ext, frames, quality=quality, exif=exif)

    new_path = unique_path(_folder(output_folder) / (input_path.stem + ext))
    save_frames(frames, durations, loop, new_path, opts)
    return new_path


def compress_image(input_path, output_folder, quality=80, keep_metadata=False):
    input_path = Path(input_path)
    ext = input_path.suffix.lower()
    if ext in (".bmp", ".ico"):
        raise ValueError(
            f"{ext.upper()[1:]} files can't be compressed. Convert it to PNG, JPG or WebP instead."
        )

    frames, durations, loop = load_frames(input_path)
    exif = read_exif(input_path) if keep_metadata else None
    frames, opts = finalize(ext, frames, quality=quality, exif=exif, optimize=True)

    new_path = unique_path(_folder(output_folder) / input_path.name)
    save_frames(frames, durations, loop, new_path, opts)
    return new_path


def compress_image_to_size(input_path, output_folder, target_kb, keep_metadata=False):
    """Squeeze a picture under a size limit by lowering quality, then size."""
    input_path = Path(input_path)
    ext = input_path.suffix.lower()
    if ext not in QUALITY_FORMATS + (".png",):
        raise ValueError(
            f"Target size works for JPG, PNG, WebP, AVIF and HEIC. Convert {ext} to one of those first."
        )
    target = int(float(target_kb) * 1024)
    if target < 2048:
        raise ValueError("Target size is too small. Use at least 2 KB.")

    new_path = unique_path(_folder(output_folder) / input_path.name)
    if input_path.stat().st_size <= target:
        shutil.copyfile(input_path, new_path)
        return new_path

    frames, _, _ = load_frames(input_path)
    if len(frames) > 1:
        raise ValueError("Animated images can't be squeezed to a target size.")
    exif = read_exif(input_path) if keep_metadata else None
    base = prepare_for(ext, frames[0])

    def encode(img, quality=None):
        _, opts = finalize(ext, [img], quality=quality, exif=exif, optimize=True)
        buffer = io.BytesIO()
        img.save(buffer, format=PIL_NAMES[ext], **opts)
        return buffer.getvalue()

    def smaller_copy(scale):
        if scale >= 0.999:
            return base
        size = (max(1, round(base.width * scale)), max(1, round(base.height * scale)))
        return base.resize(size, RESAMPLE)

    def try_quality(img):
        """(best_data or None, size_at_lowest_quality)"""
        top = encode(img, 95)
        if len(top) <= target:
            return top, len(top)
        low = encode(img, 5)
        if len(low) > target:
            return None, len(low)
        lo, hi, best = 5, 95, low
        while hi - lo > 1:
            mid = (lo + hi) // 2
            data = encode(img, mid)
            if len(data) <= target:
                lo, best = mid, data
            else:
                hi = mid
        return best, len(low)

    def try_png(img):
        data = encode(img)
        if len(data) <= target:
            return data, len(data)
        small = img if img.mode in ("L", "LA") else (
            img.quantize(256, method=Image.Quantize.FASTOCTREE)
            if img.mode == "RGBA" else img.convert("RGB").quantize(256)
        )
        buffer = io.BytesIO()
        small.save(buffer, format="PNG", optimize=True)
        data = buffer.getvalue()
        return (data if len(data) <= target else None), len(data)

    attempt = try_png if ext == ".png" else try_quality
    scale, data = 1.0, None
    for _ in range(10):
        data, floor_size = attempt(smaller_copy(scale))
        if data is not None:
            break
        scale *= min(0.85, max(0.2, (target / floor_size) ** 0.5 * 0.95))
        if min(base.size) * scale < 24:
            break

    if data is None:
        raise ValueError(
            f"Couldn't get it under {format_size(target)} without making it tiny."
        )
    new_path.write_bytes(data)
    return new_path


def resize_image(input_path, output_folder, width=None, height=None,
                 percent=None, fit=None, keep_metadata=False):
    input_path = Path(input_path)
    ext = input_path.suffix.lower()
    frames, durations, loop = load_frames(input_path)
    w0, h0 = frames[0].size

    if percent is not None:
        nw, nh = round(w0 * percent / 100), round(h0 * percent / 100)
    elif fit is not None:
        ratio = min(fit[0] / w0, fit[1] / h0)
        nw, nh = round(w0 * ratio), round(h0 * ratio)
    elif width is not None and height is not None:
        nw, nh = width, height
    elif width is not None:
        nw, nh = width, round(h0 * width / w0)
    elif height is not None:
        nw, nh = round(w0 * height / h0), height
    else:
        raise ValueError("give a width, a height or a percent")

    nw, nh = max(1, int(nw)), max(1, int(nh))
    if nw * nh > 300_000_000:
        raise ValueError("That would make an enormous image.")

    resized = [normalize(f).resize((nw, nh), RESAMPLE) for f in frames]
    exif = read_exif(input_path) if keep_metadata else None
    resized, opts = finalize(ext, resized, exif=exif)

    new_path = unique_path(_folder(output_folder) / input_path.name)
    save_frames(resized, durations, loop, new_path, opts)
    return new_path


def rotate_image(input_path, output_folder, degrees=0, flip_h=False, flip_v=False,
                 keep_metadata=False):
    """degrees is clockwise: 0, 90, 180 or 270."""
    turns = {
        0: None,
        90: Image.Transpose.ROTATE_270,
        180: Image.Transpose.ROTATE_180,
        270: Image.Transpose.ROTATE_90,
    }
    if degrees not in turns:
        raise ValueError("Rotation must be 0, 90, 180 or 270.")
    if not degrees and not flip_h and not flip_v:
        raise ValueError("Pick a rotation or a flip.")

    input_path = Path(input_path)
    ext = input_path.suffix.lower()
    frames, durations, loop = load_frames(input_path)

    out = []
    for f in frames:
        f = normalize(f)
        if turns[degrees] is not None:
            f = f.transpose(turns[degrees])
        if flip_h:
            f = f.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if flip_v:
            f = f.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        out.append(f)

    exif = read_exif(input_path) if keep_metadata else None
    out, opts = finalize(ext, out, exif=exif)
    new_path = unique_path(_folder(output_folder) / input_path.name)
    save_frames(out, durations, loop, new_path, opts)
    return new_path




def adjust_image(input_path, output_folder, brightness=100, contrast=100,
                 color=100, grayscale=False, keep_metadata=False):
    """brightness, contrast and color are percentages (100 = unchanged)."""
    if (brightness, contrast, color, grayscale) == (100, 100, 100, False):
        raise ValueError("Nothing to change. Move a slider or tick Black and white.")

    input_path = Path(input_path)
    ext = input_path.suffix.lower()
    frames, durations, loop = load_frames(input_path)

    out = []
    for f in frames:
        f = normalize(f)
        alpha = f.getchannel("A") if f.mode in ("RGBA", "LA") else None
        rgb = f.convert("RGB")
        rgb = ImageEnhance.Brightness(rgb).enhance(brightness / 100)
        rgb = ImageEnhance.Contrast(rgb).enhance(contrast / 100)
        rgb = ImageEnhance.Color(rgb).enhance(color / 100)
        if grayscale:
            rgb = ImageOps.grayscale(rgb).convert("RGB")
        if alpha is not None:
            rgb.putalpha(alpha)
        out.append(rgb)

    exif = read_exif(input_path) if keep_metadata else None
    out, opts = finalize(ext, out, exif=exif)
    new_path = unique_path(_folder(output_folder) / input_path.name)
    save_frames(out, durations, loop, new_path, opts)
    return new_path


def load_font(size):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


WATERMARK_POSITIONS = [
    "Bottom right", "Bottom left", "Top right", "Top left", "Center", "Tiled",
]


def watermark_image(input_path, output_folder, text, position="Bottom right",
                    size_percent=5, opacity=60, color="white", keep_metadata=False):
    text = str(text).strip()
    if not text:
        raise ValueError("Type the watermark text.")
    if position not in WATERMARK_POSITIONS:
        raise ValueError("Unknown watermark position.")

    input_path = Path(input_path)
    ext = input_path.suffix.lower()
    frames, durations, loop = load_frames(input_path)

    alpha = int(255 * max(5, min(100, opacity)) / 100)
    fill = (255, 255, 255, alpha) if color == "white" else (0, 0, 0, alpha)
    outline = (0, 0, 0, alpha) if color == "white" else (255, 255, 255, alpha)

    out = []
    for f in frames:
        base = normalize(f).convert("RGBA")
        width, height = base.size
        font = load_font(max(10, round(width * size_percent / 100)))
        stroke = max(1, round(font.size / 14))
        probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        left, top, right, bottom = probe.textbbox((0, 0), text, font=font, stroke_width=stroke)
        tw, th = right - left, bottom - top

        layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        if position == "Tiled":
            pad = stroke * 2
            tile = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
            ImageDraw.Draw(tile).text(
                (pad - left, pad - top), text, font=font, fill=fill,
                stroke_width=stroke, stroke_fill=outline,
            )
            tile = tile.rotate(30, expand=True, resample=Image.Resampling.BICUBIC)
            step_x, step_y = int(tile.width * 1.25), int(tile.height * 1.6)
            for row, y in enumerate(range(-tile.height // 2, height, step_y)):
                shift = step_x // 2 if row % 2 else 0
                for x in range(-tile.width // 2 + shift, width, step_x):
                    layer.alpha_composite(
                        tile, (max(0, x), max(0, y)), (max(0, -x), max(0, -y))
                    )
        else:
            margin = round(min(width, height) * 0.03)
            x = {"left": margin, "right": width - tw - margin, "mid": (width - tw) // 2}
            y = {"top": margin, "bottom": height - th - margin, "mid": (height - th) // 2}
            spot = {
                "Bottom right": (x["right"], y["bottom"]),
                "Bottom left": (x["left"], y["bottom"]),
                "Top right": (x["right"], y["top"]),
                "Top left": (x["left"], y["top"]),
                "Center": (x["mid"], y["mid"]),
            }[position]
            ImageDraw.Draw(layer).text(
                (spot[0] - left, spot[1] - top), text, font=font, fill=fill,
                stroke_width=stroke, stroke_fill=outline,
            )
        out.append(Image.alpha_composite(base, layer))

    exif = read_exif(input_path) if keep_metadata else None
    out, opts = finalize(ext, out, exif=exif)
    new_path = unique_path(_folder(output_folder) / input_path.name)
    save_frames(out, durations, loop, new_path, opts)
    return new_path


def strip_metadata(input_path, output_folder):
    """Rebuild the picture from its raw pixels so no hidden info comes along."""
    input_path = Path(input_path)
    ext = input_path.suffix.lower()
    frames, durations, loop = load_frames(input_path)

    clean = []
    for f in frames:
        f = normalize(f)
        clean.append(Image.frombytes(f.mode, f.size, f.tobytes()))
    clean, opts = finalize(ext, clean, quality=95)

    new_path = unique_path(_folder(output_folder) / input_path.name)
    save_frames(clean, durations, loop, new_path, opts)
    return new_path


def images_to_animation(paths, output_folder, output_name="animation", fmt="gif",
                        frame_ms=200, loop=True, width=None):
    paths = [Path(p) for p in paths]
    if len(paths) < 2:
        raise ValueError("An animation needs at least 2 images.")
    ext = "." + fmt.lstrip(".").lower()
    if ext not in ANIMATED_OUT:
        raise ValueError("Animations can be GIF, WebP or PNG.")
    if not 20 <= frame_ms <= 10000:
        raise ValueError("Frame time must be between 20 and 10000 ms.")

    first = load_frames(paths[0])[0][0]
    w0, h0 = first.size
    size = (width, max(1, round(h0 * width / w0))) if width else (w0, h0)

    frames = []
    for p in paths:
        frame = normalize(load_frames(p)[0][0]).convert("RGBA")
        fitted = ImageOps.contain(frame, size, RESAMPLE)
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        canvas.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
        frames.append(canvas)

    frames, opts = finalize(ext, frames)
    new_path = unique_path(_folder(output_folder) / (Path(output_name).stem + ext))
    save_frames(frames, [int(frame_ms)] * len(frames), 0 if loop else None, new_path, opts)
    return new_path


# ---------- preview ----------

def preview_image(path, box=(520, 140)):
    """(thumbnail image, one line of info) for the preview panel."""
    path = Path(path)
    with Image.open(path) as src:
        fmt = src.format or path.suffix[1:].upper()
        size = src.size
        animated = getattr(src, "is_animated", False)
        if fmt == "JPEG":
            src.draft("RGB", (box[0] * 2, box[1] * 2))
        frame = ImageOps.exif_transpose(src)
        frame.load()

    thumb = normalize(frame).convert("RGBA")
    thumb.thumbnail(box, RESAMPLE)
    info = f"{size[0]} x {size[1]} \u00b7 {fmt} \u00b7 {format_size(path.stat().st_size)}"
    if animated:
        info += " \u00b7 animated"
    return thumb, info

def crop_image(input_path, output_folder, left=None, top=None, right=None,
               bottom=None, square=False, keep_metadata=False):
    """Crop to a box. square=True cuts a centered square instead."""
    input_path = Path(input_path)
    ext = input_path.suffix.lower()
    frames, durations, loop = load_frames(input_path)
    w0, h0 = frames[0].size

    if square:
        side = min(w0, h0)
        left = (w0 - side) // 2
        top = (h0 - side) // 2
        right = left + side
        bottom = top + side
    else:
        if None in (left, top, right, bottom):
            raise ValueError("Give all four sides of the crop box.")
        left, top, right, bottom = int(left), int(top), int(right), int(bottom)
        left, top = max(0, left), max(0, top)
        right, bottom = min(w0, right), min(h0, bottom)
        if right - left < 1 or bottom - top < 1:
            raise ValueError("That crop box is outside the picture.")

    out = [normalize(f).crop((left, top, right, bottom)) for f in frames]
    exif = read_exif(input_path) if keep_metadata else None
    out, opts = finalize(ext, out, exif=exif)

    new_path = unique_path(_folder(output_folder) / input_path.name)
    save_frames(out, durations, loop, new_path, opts)
    return new_path
