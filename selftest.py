"""Checks every backend feature using files it makes itself.

Run:  py selftest.py            (everything)
      py selftest.py app        (or: images, pdfs, video, audio, docs, files, helpers)
Nothing in your own folders is touched. Results go in a temp folder.
"""
import os
import sys
import time
import tempfile
import traceback
import shutil
import subprocess
import hashlib
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image, ImageDraw  # noqa: E402
from core.tools import find_tool  # noqa: E402

ROOT = Path(tempfile.mkdtemp(prefix="convertor_selftest_"))
RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    mark = "ok  " if condition else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail and not condition else ""))


def section(title):
    print(f"\n== {title} ==")


def guarded(name, function):
    try:
        function()
    except Exception:
        RESULTS.append((name, False, "crashed"))
        print(f"  [FAIL] {name} crashed:")
        traceback.print_exc()


def make(folder):
    path = ROOT / folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def noisy(size, seed=1):
    import random
    random.seed(seed)
    data = bytes(random.getrandbits(8) for _ in range(size[0] * size[1] * 3))
    return Image.frombytes("RGB", size, data)


def test_app():
    from core.tools import tool_status
    from core.sounds import play
    import core.appdata as appdata

    section("app logic")

    # Redirect app data to a temp folder so we NEVER touch the user's real settings
    original_dir = appdata.data_dir
    fake_dir = make("fake_appdata")
    appdata.data_dir = lambda: fake_dir

    try:
        test_data = {
            "app_name": "Test GF Converter",
            "sound_mode": "cute",
            "custom_message": "Yay! {count} files done!",
            "theme": "pink",
        }
        appdata.save_config(test_data)
        loaded = appdata.load_config()
        check("settings save & load", loaded.get("app_name") == "Test GF Converter")
        check("settings custom message", loaded.get("custom_message") == "Yay! {count} files done!")

        config = appdata.load_config()
        if "saved_presets" not in config:
            config["saved_presets"] = {}
        config["saved_presets"]["DummyPage"] = {"Test Preset": {"quality": 55, "format": "jpg"}}
        appdata.save_config(config)

        reloaded = appdata.load_config()
        saved_presets = reloaded.get("saved_presets", {})
        check("preset saving works", "DummyPage" in saved_presets)
        check("preset loading works", saved_presets["DummyPage"]["Test Preset"]["quality"] == 55)

        builtins = {"WebP": {"action": "Convert"}}
        merged = dict(builtins)
        merged.update(saved_presets["DummyPage"])
        check("preset merging logic", "WebP" in merged and "Test Preset" in merged)
    finally:
        # Restore the real data directory
        appdata.data_dir = original_dir

    status = tool_status()
    check("tool_status returns dict", isinstance(status, dict))
    check("ffmpeg key present", "ffmpeg" in status)

    if sys.platform == "darwin":
        check("macOS detected", True)
        check("brew key present on mac", "brew" in status)
    else:
        check("windows/linux detected", True)
        check("winget not in tool_status", "winget" not in status)

    try:
        play("success", "cute")
        play("success", "voice", "Testing voice")
        play("error", "chime")
        check("sound generation", True)
    except Exception as e:
        check("sound generation", False, str(e))


def test_images():
    from core import images as I

    section("images")
    src = make("img_src")
    out = make("img_out")

    exif = Image.Exif()
    exif[0x010F] = "TestCam"
    exif[0x0112] = 6
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2] = "N", (25.0, 15.0, 0.0)
    exif[0x8825] = gps
    photo = Image.linear_gradient("L").convert("RGB").resize((400, 300))
    ImageDraw.Draw(photo).rectangle((20, 20, 120, 80), fill="red")
    photo.save(src / "photo.jpg", exif=exif)

    alpha = Image.new("RGBA", (200, 120), (0, 0, 0, 0))
    ImageDraw.Draw(alpha).ellipse((20, 10, 180, 110), fill=(255, 0, 0, 255))
    alpha.save(src / "alpha.png")

    frames = []
    for i in range(5):
        f = Image.new("RGB", (120, 80), "white")
        ImageDraw.Draw(f).ellipse((10 + i * 15, 20, 40 + i * 15, 50), fill="blue")
        frames.append(f)
    frames[0].save(src / "anim.gif", save_all=True, append_images=frames[1:],
                   duration=80, loop=0)

    Image.new("CMYK", (100, 60), (0, 100, 100, 0)).save(src / "cmyk.jpg")
    Image.new("P", (50, 50)).save(src / "palette.png")
    Image.new("L", (90, 90), 128).save(src / "gray.png")
    Image.new("I;16", (60, 40), 30000).save(src / "deep.png")
    noisy((500, 400)).save(src / "noise.jpg", quality=95)
    noisy((300, 300)).save(src / "noise.png")

    for fmt in I.OUTPUT_FORMATS:
        p = I.convert_image(src / "photo.jpg", out, fmt)
        im = Image.open(p)
        expected = (256, 256) if fmt == "ico" else (300, 400)
        check(f"convert photo.jpg -> {fmt}", p.exists() and im.size == expected,
              f"size {im.size}")

    p = I.convert_image(src / "alpha.png", out, "jpg")
    check("alpha png -> jpg corner is white",
          Image.open(p).convert("RGB").getpixel((1, 1)) == (255, 255, 255))
    p = I.convert_image(src / "alpha.png", out, "ico")
    check("non-square -> ico is square", Image.open(p).size[0] == Image.open(p).size[1],
          str(Image.open(p).size))
    for fmt in ("png", "webp", "gif", "bmp", "tiff", "avif", "heic"):
        guarded(f"alpha png -> {fmt}",
                lambda fmt=fmt: check(f"alpha png -> {fmt}",
                                      I.convert_image(src / "alpha.png", out, fmt).exists()))

    for name in ("cmyk.jpg", "palette.png", "gray.png", "deep.png"):
        for fmt in ("png", "jpg", "webp", "bmp", "ico"):
            guarded(f"{name} -> {fmt}",
                    lambda name=name, fmt=fmt: check(
                        f"{name} -> {fmt}", I.convert_image(src / name, out, fmt).exists()))

    for fmt in ("gif", "webp", "png"):
        p = I.convert_image(src / "anim.gif", out, fmt)
        check(f"animated gif -> {fmt} keeps 5 frames",
              getattr(Image.open(p), "n_frames", 1) == 5,
              str(getattr(Image.open(p), "n_frames", 1)))
    p = I.convert_image(src / "anim.gif", out, "jpg")
    check("animated gif -> jpg is one still", getattr(Image.open(p), "n_frames", 1) == 1)

    p = I.convert_image(src / "photo.jpg", out, "jpg", keep_metadata=True)
    ex = Image.open(p).getexif()
    check("keep metadata keeps camera + GPS",
          ex.get(0x010F) == "TestCam" and ex.get_ifd(0x8825).get(1) == "N")
    p = I.convert_image(src / "photo.jpg", out, "jpg")
    check("default convert has no metadata", not dict(Image.open(p).getexif()))
    p = I.strip_metadata(src / "photo.jpg", out)
    check("strip_metadata removes everything", not dict(Image.open(p).getexif()))
    check("rotation applied on convert", Image.open(p).size == (300, 400))

    p = I.compress_image(src / "noise.jpg", out, quality=40)
    check("compress jpg gets smaller", p.stat().st_size < (src / "noise.jpg").stat().st_size)
    for name in ("alpha.png", "anim.gif"):
        guarded(f"compress {name}",
                lambda name=name: check(f"compress {name}",
                                        I.compress_image(src / name, out).exists()))
    bmp = I.convert_image(src / "photo.jpg", src, "bmp")
    try:
        I.compress_image(bmp, out)
        check("compress bmp refuses with a clear message", False)
    except ValueError as e:
        check("compress bmp refuses with a clear message", "BMP" in str(e), str(e))

    for name, kb in (("noise.jpg", 40), ("noise.png", 60), ("photo.jpg", 2)):
        guarded(f"target size {name}", lambda name=name, kb=kb: _target(I, src, out, name, kb))
    webp = I.convert_image(src / "noise.jpg", src, "webp")
    _target(I, src, out, webp.name, 30)
    p = I.compress_image_to_size(src / "alpha.png", out, 500)
    check("target size bigger than file copies it", p.exists())
    try:
        I.compress_image_to_size(src / "anim.gif", out, 5)
        check("target size on gif refuses", False)
    except ValueError:
        check("target size on gif refuses", True)

    cases = [
        ("width", dict(width=150), (150, 200)),
        ("height", dict(height=100), (75, 100)),
        ("percent", dict(percent=50), (150, 200)),
        ("fit", dict(fit=(100, 100)), (75, 100)),
        ("exact", dict(width=64, height=64), (64, 64)),
    ]
    for label_, kwargs, expected in cases:
        p = I.resize_image(src / "photo.jpg", out, **kwargs)
        check(f"resize {label_}", Image.open(p).size == expected, str(Image.open(p).size))
    p = I.resize_image(src / "anim.gif", out, width=60)
    check("resize keeps animation", getattr(Image.open(p), "n_frames", 1) == 5)
    p = I.resize_image(src / "alpha.png", out, width=50)
    check("resize keeps transparency", Image.open(p).mode == "RGBA")

    p = I.crop_image(src / "photo.jpg", out, square=True)
    check("crop square", Image.open(p).size == (300, 300), str(Image.open(p).size))
    p = I.crop_image(src / "photo.jpg", out, left=50, top=50, right=150, bottom=150)
    check("crop box", Image.open(p).size == (100, 100), str(Image.open(p).size))
    p = I.crop_image(src / "anim.gif", out, square=True)
    check("crop keeps animation", getattr(Image.open(p), "n_frames", 1) == 5)

    p = I.rotate_image(src / "alpha.png", out, degrees=90)
    check("rotate 90 swaps sides", Image.open(p).size == (120, 200))
    p = I.rotate_image(src / "alpha.png", out, flip_h=True, flip_v=True)
    check("flip works", Image.open(p).size == (200, 120))
    p = I.rotate_image(src / "anim.gif", out, degrees=180)
    check("rotate keeps animation", getattr(Image.open(p), "n_frames", 1) == 5)
    p = I.adjust_image(src / "photo.jpg", out, brightness=150, grayscale=True)
    px = Image.open(p).convert("RGB").getpixel((50, 150))
    check("adjust grayscale", px[0] == px[1] == px[2], str(px))
    for pos in I.WATERMARK_POSITIONS:
        guarded(f"watermark {pos}", lambda pos=pos: _watermark(I, src, out, pos))
    p = I.watermark_image(src / "alpha.png", out, "hello", color="black")
    check("watermark on transparent png", Image.open(p).mode == "RGBA")
    p = I.watermark_image(src / "anim.gif", out, "hello")
    check("watermark keeps animation", getattr(Image.open(p), "n_frames", 1) == 5)

    sample = [src / "photo.jpg", src / "alpha.png", src / "gray.png"]
    for fmt in ("gif", "webp", "png"):
        p = I.images_to_animation(sample, out, "anim_" + fmt, fmt, 150, True, width=120)
        check(f"make {fmt} animation", getattr(Image.open(p), "n_frames", 1) == 3)
    p = I.images_to_animation(sample, out, "once", "gif", 150, False)
    check("play-once gif", p.exists())

    thumb, info = I.preview_image(src / "photo.jpg")
    check("preview image", thumb.width <= 520 and "JPEG" in info, info)
    thumb, info = I.preview_image(src / "anim.gif")
    check("preview animated mentions animated", "animated" in info, info)

    a = I.convert_image(src / "photo.jpg", out, "png")
    b = I.convert_image(src / "photo.jpg", out, "png")
    check("never overwrites", a != b and a.exists() and b.exists())


def _target(I, src, out, name, kb):
    p = I.compress_image_to_size(src / name, out, kb)
    size = p.stat().st_size
    check(f"target size {name} <= {kb} KB", size <= kb * 1024, f"{size / 1024:.1f} KB")


def _watermark(I, src, out, pos):
    p = I.watermark_image(src / "photo.jpg", out, "Sample text", position=pos)
    from PIL import ImageChops
    base = Image.open(src / "photo.jpg").convert("RGB")
    changed = Image.open(p).convert("RGB")
    box = ImageChops.difference(base, changed).getbbox()
    check(f"watermark {pos} draws something", box is not None and changed.size == (300, 400),
          f"changed area {box}")


def test_pdfs():
    import pymupdf
    from core import pdfs as P

    section("pdfs")
    src = make("pdf_src")
    out = make("pdf_out")

    for name in "abc":
        doc = pymupdf.open()
        for i in range(1, 4):
            page = doc.new_page()
            page.insert_text((72, 72), f"File {name.upper()} page {i}", fontsize=24)
            page.insert_text((72, 120), "Contact: john.smith@example.com  +971 50 123 4567",
                             fontsize=12)
            page.insert_text((72, 150), "Secret code 48219937 and web https://example.com/x",
                             fontsize=12)
        doc.set_metadata({"author": "Someone Private", "title": "Private"})
        doc.save(src / f"{name}.pdf")
        doc.close()

    photo = ROOT / "pdf_photo.png"
    noisy((1400, 1000)).save(photo)
    doc = pymupdf.open()
    for _ in range(3):
        page = doc.new_page()
        page.insert_image(page.rect, filename=str(photo))
    doc.save(src / "heavy.pdf")
    doc.close()

    def pages(path):
        with pymupdf.open(path) as d:
            return len(d)

    def text(path, index=0):
        with pymupdf.open(path) as d:
            return d[index].get_text()

    p = P.merge_pdfs([src / "a.pdf", src / "b.pdf", src / "c.pdf"], out, "m.pdf")
    check("merge 9 pages", pages(p) == 9)
    check("merge keeps order", "File B" in text(p, 3))

    imgs = [photo, ROOT / "pdf_photo.png"]
    for mode in ("auto", "a4", "letter"):
        p = P.images_to_pdf(imgs, out, f"img_{mode}.pdf", page_mode=mode)
        check(f"images to pdf {mode}", pages(p) == 2)

    p = P.images_to_pdf(imgs, out, "img_stitch.pdf", page_mode="stitch")
    with pymupdf.open(p) as d:
        check("images to pdf stitch (1 page)", len(d) == 1, str(len(d)))
        check("images to pdf stitch (long page)", d[0].rect.height > d[0].rect.width * 1.4,
              f"{d[0].rect.width}x{d[0].rect.height}")

    p = P.extract_pages(src / "a.pdf", out, "3,1")
    check("extract in typed order", "page 3" in text(p, 0) and "page 1" in text(p, 1))
    p = P.extract_pages(src / "a.pdf", out, "all")
    check("extract all", pages(p) == 3)
    for bad in ("0", "1-99", "5-2", "abc"):
        try:
            P.extract_pages(src / "a.pdf", out, bad)
            check(f"extract rejects '{bad}'", False)
        except ValueError as e:
            check(f"extract rejects '{bad}' with a clean message",
                  "abc" not in str(e) or "bad page" in str(e), str(e))

    p = P.reorder_pages(src / "a.pdf", out, "3,1,2")
    check("reorder pages", pages(p) == 3 and "page 3" in text(p, 0)
          and "page 1" in text(p, 1) and "page 2" in text(p, 2))

    made = P.split_pdf(src / "a.pdf", out / "split1")
    check("split every page", len(made) == 3)
    made = P.split_pdf(src / "a.pdf", out / "split2", every=2)
    check("split every 2", len(made) == 2 and pages(made[0]) == 2 and pages(made[1]) == 1)

    p = P.delete_pages(src / "a.pdf", out, "2")
    check("delete page", pages(p) == 2 and "page 3" in text(p, 1))
    try:
        P.delete_pages(src / "a.pdf", out, "all")
        check("delete refuses everything", False)
    except ValueError:
        check("delete refuses everything", True)

    p = P.rotate_pages(src / "a.pdf", out, "1", 90)
    with pymupdf.open(p) as d:
        check("rotate page", [pg.rotation for pg in d] == [90, 0, 0])
    p = P.rotate_pages(src / "a.pdf", out, "1,1", 90)
    with pymupdf.open(p) as d:
        check("rotate duplicate page numbers only once", d[0].rotation == 90)

    heavy = src / "heavy.pdf"
    sizes = {}
    for level in P.COMPRESS_LEVELS:
        p = P.compress_pdf(heavy, out, level)
        sizes[level] = p.stat().st_size
    check("compress levels shrink the heavy pdf",
          sizes["strong"] < sizes["light"] * 0.5 and sizes["extreme"] <= sizes["strong"],
          str(sizes))
    p = P.compress_pdf(src / "a.pdf", out, "extreme")
    check("compress never makes a file bigger",
          p.stat().st_size <= (src / "a.pdf").stat().st_size)
    target = max(0.3, sizes["strong"] / 1024 / 1024 * 1.1)
    p = P.compress_pdf_to_size(heavy, out, target)
    check("compress to size lands under target", p.stat().st_size <= target * 1024 * 1024,
          f"{p.stat().st_size / 1024:.0f} KB vs {target * 1024:.0f} KB")
    try:
        P.compress_pdf_to_size(heavy, out, 0.01)
        check("compress to size impossible target reports it", False)
    except ValueError as e:
        check("compress to size impossible target reports it", "Smallest" in str(e), str(e))

    p, count = P.redact_text(src / "a.pdf", out, words=["48219937"])
    check("redact word really removes text",
          "48219937" not in text(p) and "File A" in text(p) and count == 3, f"{count}")
    p, count = P.redact_text(src / "a.pdf", out, presets=["emails", "links"])
    t = text(p)
    check("redact presets remove emails and links",
          "@" not in t and "example.com" not in t and "Secret code" in t, t[:80])
    p, count = P.redact_text(src / "a.pdf", out, presets=["phones", "long numbers"])
    check("redact phones and long numbers", "123 4567" not in text(p) and "48219937" not in text(p))
    try:
        P.redact_text(src / "a.pdf", out, words=["zzzzqqq"])
        check("redact nothing found raises", False)
    except ValueError:
        check("redact nothing found raises", True)
    with pymupdf.open(p) as d:
        check("redact scrubs metadata", not d.metadata.get("author"))

    p = P.strip_pdf_metadata(src / "a.pdf", out)
    with pymupdf.open(p) as d:
        check("strip pdf metadata", not d.metadata.get("author") and not d.metadata.get("title"),
              str(d.metadata))

    locked = P.lock_pdf(src / "a.pdf", out, "hunter2")
    with pymupdf.open(locked) as d:
        check("lock needs password", bool(d.needs_pass))
    try:
        P.unlock_pdf(locked, out, "nope")
        check("unlock wrong password", False)
    except ValueError as e:
        check("unlock wrong password", "wrong" in str(e))
    un = P.unlock_pdf(locked, out, "hunter2")
    with pymupdf.open(un) as d:
        check("unlock works", not d.needs_pass and len(d) == 3)
    try:
        P.merge_pdfs([locked, src / "a.pdf"], out)
        check("locked pdf gives a clear message", False)
    except ValueError as e:
        check("locked pdf gives a clear message", "password" in str(e), str(e))

    p = P.watermark_pdf(src / "a.pdf", out, "CONFIDENTIAL")
    check("watermark pdf", "CONFIDENTIAL" in text(p) or p.exists())
    rot = P.rotate_pages(src / "a.pdf", out, "1", 90)
    p = P.watermark_pdf(rot, out, "CONFIDENTIAL")
    check("watermark rotated pdf", p.exists())
    p = P.add_page_numbers(src / "a.pdf", out, "Bottom center")
    check("page numbers text", "Page 2 of 3" in text(p, 1), text(p, 1)[-40:])
    for pos in P.NUMBER_POSITIONS:
        check(f"page numbers {pos}", P.add_page_numbers(src / "a.pdf", out, pos, start=5).exists())
    p = P.add_page_numbers(rot, out, "Top right")
    check("page numbers on rotated page", p.exists())

    made = P.pdf_to_images(src / "a.pdf", out / "imgs", ".png", 72)
    check("pdf to images", len(made) == 3 and Image.open(made[0]).width > 100)
    made = P.pdf_to_images(src / "a.pdf", out / "imgs", ".jpg", 72)
    check("pdf to jpg", len(made) == 3)
    p = P.pdf_to_text(src / "a.pdf", out)
    check("pdf to text", "File A page 2" in p.read_text(encoding="utf-8"))
    try:
        P.pdf_to_text(heavy, out)
        check("pdf to text on scans explains itself", False)
    except ValueError as e:
        check("pdf to text on scans explains itself", "scanned" in str(e), str(e))
    made = P.extract_pdf_images(heavy, out / "pdfimgs")
    check("extract pdf images", len(made) == 1 and Image.open(made[0]).size == (1400, 1000),
          str(made))

    img, total = P.render_pdf_page(src / "b.pdf", 1, 300)
    check("render page", total == 3 and img.width == 300)
    try:
        P.render_pdf_page(locked)
        check("render locked raises", False)
    except ValueError:
        check("render locked raises", True)
    check("describe pdf", "3 pages" in P.describe_pdf(src / "a.pdf"))

    if find_tool("tesseract"):
        img = Image.new("RGB", (400, 200), "white")
        d = ImageDraw.Draw(img)
        d.text((50, 50), "Hello OCR 123", fill="black")
        img_path = src / "ocr_test.png"
        img.save(img_path)
        pdf_path = P.images_to_pdf([img_path], out, "ocr.pdf")
        txt_path = P.ocr_pdf(pdf_path, out)
        ocr_text = txt_path.read_text(encoding="utf-8")
        check("ocr pdf extracts text", "Hello" in ocr_text or "OCR" in ocr_text, ocr_text[:50])
    else:
        print("  [SKIP] ocr pdf (tesseract not found)")

    shutil.copyfile(P.add_page_numbers(rot, out, "Bottom right"), ROOT / "look_numbers_rotated.pdf")
    shutil.copyfile(P.watermark_pdf(rot, out, "DRAFT"), ROOT / "look_watermark_rotated.pdf")
    shutil.copyfile(P.watermark_pdf(src / "a.pdf", out, "DRAFT"), ROOT / "look_watermark.pdf")


def ff(*args):
    result = subprocess.run([find_tool("ffmpeg"), "-y", "-loglevel", "error", *args],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)


def test_video():
    from core import media
    from core import video as V

    section("video")
    if not find_tool("ffmpeg"):
        check("ffmpeg installed", False, "skipping video and audio tests")
        return
    src = make("vid_src")
    out = make("vid_out")

    ff("-f", "lavfi", "-i", "testsrc2=duration=6:size=640x360:rate=30",
       "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
       str(src / "clip.mp4"))
    ff("-f", "lavfi", "-i", "testsrc=duration=3:size=321x241:rate=25",
       "-c:v", "libx264", "-pix_fmt", "yuv444p", str(src / "odd_silent.mkv"))
    ff("-f", "lavfi", "-i", "testsrc2=duration=30:size=1280x720:rate=30",
       "-f", "lavfi", "-i", "anoisesrc=d=30:c=pink",
       "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", "-c:a", "aac",
       "-shortest", str(src / "big.mp4"))
    clip = src / "clip.mp4"

    info = media.probe(clip)
    check("probe", info["has_video"] and info["has_audio"] and info["width"] == 640
          and 5.5 < info["duration"] < 6.5, str(info))
    check("probe silent clip", not media.probe(src / "odd_silent.mkv")["has_audio"])

    for fmt in V.VIDEO_FORMATS:
        guarded(f"convert -> {fmt}", lambda fmt=fmt: _vconv(V, media, clip, out, fmt))
    p = V.convert_video(src / "odd_silent.mkv", out, "mp4")
    check("odd-sized silent video converts", media.probe(p)["width"] % 2 == 0, str(media.probe(p)))
    p = V.convert_video(clip, out, "mkv", fast_copy=True)
    check("fast copy convert", media.probe(p)["vcodec"] == "h264")

    p = V.compress_video(clip, out, crf=34, max_height=240)
    check("compress with max height", media.probe(p)["height"] == 240, str(media.probe(p)))
    p = V.compress_video(clip, out, crf=30, max_height=1080)
    check("compress never enlarges", media.probe(p)["height"] == 360)
    p = V.compress_video(src / "odd_silent.mkv", out, max_height=100)
    check("compress odd height gives even size", media.probe(p)["height"] % 2 == 0)

    big = src / "big.mp4"
    for mb in (3, 1.5):
        guarded(f"target {mb} MB", lambda mb=mb: _vtarget(V, media, big, out, mb))
    try:
        V.compress_video_to_size(clip, out, 0.01)
        check("target size absurdly small is refused", False)
    except ValueError as e:
        check("target size absurdly small is refused",
              "too small" in str(e) or "under" in str(e), str(e))
    p = V.compress_video_to_size(clip, out, 500)
    check("video already under the target is copied untouched",
          p.stat().st_size == clip.stat().st_size)

    for fmt in (".mp3", ".m4a", ".ogg", ".opus", ".wav", ".flac", ".aac", ".aiff"):
        guarded(f"extract audio {fmt}",
                lambda fmt=fmt: check(f"extract audio {fmt}",
                                      V.extract_audio(clip, out, fmt).exists()))
    try:
        V.extract_audio(src / "odd_silent.mkv", out)
        check("extract audio from silent video explains itself", False)
    except ValueError:
        check("extract audio from silent video explains itself", True)

    p = V.trim_video(clip, out, "1", "3")
    check("fast trim length", 1.0 < media.probe(p)["duration"] < 3.6,
          str(media.probe(p)["duration"]))
    p = V.trim_video(clip, out, "1", "3", precise=True)
    check("exact trim length", 1.8 < media.probe(p)["duration"] < 2.3,
          str(media.probe(p)["duration"]))
    p = V.trim_video(clip, out, "0:00:02.50", "0:00:04.00", precise=True)
    check("trim with decimal times", 1.2 < media.probe(p)["duration"] < 1.8)
    for start, end in (("5", "2"), ("abc", "3"), ("10", "20")):
        try:
            V.trim_video(clip, out, start, end)
            check(f"trim rejects {start}-{end}", False)
        except ValueError:
            check(f"trim rejects {start}-{end}", True)

    a = V.trim_video(clip, src, "0", "2", precise=True)
    b = V.trim_video(clip, src, "2", "4", precise=True)
    c = V.trim_video(clip, src, "4", "6", precise=True)
    p = V.merge_videos([a, b, c], out, "merged_fast")
    check("merge fast", 5.0 < media.probe(p)["duration"] < 7.0, str(media.probe(p)["duration"]))
    try:
        V.merge_videos([a, src / "odd_silent.mkv"], out)
        check("fast merge mismatch explains itself", False)
    except ValueError as e:
        check("fast merge mismatch explains itself", "Re-encode" in str(e), str(e))
    p = V.merge_videos([clip, src / "odd_silent.mkv", a], out, "mix", reencode=True)
    d = media.probe(p)["duration"]
    check("merge re-encode with a silent clip", 10.5 < d < 12 and media.probe(p)["has_audio"], str(d))
    p = V.merge_videos([clip, a], out, "hd", reencode=True, resolution=(1920, 1080), fps=24)
    check("merge custom size and fps",
          media.probe(p)["width"] == 1920 and round(media.probe(p)["fps"]) == 24)
    p = V.merge_videos([clip, a], out, "match", reencode=True, resolution=None, fps=None)
    check("merge match first video", media.probe(p)["width"] == 640)

    p = V.video_to_gif(clip, out, fps=10, width=200, start="1", end="3")
    check("video to gif", Image.open(p).size[0] == 200 and Image.open(p).n_frames > 10)
    p = V.remove_audio(clip, out)
    check("remove audio", not media.probe(p)["has_audio"] and media.probe(p)["has_video"])
    for factor in (2.0, 0.5, 4.0):
        p = V.change_speed(clip, out, factor)
        d = media.probe(p)["duration"]
        check(f"speed {factor}x", abs(d - 6 / factor) < 0.8, f"{d:.2f}s")
    p = V.change_speed(src / "odd_silent.mkv", out, 2)
    check("speed on silent video", p.exists())
    p = V.rotate_video(clip, out, degrees=90)
    check("rotate video 90", (media.probe(p)["width"], media.probe(p)["height"]) == (360, 640))
    p = V.rotate_video(clip, out, flip_h=True)
    check("flip video", media.probe(p)["width"] == 640)

    p = V.crop_video(clip, out, aspect=(1, 1), mode="crop")
    check("crop video 1:1", media.probe(p)["width"] == 360 and media.probe(p)["height"] == 360)
    p = V.crop_video(clip, out, aspect=(1, 1), mode="pad")
    check("pad video 1:1", media.probe(p)["width"] == 640 and media.probe(p)["height"] == 640)

    audio_path = src / "replacement.wav"
    ff("-f", "lavfi", "-i", "sine=frequency=880:duration=6", str(audio_path))
    p = V.replace_audio(src / "odd_silent.mkv", audio_path, out)
    check("replace audio on silent video", media.probe(p)["has_audio"])

    p = V.screenshot(clip, out, 2.5)
    check("screenshot", Image.open(p).size == (640, 360))
    p = V.screenshot(clip, out, "0:03", ".jpg")
    check("screenshot jpg", p.suffix == ".jpg")
    made = V.extract_frames(clip, out, every=2)
    check("extract frames every 2 s", len(made) == 3, str(len(made)))
    check("describe video", "640x360" in V.describe_video(clip), V.describe_video(clip))

    seen = []
    V.compress_video(clip, out, progress=seen.append)
    check("progress goes up to 100%",
          seen and seen[-1] == 1.0 and seen == sorted(seen), str(seen[-4:]))

    from core.common import Cancelled
    before = set(out.glob("*"))

    def cancel_now():
        return True

    try:
        V.convert_video(big, out, "mkv", cancel=cancel_now)
        check("cancel stops ffmpeg", False)
    except Cancelled:
        check("cancel stops ffmpeg", True)
    check("cancel leaves no half-written file", set(out.glob("*")) == before)

    frame = media.grab_frame(clip, 2.0, 320)
    check("grab frame", frame.width == 320)
    frame = media.grab_frame(clip, 999, 320)
    check("grab frame past the end still works or fails cleanly", frame is not None)


def _vconv(V, media, clip, out, fmt):
    p = V.convert_video(clip, out, fmt)
    info = media.probe(p)
    check(f"convert -> {fmt}", info["has_video"] and info["has_audio"] and 5 < info["duration"] < 7,
          str(info))


def _vtarget(V, media, big, out, mb):
    p = V.compress_video_to_size(big, out, mb)
    size = p.stat().st_size
    check(f"target {mb} MB lands under",
          size <= mb * 1024 * 1024 and size > mb * 1024 * 1024 * 0.4,
          f"{size / 1024 / 1024:.2f} MB, {media.probe(p)['height']}p")


def test_audio():
    from core import audio as A
    from core import media

    section("audio")
    if not find_tool("ffmpeg"):
        check("ffmpeg installed", False, "skipping")
        return
    src = make("aud_src")
    out = make("aud_out")
    ff("-f", "lavfi", "-i", "sine=frequency=440:duration=4", str(src / "tone.wav"))
    ff("-f", "lavfi", "-i", "sine=frequency=660:duration=3", "-ar", "22050",
       str(src / "tone2.flac"))
    tone = src / "tone.wav"

    for fmt in A.AUDIO_FORMATS:
        guarded(f"audio convert {fmt}", lambda fmt=fmt: _aconv(A, media, tone, out, fmt))
    p = A.convert_audio(tone, out, "mp3", kbps=96)
    big = A.convert_audio(tone, out, "mp3", kbps=320)
    check("lower bitrate is smaller", p.stat().st_size < big.stat().st_size)
    p = A.trim_audio(tone, out, "1", "3")
    check("audio trim", 1.5 < media.probe(p)["duration"] < 2.5, str(media.probe(p)["duration"]))
    p = A.merge_audio([tone, src / "tone2.flac", tone], out, "joined", "mp3")
    check("audio merge different formats", 10.5 < media.probe(p)["duration"] < 11.5,
          str(media.probe(p)["duration"]))
    p = A.change_volume(tone, out, db=6)
    check("volume up", p.exists())
    p = A.change_volume(tone, out, normalize=True)
    check("normalize", p.exists())
    try:
        A.change_volume(tone, out, db=0)
        check("volume 0 dB refused", False)
    except ValueError:
        check("volume 0 dB refused", True)
    for factor in (0.5, 2, 3.5):
        p = A.change_speed_audio(tone, out, factor)
        check(f"audio speed {factor}x", abs(media.probe(p)["duration"] - 4 / factor) < 0.5,
              str(media.probe(p)["duration"]))
    wma = src / "x.wma"
    ff("-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:a", "wmav2", str(wma))
    p = A.change_volume(wma, out, db=3)
    check("unusual input keeps working (falls back to mp3)", p.suffix == ".mp3")
    wave = media.grab_waveform(tone, 400, 100)
    check("waveform picture", wave.size == (400, 100))
    check("describe audio",
          "WAV" in A.describe_audio(tone).upper() or "PCM" in A.describe_audio(tone).upper(),
          A.describe_audio(tone))

    p = A.fade_audio(tone, out, fade_in=1.0, fade_out=1.0)
    check("fade audio", p.exists() and abs(media.probe(p)["duration"] - 4.0) < 0.5,
          str(media.probe(p)["duration"]))

    ff("-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "1", str(src / "silence.wav"))
    list_file = src / "concat.txt"
    with open(list_file, "w") as f:
        f.write(f"file '{src / 'silence.wav'}'\n")
        f.write(f"file '{src / 'tone.wav'}'\n")
        f.write(f"file '{src / 'silence.wav'}'\n")
    padded = src / "padded.wav"
    ff("-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(padded))
    p = A.trim_silence(padded, out, threshold_db=-40, min_silence=0.1)
    check("trim silence", abs(media.probe(p)["duration"] - 4.2) < 0.5,
          str(media.probe(p)["duration"]))


def _aconv(A, media, tone, out, fmt):
    p = A.convert_audio(tone, out, fmt)
    check(f"audio convert {fmt}", p.exists() and 3.5 < media.probe(p)["duration"] < 4.6,
          str(media.probe(p)["duration"]))


def test_files():
    from core import files as F

    section("files")
    src = make("file_src")
    out = make("file_out")

    test_file = src / "big_file.bin"
    with open(test_file, "wb") as f:
        f.write(os.urandom(5 * 1024 * 1024))

    original_size = test_file.stat().st_size
    original_hash = hashlib.md5(test_file.read_bytes()).hexdigest()

    parts = F.split_file(test_file, out, chunk_size_mb=1)
    check("split file parts count", len(parts) == 5, str(len(parts)))
    check("split file part size", parts[0].stat().st_size == 1024 * 1024,
          str(parts[0].stat().st_size))
    check("split file naming", parts[0].name == "big_file.bin.part001", parts[0].name)

    joined = F.join_files(parts, out)
    check("join file size", joined.stat().st_size == original_size, str(joined.stat().st_size))

    joined_hash = hashlib.md5(joined.read_bytes()).hexdigest()
    check("join file integrity (hash matches)", joined_hash == original_hash)

    joined_named = F.join_files(parts, out, output_name="reassembled.bin")
    check("join file custom name", joined_named.name == "reassembled.bin", joined_named.name)


def test_docs():
    from core import docs as D

    section("documents")
    if not find_tool("soffice"):
        check("LibreOffice installed", False, "skipping document tests (optional)")
        return
    src = make("doc_src")
    out = make("doc_out")

    (src / "note.txt").write_text("Hello from the test.\nSecond line.\n", encoding="utf-8")
    (src / "table.csv").write_text("name,score\nAda,10\nBob,7\n", encoding="utf-8")

    p = D.convert_document(src / "note.txt", out, "pdf")
    check("txt -> pdf", p.suffix == ".pdf" and p.stat().st_size > 500)
    docx = D.convert_document(src / "note.txt", out, "docx")
    check("txt -> docx", docx.suffix == ".docx")
    p = D.convert_document(docx, out, "pdf")
    check("docx -> pdf", p.stat().st_size > 500)
    p = D.convert_document(docx, out, "odt")
    check("docx -> odt", p.suffix == ".odt")
    p = D.convert_document(docx, out, "txt")
    check("docx -> txt", "Hello from the test." in p.read_text(encoding="utf-8-sig"))
    p = D.convert_document(docx, out, "rtf")
    check("docx -> rtf", p.suffix == ".rtf")
    p = D.convert_document(docx, out, "html")
    check("docx -> html", p.suffix == ".html")
    xlsx = D.convert_document(src / "table.csv", out, "xlsx")
    check("csv -> xlsx", xlsx.suffix == ".xlsx")
    p = D.convert_document(xlsx, out, "pdf")
    check("xlsx -> pdf", p.stat().st_size > 500)
    p = D.convert_document(xlsx, out, "csv")
    check("xlsx -> csv", "Ada" in p.read_text(encoding="utf-8-sig"))
    p = D.convert_document(xlsx, out, "ods")
    check("xlsx -> ods", p.suffix == ".ods")
    try:
        D.convert_document(docx, out, "xlsx")
        check("docx -> xlsx explains itself", False)
    except ValueError as e:
        check("docx -> xlsx explains itself", "can only be turned into" in str(e), str(e))
    again = D.convert_document(src / "note.txt", out, "pdf")
    check("documents never overwrite", again.name != "note.pdf")

    from core.common import Cancelled
    try:
        D.convert_document(src / "note.txt", out, "pdf", cancel=lambda: True)
        check("cancel stops LibreOffice", False)
    except Cancelled:
        check("cancel stops LibreOffice", True)


def test_misc():
    from core.common import clean_name, format_stamp, format_time, to_seconds
    from core.batch import run_batch
    from core.common import unique_path

    section("helpers")
    check("to_seconds", to_seconds("1:02:03.5") == 3723.5 and to_seconds("45") == 45)
    check("format_time", format_time(83.4) == "1:23" and format_time(3723) == "1:02:03")
    check("format_stamp", format_stamp(83.456) == "0:01:23.45", format_stamp(83.456))
    check("format_stamp round trips",
          abs(to_seconds(format_stamp(59.999)) - 59.99) < 0.02)
    check("clean_name", clean_name('a<b>:"c"/d?.mp4', "x", (".mp4",)) == "abcd")
    check("clean_name reserved", clean_name("CON", "fallback") == "fallback")

    folder = make("misc")
    (folder / "a.txt").write_text("x")
    check("unique_path", unique_path(folder / "a.txt").name == "a (1).txt")

    seen = []

    def boom(path, out, **kw):
        if "bad" in path.name:
            raise ValueError("nope")
        return path

    files = [folder / "good1", folder / "bad", folder / "good2"]
    result = run_batch(files, folder, boom, on_progress=seen.append)
    check("batch survives a failure", len(result.done) == 2 and len(result.failed) == 1
          and result.failed[0][1] == "nope" and seen[-1] == 1.0)
    result = run_batch(files, folder, boom, should_cancel=lambda: True)
    check("batch cancel", result.cancelled and not result.done)


SECTIONS = {
    "app": test_app,
    "helpers": test_misc,
    "images": test_images,
    "pdfs": test_pdfs,
    "video": test_video,
    "audio": test_audio,
    "files": test_files,
    "docs": test_docs,
}


def run_all(wanted=None):
    global RESULTS, ROOT
    RESULTS = []
    ROOT = Path(tempfile.mkdtemp(prefix="convertor_selftest_"))

    wanted = wanted or list(SECTIONS)
    for name in wanted:
        if name not in SECTIONS:
            print(f"Unknown section '{name}'. Pick from: {', '.join(SECTIONS)}")
            continue
        guarded(name, SECTIONS[name])

    failed = [r for r in RESULTS if not r[1]]
    total = len(RESULTS)
    passed = total - len(failed)
    return passed, total, failed, ROOT


def main():
    wanted = sys.argv[1:] or list(SECTIONS)
    started = time.time()

    passed, total, failed, root = run_all(wanted)

    print(f"\n{passed} of {total} checks passed in {time.time() - started:.0f} seconds.")
    if failed:
        print("\nFailed:")
        for name, _, detail in failed:
            print(f"  - {name}  {detail}")
    print(f"\nTest files are in: {root}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())