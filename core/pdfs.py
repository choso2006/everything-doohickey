import io
import re
import shutil
import tempfile
from pathlib import Path

import pymupdf
from PIL import Image

from core.common import format_size, unique_path
from core.images import flatten_on_white, load_frames, normalize

PAGE_WIDTH = 595
PAGE_SIZES = {"a4": (595, 842), "letter": (612, 792)}

COMPRESS_LEVELS = {
    "light": None,
    "medium": (200, 150, 75),
    "strong": (150, 100, 60),
    "extreme": (110, 72, 40),
}

REDACT_PRESETS = {
    "emails": r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
    "links": r"(?:https?://|www\.)[^\s<>\"']+",
    "phones": r"\+?\d[\d\s().\-]{7,}\d",
    "long numbers": r"\b\d{8,}\b",
}


def _folder(output_folder):
    folder = Path(output_folder)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def open_pdf(path, password=None):
    """Open a PDF, with a clear message if it's locked."""
    doc = pymupdf.open(path)
    if doc.needs_pass:
        if not password or not doc.authenticate(password):
            doc.close()
            raise ValueError(f"{Path(path).name} is password protected. Unlock it first.")
    return doc


# ---------- page ranges ----------

def parse_pages(text, total):
    pages = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "-" in part:
                start, end = (int(x) for x in part.split("-"))
            else:
                start = end = int(part)
        except ValueError:
            raise ValueError(f"bad page range: '{part}'. Use numbers like 1-3,5")
        if start < 1 or end > total or start > end:
            raise ValueError(f"bad page range: {part} (PDF has {total} pages)")
        pages.extend(range(start - 1, end))
    return pages


def select_pages(pages_text, total):
    if pages_text.strip().lower() == "all":
        return list(range(total))
    return parse_pages(pages_text, total)


# ---------- building and rearranging ----------

def merge_pdfs(pdf_paths, output_folder, output_name="merged.pdf"):
    if not pdf_paths:
        raise ValueError("no PDFs given")

    merged = pymupdf.open()
    try:
        for path in pdf_paths:
            with open_pdf(path) as source:
                merged.insert_pdf(source)
        new_path = unique_path(_folder(output_folder) / output_name)
        merged.save(new_path, garbage=3, deflate=True)
    finally:
        merged.close()
    return new_path


def images_to_pdf(image_paths, output_folder, output_name="images.pdf",
                  page_mode="auto", quality=90):
    """page_mode: 'auto', 'stitch', 'a4' or 'letter'."""
    if not image_paths:
        raise ValueError("no images given")
    if page_mode not in ("auto", "stitch", *PAGE_SIZES):
        raise ValueError("unknown page size")

    doc = pymupdf.open()
    try:
        if page_mode == "stitch":
            # Vertical stitching (Scan mode)
            images = []
            for path in image_paths:
                frames, _, _ = load_frames(path)
                im = flatten_on_white(normalize(frames[0]))
                images.append(im)
            
            max_width = max(im.width for im in images)
            total_height = sum(im.height for im in images)
            
            # PDF maximum height is 14400 points. Cap it just in case.
            if total_height > 14000:
                total_height = 14000
            
            stitched = Image.new("RGB", (max_width, total_height), "white")
            y_offset = 0
            for im in images:
                stitched.paste(im, (0, y_offset))
                y_offset += im.height
                
            buffer = io.BytesIO()
            stitched.save(buffer, format="JPEG", quality=quality)
            
            # Convert pixels to PDF points (0.75 points per pixel)
            width_pts = max_width * 0.75
            height_pts = total_height * 0.75
            
            page = doc.new_page(width=width_pts, height=height_pts)
            page.insert_image(page.rect, stream=buffer.getvalue())
            
        else:
            # Standard page-by-page
            for path in image_paths:
                frames, _, _ = load_frames(path)
                im = flatten_on_white(normalize(frames[0]))

                buffer = io.BytesIO()
                im.save(buffer, format="JPEG", quality=quality)

                if page_mode == "auto":
                    height = round(PAGE_WIDTH * im.height / im.width)
                    page = doc.new_page(width=PAGE_WIDTH, height=max(height, 20))
                    rect = page.rect
                else:
                    width, height = PAGE_SIZES[page_mode]
                    if im.width > im.height:
                        width, height = height, width
                    page = doc.new_page(width=width, height=height)
                    rect = pymupdf.Rect(24, 24, width - 24, height - 24)
                page.insert_image(rect, stream=buffer.getvalue(), keep_proportion=True)

        new_path = unique_path(_folder(output_folder) / output_name)
        doc.save(new_path, garbage=3, deflate=True)
    finally:
        doc.close()
    return new_path


def extract_pages(pdf_path, output_folder, pages_text):
    pdf_path = Path(pdf_path)
    with open_pdf(pdf_path) as doc:
        pages = select_pages(pages_text, len(doc))
        if not pages:
            raise ValueError("no pages selected")
        doc.select(pages)
        new_path = unique_path(_folder(output_folder) / f"{pdf_path.stem}_extracted.pdf")
        doc.save(new_path, garbage=3, deflate=True)
    return new_path


def reorder_pages(pdf_path, output_folder, pages_text):
    """Keep exactly these pages, in exactly this order."""
    pdf_path = Path(pdf_path)
    with open_pdf(pdf_path) as doc:
        order = parse_pages(pages_text, len(doc))
        if not order:
            raise ValueError("no pages selected")
        doc.select(order)
        new_path = unique_path(_folder(output_folder) / f"{pdf_path.stem}_reordered.pdf")
        doc.save(new_path, garbage=3, deflate=True)
    return new_path


def split_pdf(pdf_path, output_folder, every=1):
    """One PDF per page, or per block of `every` pages."""
    every = max(1, int(every))
    pdf_path = Path(pdf_path)
    folder = _folder(output_folder)

    made = []
    with open_pdf(pdf_path) as doc:
        total = len(doc)
        for first in range(0, total, every):
            last = min(first + every, total) - 1
            piece = pymupdf.open()
            piece.insert_pdf(doc, from_page=first, to_page=last)
            if first == last:
                label = f"page{first + 1:02d}"
            else:
                label = f"pages{first + 1:02d}-{last + 1:02d}"
            new_path = unique_path(folder / f"{pdf_path.stem}_{label}.pdf")
            piece.save(new_path, garbage=3, deflate=True)
            piece.close()
            made.append(new_path)
    return made


def delete_pages(pdf_path, output_folder, pages_text):
    pdf_path = Path(pdf_path)
    with open_pdf(pdf_path) as doc:
        to_delete = sorted(set(select_pages(pages_text, len(doc))))
        if len(to_delete) >= len(doc):
            raise ValueError("that would delete every page")
        doc.delete_pages(to_delete)
        new_path = unique_path(_folder(output_folder) / f"{pdf_path.stem}_trimmed.pdf")
        doc.save(new_path, garbage=4, deflate=True)
    return new_path


def rotate_pages(pdf_path, output_folder, pages_text, degrees):
    if degrees % 90 != 0:
        raise ValueError("degrees must be a multiple of 90")

    pdf_path = Path(pdf_path)
    with open_pdf(pdf_path) as doc:
        for index in sorted(set(select_pages(pages_text, len(doc)))):
            page = doc[index]
            page.set_rotation((page.rotation + degrees) % 360)
        new_path = unique_path(_folder(output_folder) / f"{pdf_path.stem}_rotated.pdf")
        doc.save(new_path)
    return new_path


# ---------- size ----------

def _save_compressed(doc, level, path):
    settings = COMPRESS_LEVELS[level]
    if settings:
        doc.rewrite_images(
            dpi_threshold=settings[0], dpi_target=settings[1], quality=settings[2]
        )
    doc.save(path, garbage=4, deflate=True, clean=True)


def compress_pdf(pdf_path, output_folder, level="light"):
    if level not in COMPRESS_LEVELS:
        raise ValueError("unknown compression level")
    pdf_path = Path(pdf_path)
    new_path = unique_path(_folder(output_folder) / f"{pdf_path.stem}_compressed.pdf")

    with open_pdf(pdf_path) as doc:
        _save_compressed(doc, level, new_path)

    if new_path.stat().st_size >= pdf_path.stat().st_size:
        shutil.copyfile(pdf_path, new_path)
    return new_path


def compress_pdf_to_size(pdf_path, output_folder, target_mb):
    """Try gentler compression first, getting stronger until it fits."""
    pdf_path = Path(pdf_path)
    target = int(float(target_mb) * 1024 * 1024)
    new_path = unique_path(_folder(output_folder) / f"{pdf_path.stem}_compressed.pdf")

    if pdf_path.stat().st_size <= target:
        shutil.copyfile(pdf_path, new_path)
        return new_path

    work = Path(tempfile.mkdtemp(prefix="convertor_"))
    best = None
    try:
        for level in COMPRESS_LEVELS:
            candidate = work / f"{level}.pdf"
            with open_pdf(pdf_path) as doc:
                _save_compressed(doc, level, candidate)
            size = candidate.stat().st_size
            if best is None or size < best[1]:
                best = (candidate, size)
            if size <= target:
                break

        if best[1] >= pdf_path.stat().st_size:
            shutil.copyfile(pdf_path, new_path)
        else:
            shutil.copyfile(best[0], new_path)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    if best[1] > target:
        raise ValueError(
            f"Smallest I could make it was {format_size(best[1])} "
            f"(target {target_mb:g} MB). Saved that version anyway."
        )
    return new_path


# ---------- privacy ----------

def redact_text(pdf_path, output_folder, words=(), presets=()):
    """Black out text for good. Returns (new_path, number_of_matches)."""
    words = [w for w in words if w.strip()]
    if not words and not presets:
        raise ValueError("no words given")
    for name in presets:
        if name not in REDACT_PRESETS:
            raise ValueError(f"unknown preset: {name}")

    pdf_path = Path(pdf_path)
    total = 0
    with open_pdf(pdf_path) as doc:
        for page in doc:
            found = set()
            if presets:
                text = page.get_text()
                for name in presets:
                    for match in re.finditer(REDACT_PRESETS[name], text):
                        found.add(match.group(0).strip())
            for word in words + sorted(found):
                for rect in page.search_for(word):
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    total += 1
            page.apply_redactions()

        if total == 0:
            raise ValueError("none of those words were found")

        doc.scrub(hidden_text=False)
        new_path = unique_path(_folder(output_folder) / f"{pdf_path.stem}_redacted.pdf")
        doc.save(new_path, garbage=4, deflate=True)
    return new_path, total


def strip_pdf_metadata(pdf_path, output_folder):
    pdf_path = Path(pdf_path)
    with open_pdf(pdf_path) as doc:
        doc.set_metadata({})
        doc.del_xml_metadata()
        new_path = unique_path(_folder(output_folder) / f"{pdf_path.stem}_clean.pdf")
        doc.save(new_path, garbage=4, deflate=True)
    return new_path


def lock_pdf(pdf_path, output_folder, password):
    if not password:
        raise ValueError("password can't be empty")

    pdf_path = Path(pdf_path)
    with open_pdf(pdf_path) as doc:
        new_path = unique_path(_folder(output_folder) / f"{pdf_path.stem}_locked.pdf")
        doc.save(
            new_path,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            user_pw=password,
            owner_pw=password,
        )
    return new_path


def unlock_pdf(pdf_path, output_folder, password):
    pdf_path = Path(pdf_path)
    doc = pymupdf.open(pdf_path)
    try:
        if not doc.needs_pass:
            raise ValueError("this PDF isn't locked")
        if not doc.authenticate(password):
            raise ValueError("wrong password")
        new_path = unique_path(_folder(output_folder) / f"{pdf_path.stem}_unlocked.pdf")
        doc.save(new_path, encryption=pymupdf.PDF_ENCRYPT_NONE)
    finally:
        doc.close()
    return new_path


# ---------- stamping ----------

def _stamp_point(page, x, y):
    return pymupdf.Point(x, y) * page.derotation_matrix


def watermark_pdf(pdf_path, output_folder, text, size=60, opacity=25, angle=45):
    text = str(text).strip()
    if not text:
        raise ValueError("Type the watermark text.")

    pdf_path = Path(pdf_path)
    with open_pdf(pdf_path) as doc:
        for page in doc:
            length = pymupdf.get_text_length(text, fontname="helv", fontsize=size)
            width, height = page.rect.width, page.rect.height
            centre = _stamp_point(page, width / 2, height / 2)
            start = _stamp_point(page, width / 2 - length / 2, height / 2 + size / 3)
            turn = pymupdf.Matrix(angle)
            page.insert_text(
                start, text, fontsize=size, fontname="helv",
                color=(0.45, 0.45, 0.45), fill_opacity=opacity / 100,
                rotate=page.rotation, morph=(centre, turn), overlay=True,
            )
        new_path = unique_path(_folder(output_folder) / f"{pdf_path.stem}_watermarked.pdf")
        doc.save(new_path, garbage=3, deflate=True)
    return new_path


NUMBER_POSITIONS = ["Bottom center", "Bottom right", "Bottom left",
                    "Top center", "Top right", "Top left"]


def add_page_numbers(pdf_path, output_folder, position="Bottom center", start=1,
                     style="Page {n} of {total}"):
    if position not in NUMBER_POSITIONS:
        raise ValueError("unknown position")
    if "{n}" not in style:
        raise ValueError("The number format needs {n} in it.")

    pdf_path = Path(pdf_path)
    with open_pdf(pdf_path) as doc:
        total = len(doc)
        for index, page in enumerate(doc):
            label = style.replace("{n}", str(index + int(start))).replace(
                "{total}", str(total + int(start) - 1))
            size = 10
            length = pymupdf.get_text_length(label, fontname="helv", fontsize=size)
            width, height = page.rect.width, page.rect.height
            margin = 28
            x = {"left": margin, "center": (width - length) / 2,
                 "right": width - length - margin}[position.split()[1]]
            y = height - margin + size if position.startswith("Bottom") else margin
            page.insert_text(
                _stamp_point(page, x, y), label, fontsize=size, fontname="helv",
                color=(0.25, 0.25, 0.25), rotate=page.rotation, overlay=True,
            )
        new_path = unique_path(_folder(output_folder) / f"{pdf_path.stem}_numbered.pdf")
        doc.save(new_path, garbage=3, deflate=True)
    return new_path


# ---------- taking things out ----------

def pdf_to_images(pdf_path, output_folder, fmt=".png", dpi=150):
    if fmt not in (".png", ".jpg", ".jpeg"):
        raise ValueError("fmt must be .png or .jpg")

    pdf_path = Path(pdf_path)
    folder = _folder(output_folder)
    made = []
    with open_pdf(pdf_path) as doc:
        for index, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            new_path = unique_path(folder / f"{pdf_path.stem}_page{index + 1:02d}{fmt}")
            pix.save(new_path)
            made.append(new_path)
    return made


def pdf_to_text(pdf_path, output_folder, page_markers=True):
    pdf_path = Path(pdf_path)
    parts = []
    with open_pdf(pdf_path) as doc:
        for index, page in enumerate(doc):
            text = page.get_text().strip()
            parts.append(f"--- Page {index + 1} ---\n{text}" if page_markers else text)

    if not any(p.split("\n", 1)[-1].strip() for p in parts):
        raise ValueError("No text found. This looks like a scanned PDF (just pictures).")

    new_path = unique_path(_folder(output_folder) / f"{pdf_path.stem}.txt")
    new_path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return new_path


def ocr_pdf(pdf_path, output_folder, page_markers=True, dpi=200, languages="eng"):
    """OCR a scanned PDF into a .txt file. Needs Tesseract + pytesseract."""
    from core.tools import find_tool
    tesseract = find_tool("tesseract")
    if tesseract is None:
        raise ValueError(
            "Tesseract OCR isn't installed. Install it from "
            "github.com/UB-Mannheim/tesseract, then fully close and reopen the app."
        )
    try:
        import pytesseract
    except ImportError:
        raise ValueError("Install pytesseract to use OCR: pip install pytesseract")
    pytesseract.pytesseract.tesseract_cmd = tesseract

    pdf_path = Path(pdf_path)
    parts = []
    with open_pdf(pdf_path) as doc:
        for index, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            text = pytesseract.image_to_string(img, lang=languages).strip()
            if page_markers:
                parts.append(f"--- Page {index + 1} ---\n{text}")
            else:
                parts.append(text)

    new_path = unique_path(_folder(output_folder) / f"{pdf_path.stem}_ocr.txt")
    new_path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return new_path


def extract_pdf_images(pdf_path, output_folder, min_size=24):
    pdf_path = Path(pdf_path)
    folder = _folder(output_folder)
    made, seen = [], set()

    with open_pdf(pdf_path) as doc:
        for page_number, page in enumerate(doc, start=1):
            for position, image in enumerate(page.get_images(full=True), start=1):
                xref = image[0]
                if xref in seen:
                    continue
                seen.add(xref)
                try:
                    data = doc.extract_image(xref)
                except Exception:
                    continue
                if not data or min(data["width"], data["height"]) < min_size:
                    continue
                name = f"{pdf_path.stem}_p{page_number:03d}_{position}.{data['ext']}"
                new_path = unique_path(folder / name)
                new_path.write_bytes(data["image"])
                made.append(new_path)

    if not made:
        raise ValueError("No pictures found inside this PDF.")
    return made


# ---------- preview ----------

def render_pdf_page(path, index=0, width=380):
    """(PIL image of one page, total pages). Raises ValueError if locked."""
    with pymupdf.open(path) as doc:
        if doc.needs_pass:
            raise ValueError("locked")
        total = len(doc)
        page = doc[max(0, min(index, total - 1))]
        zoom = width / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples), total


def describe_pdf(path):
    path = Path(path)
    with pymupdf.open(path) as doc:
        if doc.needs_pass:
            return f"Password protected \u00b7 {format_size(path.stat().st_size)}"
        pages = len(doc)
    word = "page" if pages == 1 else "pages"
    return f"{pages} {word} \u00b7 {format_size(path.stat().st_size)}"