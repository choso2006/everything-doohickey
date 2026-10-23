from pathlib import Path

import customtkinter as ctk
import pymupdf
from PIL import Image as PILImage

from core.common import clean_name
from core.images import ALLOWED as IMAGE_EXTENSIONS
from core.pdfs import (
    NUMBER_POSITIONS, REDACT_PRESETS, add_page_numbers, compress_pdf,
    compress_pdf_to_size, delete_pages, extract_pages, extract_pdf_images,
    images_to_pdf, lock_pdf, merge_pdfs, ocr_pdf, pdf_to_images, pdf_to_text,
    redact_text, reorder_pages, rotate_pages, select_pages, split_pdf,
    strip_pdf_metadata, unlock_pdf, watermark_pdf,
)
from core.tools import find_tool
from ui import theme
from ui.toolpage import ToolPage
from ui.widgets import (
    checkbox, entry, label, note, option_menu, primary_button, read_float,
    read_int, secondary_button, setting_row, slider_row, small_button, textbox,
    SquaredScrollableFrame
)

ACTIONS = [
    "Merge", "Images to PDF", "Extract pages", "Reorder pages",
    "Split into pages", "Delete pages", "Rotate pages", "Compress",
    "Compress to size", "Redact text", "Watermark", "Page numbers",
    "Strip metadata", "Lock", "Unlock", "PDF to images", "PDF to text",
    "OCR scanned PDF", "Extract pictures",
]
ORDERED = ("Merge", "Images to PDF")
ROTATIONS = {
    "Clockwise 90": 90,
    "Upside down 180": 180,
    "Counter-clockwise 90": -90,
}
LEVELS = {
    "Light (no quality loss)": "light",
    "Medium": "medium",
    "Strong": "strong",
    "Extreme (smallest)": "extreme",
}
PAGE_SIZES = {
    "Fit to the picture": "auto",
    "Stitch into one long page": "stitch",
    "A4 pages": "a4",
    "Letter pages": "letter",
}
DPI_CHOICES = ["72", "100", "150", "200", "300"]
PRESET_LABELS = {
    "emails": "Email addresses",
    "links": "Web links",
    "phones": "Phone numbers",
    "long numbers": "Long numbers (8+ digits)",
}


def split_action(path, output_folder, every=1):
    target = Path(output_folder) / Path(path).stem
    return split_pdf(path, target, every=every)


def images_action(path, output_folder, fmt, dpi):
    target = Path(output_folder) / Path(path).stem
    return pdf_to_images(path, target, fmt=fmt, dpi=dpi)


def pictures_action(path, output_folder):
    target = Path(output_folder) / Path(path).stem
    return extract_pdf_images(path, target)


class PdfsPage(ToolPage):
    ACTIONS = ACTIONS

    def __init__(self, parent, state=None):
        super().__init__(
            parent, "PDFs",
            "Merge, split, redact, compress, protect and take PDFs apart.", state,
        )
        R = self.remember
        self.merge_name = R("merge_name", ctk.StringVar(value="merged"))
        self.images_name = R("images_name", ctk.StringVar(value="images"))
        self.page_size = R("page_size", ctk.StringVar(value="Fit to the picture"))
        self.pages_var = R("pages", ctk.StringVar(value="1"))
        self.every_var = R("every", ctk.StringVar(value="1"))
        self.rotation_var = R("rotation", ctk.StringVar(value="Clockwise 90"))
        self.level_var = R("level", ctk.StringVar(value="Strong"))
        self.target_mb = R("target_mb", ctk.StringVar(value="5"))
        self.mark_text = R("mark_text", ctk.StringVar(value="CONFIDENTIAL"))
        self.mark_size = R("mark_size", ctk.DoubleVar(value=60))
        self.mark_opacity = R("mark_opacity", ctk.DoubleVar(value=25))
        self.number_pos = R("number_pos", ctk.StringVar(value="Bottom center"))
        self.number_start = R("number_start", ctk.StringVar(value="1"))
        self.number_style = R("number_style", ctk.StringVar(value="Page {n} of {total}"))
        self.format_var = R("format", ctk.StringVar(value="png"))
        self.dpi_var = R("dpi", ctk.StringVar(value="150"))
        self.markers_var = R("markers", ctk.BooleanVar(value=True))
        self.preset_vars = {
            key: R(f"redact_{key}", ctk.BooleanVar(value=False))
            for key in REDACT_PRESETS
        }

        self.password_var = ctk.StringVar()
        self.confirm_var = ctk.StringVar()

        self.redact_box = None
        self.redact_words = self.state.get("redact_words", "")
        self.redaction_count = 0

        self.build()
        try:
            self.preview.on_open_pages = self.show_page_picker
        except AttributeError:
            pass

    def current_extensions(self):
        if self.action_var.get() == "Images to PDF":
            return IMAGE_EXTENSIONS
        return (".pdf",)

    def is_ordered(self):
        return self.action_var.get() in ORDERED

    def read_redact_words(self):
        box = self.redact_box
        if box is not None and box.winfo_exists():
            self.redact_words = box.get("1.0", "end").strip("\n")
        return self.redact_words

    def get_state(self):
        saved = super().get_state()
        saved["redact_words"] = self.read_redact_words()
        return saved

    def show_page_picker(self):
        pdf = None
        if self.selected and self.selected.suffix.lower() == ".pdf":
            pdf = self.selected
        elif self.files:
            for f in self.files:
                if f.suffix.lower() == ".pdf":
                    pdf = f
                    break
        if pdf is None:
            self.set_status("Add a PDF first.", error=True)
            return
        try:
            PagePicker(
                self.winfo_toplevel(), pdf, self.pages_var.get(),
                on_apply=lambda text: self.pages_var.set(text),
            )
        except Exception as e:
            self.set_status(str(e), error=True)

    def build_settings(self):
        self.read_redact_words()
        self.redact_box = None
        for child in self.settings.winfo_children():
            child.destroy()

        action = self.action_var.get()
        box = self.settings

        def pages_row():
            row = setting_row(box, "Pages")
            entry(row, self.pages_var).pack(side="left", fill="x", expand=True)
            secondary_button(row, "Pick", self.show_page_picker, width=60).pack(
                side="left", padx=(6, 0)
            )

        def password_row(text, variable):
            row = setting_row(box, text)
            entry(row, variable, show="*").pack(side="left", fill="x", expand=True)

        if action == "Merge":
            row = setting_row(box, "Name")
            entry(row, self.merge_name).pack(side="left", fill="x", expand=True)
            note(box, "Joins the PDFs in the order shown on the left. Use the "
                      "arrow buttons to change the order. Locked PDFs need "
                      "unlocking first.")

        elif action == "Images to PDF":
            row = setting_row(box, "Name")
            entry(row, self.images_name).pack(side="left", fill="x", expand=True)
            row = setting_row(box, "Pages")
            option_menu(row, list(PAGE_SIZES), self.page_size).pack(
                side="left", fill="x", expand=True
            )
            note(box, "One page per picture, in the order shown. 'Fit to the "
                      "picture' makes each page as tall as its picture needs, "
                      "so nothing is stretched. A4 and Letter pages center "
                      "each picture on a standard page. Animated pictures use "
                      "their first frame.")

        elif action == "Extract pages":
            pages_row()
            note(box, "Examples: 1-3,5,8-10. The order you type is the order "
                      "you get. Press Pick to choose from thumbnails. "
                      "The same pages are used for every PDF in the list.")

        elif action == "Reorder pages":
            pages_row()
            note(box, "Keep only these pages, in exactly this order. "
                      "Press Pick to choose from thumbnails. "
                      "The same order is used for every PDF in the list.")

        elif action == "Split into pages":
            row = setting_row(box, "Every")
            entry(row, self.every_var, width=80).pack(side="left")
            ctk.CTkLabel(row, text="page(s)", text_color=theme.MUTED,
                         font=theme.font(13)).pack(side="left", padx=6)
            note(box, "1 makes one PDF per page. 5 makes a new PDF for every "
                      "5 pages. Each PDF gets its own subfolder named after "
                      "the original.")

        elif action == "Delete pages":
            pages_row()
            note(box, "Examples: 2 or 1-3,7. Deleting every page isn't "
                      "allowed. The same pages are used for every PDF in the "
                      "list.")

        elif action == "Rotate pages":
            pages_row()
            row = setting_row(box, "Turn")
            option_menu(row, list(ROTATIONS), self.rotation_var).pack(
                side="left", fill="x", expand=True
            )
            note(box, "Type all to turn every page. Rotating only changes how "
                      "the page is displayed, so it's instant and lossless.")

        elif action == "Compress":
            row = setting_row(box, "Level")
            option_menu(row, list(LEVELS), self.level_var).pack(
                side="left", fill="x", expand=True
            )
            note(box, "Light only tidies the file, with no change to how it "
                      "looks, and often saves very little. The other levels "
                      "shrink the pictures inside the PDF, which is where "
                      "the big savings are. Text always stays sharp. If a "
                      "PDF can't get smaller, you get an untouched copy "
                      "instead.")

        elif action == "Compress to size":
            row = setting_row(box, "Under")
            entry(row, self.target_mb, width=90).pack(side="left")
            ctk.CTkLabel(row, text="MB", text_color=theme.MUTED,
                         font=theme.font(13)).pack(side="left", padx=6)
            note(box, "Tries gentle compression first and only gets stronger "
                      "if it has to. If even the strongest level can't reach "
                      "your size, the smallest version is still saved and "
                      "you're told.")

        elif action == "Redact text":
            label(box, "Words to remove, one per line", 13,
                  color=theme.MUTED).pack(fill="x", pady=(0, 6))
            self.redact_box = textbox(box, height=100)
            self.redact_box.pack(fill="x")
            self.redact_box.insert("1.0", self.redact_words)
            label(box, "Also find automatically", 13,
                  color=theme.MUTED).pack(fill="x", pady=(10, 4))
            for key, variable in self.preset_vars.items():
                checkbox(box, PRESET_LABELS[key], variable).pack(anchor="w", pady=2)
            note(box, "Not case sensitive. The text is deleted from the file "
                      "itself, not just covered with a black box, and hidden "
                      "details like the author name are scrubbed too. Phone "
                      "number matching can also catch long dates. Scanned "
                      "PDFs are just pictures, so they have no real text to "
                      "find.")

        elif action == "Watermark":
            row = setting_row(box, "Text")
            entry(row, self.mark_text).pack(side="left", fill="x", expand=True)
            slider_row(box, "Size", self.mark_size, 20, 150)
            slider_row(box, "Opacity", self.mark_opacity, 5, 80, "%")
            note(box, "Stamps the text diagonally across the middle of every "
                      "page. Plain English letters and numbers only.")

        elif action == "Page numbers":
            row = setting_row(box, "Position")
            option_menu(row, NUMBER_POSITIONS, self.number_pos).pack(
                side="left", fill="x", expand=True
            )
            row = setting_row(box, "Start at")
            entry(row, self.number_start, width=80).pack(side="left")
            row = setting_row(box, "Style")
            entry(row, self.number_style).pack(side="left", fill="x", expand=True)
            note(box, "In the style, {n} becomes the page number and {total} "
                      "the last page number. For plain numbers just type {n}.")

        elif action == "Strip metadata":
            note(box, "Removes the author, title, creation program and dates "
                      "hidden inside the PDF. The pages themselves don't "
                      "change.")

        elif action == "Lock":
            password_row("Password", self.password_var)
            password_row("Confirm", self.confirm_var)
            note(box, "AES-256 encryption. If you forget the password, the "
                      "file can't be recovered. The password is never saved "
                      "or sent anywhere.")

        elif action == "Unlock":
            password_row("Password", self.password_var)
            note(box, "Makes a copy with the password removed. The password "
                      "has to be right, this isn't a cracker. One password "
                      "is used for every PDF in the list.")

        elif action == "PDF to images":
            row = setting_row(box, "Format")
            option_menu(row, ["png", "jpg"], self.format_var, width=120).pack(side="left")
            row = setting_row(box, "DPI")
            option_menu(row, DPI_CHOICES, self.dpi_var, width=120).pack(side="left")
            note(box, "Each PDF gets its own subfolder. 150 DPI is good for "
                      "reading and 300 for printing, but files get about 4 "
                      "times bigger. Long PDFs at high DPI make a lot of "
                      "files.")

        elif action == "PDF to text":
            checkbox(box, "Mark where each page starts", self.markers_var).pack(anchor="w")
            note(box, "Saves all the text in the PDF as a .txt file. It only "
                      "works on PDFs with real text, not scans.")

        elif action == "OCR scanned PDF":
            checkbox(box, "Mark where each page starts", self.markers_var).pack(anchor="w")
            if find_tool("tesseract") is None:
                note(box, "Tesseract OCR wasn't found. Install it with "
                          "'winget install UB-Mannheim.TesseractOCR', then "
                          "restart the app.")
            else:
                note(box, "Reads the text out of a scanned PDF by looking at "
                          "each page as a picture. Saves a .txt file. English "
                          "only by default. Slower than plain text extraction, "
                          "about 1 second per page.")

        else:
            note(box, "Saves every picture embedded in the PDF as its own "
                      "file, at the original quality. Each PDF gets its own "
                      "subfolder. Tiny pictures like icons are skipped.")

    def make_job(self, files, output):
        action = self.action_var.get()

        if action == "Merge":
            if len(files) < 2:
                raise ValueError("Merging needs at least 2 PDFs.")
            name = clean_name(self.merge_name.get(), "merged", (".pdf",)) + ".pdf"
            return self.single_job(
                f"Merging {len(files)} PDFs...",
                lambda: merge_pdfs(files, output, name),
            )

        if action == "Images to PDF":
            name = clean_name(self.images_name.get(), "images", (".pdf",)) + ".pdf"
            mode = PAGE_SIZES[self.page_size.get()]
            return self.single_job(
                f"Building a PDF from {len(files)} picture(s)...",
                lambda: images_to_pdf(files, output, name, page_mode=mode),
            )

        if action in ("Extract pages", "Delete pages", "Rotate pages", "Reorder pages"):
            pages = self.pages_var.get().strip()
            if not pages:
                raise ValueError("Type which pages you want, like 1-3,5.")
            if action == "Extract pages":
                return self.batch_job(files, output, extract_pages, pages_text=pages)
            if action == "Delete pages":
                return self.batch_job(files, output, delete_pages, pages_text=pages)
            if action == "Reorder pages":
                return self.batch_job(files, output, reorder_pages, pages_text=pages)
            return self.batch_job(
                files, output, rotate_pages, pages_text=pages,
                degrees=ROTATIONS[self.rotation_var.get()],
            )

        if action == "Split into pages":
            every = read_int(self.every_var.get(), "Pages per file", 1, 10000)
            return self.batch_job(files, output, split_action, every=every)

        if action == "Compress":
            self.report_savings = True
            return self.batch_job(
                files, output, compress_pdf, level=LEVELS[self.level_var.get()]
            )

        if action == "Compress to size":
            target = read_float(self.target_mb.get(), "Size", 0.05, 100000)
            self.report_savings = True
            return self.batch_job(files, output, compress_pdf_to_size, target_mb=target)

        if action == "Redact text":
            lines = self.read_redact_words().splitlines()
            words = [line.strip() for line in lines if line.strip()]
            presets = [k for k, v in self.preset_vars.items() if v.get()]
            if not words and not presets:
                raise ValueError("Type a word to remove, or tick something to find automatically.")

            self.redaction_count = 0

            def redact_action(path, output_folder, words, presets):
                new_path, count = redact_text(path, output_folder, words, presets)
                self.redaction_count += count
                return new_path

            return self.batch_job(
                files, output, redact_action, words=words, presets=presets
            )

        if action == "Watermark":
            text = self.mark_text.get().strip()
            if not text:
                raise ValueError("Type the watermark text.")
            return self.batch_job(
                files, output, watermark_pdf, text=text,
                size=int(self.mark_size.get()), opacity=int(self.mark_opacity.get()),
            )

        if action == "Page numbers":
            style = self.number_style.get().strip()
            if "{n}" not in style:
                raise ValueError("The style needs {n} in it, like: Page {n}")
            start = read_int(self.number_start.get(), "Start at", 0, 100000)
            return self.batch_job(
                files, output, add_page_numbers,
                position=self.number_pos.get(), start=start, style=style,
            )

        if action == "Strip metadata":
            return self.batch_job(files, output, strip_pdf_metadata)

        if action in ("Lock", "Unlock"):
            password = self.password_var.get()
            if not password:
                raise ValueError("Type a password.")
            if action == "Lock":
                if password != self.confirm_var.get():
                    raise ValueError("The two passwords don't match.")
                return self.batch_job(files, output, lock_pdf, password=password)
            return self.batch_job(files, output, unlock_pdf, password=password)

        if action == "PDF to images":
            return self.batch_job(
                files, output, images_action,
                fmt="." + self.format_var.get(), dpi=int(self.dpi_var.get()),
            )

        if action == "PDF to text":
            return self.batch_job(
                files, output, pdf_to_text, page_markers=self.markers_var.get()
            )

        if action == "OCR scanned PDF":
            if find_tool("tesseract") is None:
                raise ValueError(
                    "Tesseract OCR isn't installed. Install it with "
                    "'winget install UB-Mannheim.TesseractOCR', then reopen the app."
                )
            return self.batch_job(
                files, output, ocr_pdf, page_markers=self.markers_var.get()
            )

        return self.batch_job(files, output, pictures_action)

    def done_message(self, result):
        count = len(result.done)
        if self.job_action in ORDERED:
            return f"Done. Saved {Path(result.done[0]).name}"
        if self.job_action == "Redact text":
            return (f"Done. Redacted {self.redaction_count} match(es) "
                    f"in {count} file(s).")
        return super().done_message(result)


# ------------------------------------------------------------------ picker

class PagePicker(ctk.CTkToplevel):
    """Visual drag-and-drop style PDF page organizer."""
    
    def __init__(self, parent, pdf_path, initial="", on_apply=None):
        super().__init__(parent)
        self.pdf_path = Path(pdf_path)
        self.on_apply = on_apply
        self.selected_indices = []

        try:
            with pymupdf.open(self.pdf_path) as doc:
                if doc.needs_pass:
                    raise ValueError("This PDF is locked.")
                self.total = len(doc)
        except Exception as e:
            self.destroy()
            raise e

        self.title(f"Organizer — {self.pdf_path.name}")
        self.geometry("900x600")
        self.configure(fg_color=theme.BG)
        self.transient(parent)
        self.grab_set()

        # Main Layout
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # LEFT PANE: All Pages
        left = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)
        
        label(left, "Available Pages", 15, "bold").pack(anchor="w", pady=(0, 8))
        label(left, "Click a page to add it to the sequence.", 12, color=theme.MUTED).pack(anchor="w", pady=(0, 8))
        
        self.grid_frame = SquaredScrollableFrame(
            left, fg_color=theme.PANEL,
        )
        self.grid_frame.pack(fill="both", expand=True)
        
        self._all_images = []
        COLS = 4
        for i in range(self.total):
            holder = ctk.CTkFrame(self.grid_frame, fg_color="transparent", corner_radius=0)
            holder.grid(row=i // COLS, column=i % COLS, padx=4, pady=4, sticky="n")
            
            thumb = self._make_thumb(i, 80)
            self._all_images.append(thumb)
            
            btn = ctk.CTkButton(
                holder, image=thumb, text="", width=80, height=80, corner_radius=0,
                fg_color=theme.BG, hover_color=theme.HOVER,
                command=lambda idx=i: self.add_page(idx)
            )
            btn.pack()
            label(holder, f"Page {i+1}", 11, color=theme.MUTED).pack(pady=(2, 0))

        # RIGHT PANE: Current Sequence
        right = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
        
        label(right, "Current Sequence", 15, "bold").pack(anchor="w", pady=(0, 8))
        label(right, "This is the order they will be saved.", 12, color=theme.MUTED).pack(anchor="w", pady=(0, 8))
        
        self.seq_frame = SquaredScrollableFrame(
            right, fg_color=theme.PANEL,
        )
        self.seq_frame.pack(fill="both", expand=True)

        # Bottom Buttons
        footer = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        footer.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 16))
        secondary_button(footer, "Cancel", self.destroy, width=90).pack(side="right")
        primary_button(footer, "Apply Order", self.apply, width=120).pack(side="right", padx=8)
        secondary_button(footer, "Clear All", self.clear_all, width=90).pack(side="left")

        self._parse_initial(initial)
        self.render_sequence()

    def _make_thumb(self, index, width):
        with pymupdf.open(self.pdf_path) as doc:
            page = doc[index]
            zoom = width / page.rect.width
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            img = PILImage.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))

    def _parse_initial(self, text):
        if not text or not str(text).strip():
            return
        try:
            for i in select_pages(str(text), self.total):
                self.selected_indices.append(i)
        except ValueError:
            pass

    def add_page(self, index):
        self.selected_indices.append(index)
        self.render_sequence()

    def remove_page(self, pos):
        self.selected_indices.pop(pos)
        self.render_sequence()

    def move_left(self, pos):
        if pos > 0:
            self.selected_indices[pos], self.selected_indices[pos-1] = self.selected_indices[pos-1], self.selected_indices[pos]
            self.render_sequence()

    def move_right(self, pos):
        if pos < len(self.selected_indices) - 1:
            self.selected_indices[pos], self.selected_indices[pos+1] = self.selected_indices[pos+1], self.selected_indices[pos]
            self.render_sequence()

    def clear_all(self):
        self.selected_indices.clear()
        self.render_sequence()

    def render_sequence(self):
        for child in self.seq_frame.winfo_children():
            child.destroy()

        if not self.selected_indices:
            label(self.seq_frame, "No pages selected yet.\nClick pages on the left.", 12, color=theme.MUTED, justify="center").pack(pady=40)
            return

        for pos, idx in enumerate(self.selected_indices):
            row = ctk.CTkFrame(self.seq_frame, fg_color=theme.BG, corner_radius=0)
            row.pack(fill="x", pady=2, padx=2)

            thumb = self._make_thumb(idx, 50)
            lbl = ctk.CTkLabel(row, image=thumb, text="", corner_radius=0)
            lbl.image = thumb
            lbl.pack(side="left", padx=6, pady=6)

            label(row, f"Page {idx+1}", 13).pack(side="left", padx=4)

            # Buttons
            small_button(row, "✕", lambda p=pos: self.remove_page(p)).pack(side="right", padx=2)
            small_button(row, ">", lambda p=pos: self.move_right(p)).pack(side="right", padx=2)
            small_button(row, "<", lambda p=pos: self.move_left(p)).pack(side="right", padx=2)

    def apply(self):
        if not self.selected_indices:
            return
        text = ",".join(str(i + 1) for i in self.selected_indices)
        if self.on_apply:
            self.on_apply(text)
        self.destroy()