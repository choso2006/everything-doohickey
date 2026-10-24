from pathlib import Path

import customtkinter as ctk
from PIL import Image

from core.appdata import open_path
from core.audio import AUDIO_ALLOWED, describe_audio
from core.brushes import preview_brush
from core.common import format_time
from core.docs import DOC_ALLOWED, describe_document
from core.images import ALLOWED as IMAGE_EXTENSIONS, preview_image
from core.media import grab_frame, grab_waveform, play_media, probe
from core.pdfs import describe_pdf, render_pdf_page
from core.video import VIDEO_ALLOWED, describe_video
from ui import theme
from ui.asyncload import AsyncLoader
from ui.widgets import label, secondary_button, shorten

BOX = (520, 140)
BRUSH_EXT = (".brush", ".brushset")


def classify(path, prefer="image"):
    ext = Path(path).suffix.lower()
    if ext in BRUSH_EXT:
        return "brush"
    if ext == ".pdf":
        return "pdf"
    if ext in IMAGE_EXTENSIONS and ext in VIDEO_ALLOWED:
        return prefer
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in VIDEO_ALLOWED:
        return "video"
    if ext in AUDIO_ALLOWED:
        return "audio"
    if ext in DOC_ALLOWED:
        return "doc"
    return None


class PreviewPanel(ctk.CTkFrame):
    HEIGHT = 244

    def __init__(self, parent, prefer="image"):
        super().__init__(
            parent, fg_color=theme.PANEL, corner_radius=0,
            border_width=1, border_color=theme.BORDER, height=self.HEIGHT,
        )
        self.pack_propagate(False)
        self.prefer = prefer
        self.path = None
        self.kind = None
        self.duration = 0.0
        self.page_index = 0
        self.page_total = 0
        self._picture = None
        self._frame_job = None
        self._loading_job = None
        self._loading_dots = 0
        self.on_open_pages = None
        self.loader = AsyncLoader(self)

        top = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        top.pack(fill="x", padx=16, pady=(10, 0))
        label(top, "Preview", 15, "bold").pack(side="left")
        self.info = label(top, "", 12, color=theme.MUTED)
        self.info.pack(side="right")

        self.picture = ctk.CTkLabel(
            self, text="", font=theme.font(13), text_color=theme.MUTED,
            height=BOX[1], image=None, corner_radius=0,
        )
        self.picture.pack(fill="both", expand=True, padx=16, pady=6)
        blank = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        self._blank = ctk.CTkImage(light_image=blank, dark_image=blank, size=(1, 1))

        self.controls = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.controls.pack(fill="x", padx=16, pady=(0, 10))

        self.slider_var = ctk.DoubleVar(value=0)
        self.slider = ctk.CTkSlider(
            self.controls, from_=0, to=1, variable=self.slider_var,
            command=self._on_slide, state="disabled",
            fg_color=theme.BORDER, progress_color=theme.ACCENT,
            button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
            corner_radius=0, button_corner_radius=0,
        )
        self.time_label = label(self.controls, "0:00 / 0:00", 12, color=theme.MUTED, width=96)
        self.play_btn = secondary_button(self.controls, "Play", self.play, width=70)
        self.open_btn = secondary_button(self.controls, "Open", self.open, width=70)
        self.prev_btn = secondary_button(self.controls, "<", lambda: self._turn(-1), width=40)
        self.next_btn = secondary_button(self.controls, ">", lambda: self._turn(1), width=40)
        self.page_label = label(self.controls, "", 12, color=theme.MUTED, width=80)
        self.pages_btn = secondary_button(self.controls, "Pages", self._open_pages, width=70)

        self.show(None)

    def show(self, path):
        self.loader.cancel_pending()
        self._cancel_frame_job()
        self._stop_loading_animation()
        self.path = Path(path) if path else None
        self.duration = 0.0
        self.page_index = 0
        self.page_total = 0
        self.kind = classify(self.path, self.prefer) if self.path else None

        if self.path is None:
            self._set_message("Click a file in the list to preview it.")
            self._layout_controls(None)
            self.info.configure(text="")
            return
        if self.kind is None:
            self._set_message("No preview for this kind of file.")
            self._layout_controls(None)
            self.info.configure(text="")
            return

        self._layout_controls(self.kind)
        self._start_loading_animation()
        self.info.configure(text="")

        path = self.path
        if self.kind == "image":
            self.loader.submit(lambda: preview_image(path, BOX), self._image_ready)
        elif self.kind == "brush":
            self.loader.submit(lambda: preview_brush(path, BOX), self._brush_ready)
        elif self.kind == "pdf":
            self._load_pdf_page()
        elif self.kind == "video":
            self.slider.configure(state="disabled")
            self.slider_var.set(0)
            self.loader.submit(
                lambda: (probe(path), describe_video(path), grab_frame(path, 0, BOX[0])),
                self._video_ready,
            )
        elif self.kind == "audio":
            self.loader.submit(
                lambda: (grab_waveform(path, BOX[0], BOX[1] - 10), describe_audio(path)),
                self._audio_ready,
            )
        else:
            self._stop_loading_animation()
            self._set_message("No picture preview for documents.\nUse Open to see it.")
            try:
                self.info.configure(text=shorten(describe_document(path), 70))
            except OSError:
                pass

    def current_seconds(self):
        return float(self.slider_var.get()) if self.kind == "video" else 0.0

    def play(self, start=None, end=None):
        if not self.path:
            return
        if start is None and self.kind == "video":
            start = self.current_seconds()

        if self.kind == "video":
            try:
                from ui.player import open_player
                open_player(self.winfo_toplevel(), self.path, start, end)
                return
            except Exception as e:
                try:
                    from ui.widgets import ToastNotification
                    ToastNotification(
                        self.winfo_toplevel(), "Video player",
                        f"Couldn't open: {str(e)[:100]}", icon="⚠️",
                    )
                except Exception:
                    pass

        try:
            play_media(self.path, start, end, audio_only=(self.kind == "audio"))
        except OSError:
            pass

    def open(self):
        if self.path:
            open_path(self.path)

    def _open_pages(self):
        if self.on_open_pages:
            self.on_open_pages()

    def _layout_controls(self, kind):
        for widget in (self.slider, self.time_label, self.play_btn, self.open_btn,
                       self.prev_btn, self.next_btn, self.page_label, self.pages_btn):
            widget.pack_forget()

        if kind == "video":
            self.slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
            self.time_label.pack(side="left")
            self.play_btn.pack(side="left", padx=(8, 0))
        elif kind == "audio":
            self.play_btn.pack(side="left")
            self.open_btn.pack(side="left", padx=8)
        elif kind == "pdf":
            self.prev_btn.pack(side="left")
            self.page_label.configure(anchor="center")
            self.page_label.pack(side="left", padx=4)
            self.next_btn.pack(side="left")
            self.pages_btn.pack(side="left", padx=(8, 0))
            self.open_btn.pack(side="right")
        elif kind in ("image", "doc", "brush"):
            self.open_btn.pack(side="left")

    def _set_message(self, text):
        self._stop_loading_animation()
        self.picture.configure(image=self._blank, text=text)
        self._picture = None

    def _start_loading_animation(self):
        self._stop_loading_animation()
        self._loading_dots = 0
        self._animate_loading()

    def _stop_loading_animation(self):
        if self._loading_job:
            try:
                self.after_cancel(self._loading_job)
            except Exception:
                pass
            self._loading_job = None

    def _animate_loading(self):
        if not self.path:
            return
        dots = "." * (self._loading_dots % 4)
        self.picture.configure(image=self._blank, text=f"Loading{dots}")
        self._loading_dots += 1
        self._loading_job = self.after(400, self._animate_loading)

    def _set_picture(self, pil_image):
        self._stop_loading_animation()
        shown = pil_image.copy()
        shown.thumbnail(BOX, Image.Resampling.LANCZOS)
        fresh = ctk.CTkImage(
            light_image=shown, dark_image=shown, size=(shown.width, shown.height)
        )
        self.picture.configure(image=fresh, text="")
        self._picture = fresh

    def _image_ready(self, value, error):
        if error:
            self._set_message(shorten(str(error), 80))
            return
        picture, info = value
        self._set_picture(picture)
        self.info.configure(text=shorten(info, 70))

    def _brush_ready(self, value, error):
        if error or not value:
            self._set_message("Couldn't read this brush file.")
            self.info.configure(text="")
            return
        picture, info = value
        self._set_picture(picture)
        self.info.configure(text=shorten(info, 70))

    def _load_pdf_page(self):
        path, index = self.path, self.page_index
        self.loader.submit(
            lambda: (render_pdf_page(path, index, 360), describe_pdf(path)),
            self._pdf_ready,
        )

    def _pdf_ready(self, value, error):
        if error:
            if str(error) == "locked":
                self._set_message("This PDF is password protected.")
                self.info.configure(text="Locked")
            else:
                self._set_message(shorten(str(error), 80))
            self.page_label.configure(text="")
            return
        (picture, total), info = value
        self.page_total = total
        self._set_picture(picture)
        self.page_label.configure(text=f"{self.page_index + 1} / {total}")
        self.info.configure(text=shorten(info, 70))

    def _turn(self, step):
        if self.kind != "pdf" or not self.page_total:
            return
        self.page_index = max(0, min(self.page_total - 1, self.page_index + step))
        self._start_loading_animation()
        self._load_pdf_page()

    def _video_ready(self, value, error):
        if error:
            self._set_message(shorten(str(error), 80))
            return
        info, description, frame = value
        self.duration = float(info["duration"] or 0)
        self.slider.configure(
            state="normal" if self.duration > 0 else "disabled",
            to=max(self.duration, 0.1),
        )
        self.slider_var.set(0)
        self._update_time(0)
        self._set_picture(frame)
        self.info.configure(text=shorten(description, 70))

    def _audio_ready(self, value, error):
        if error:
            self._set_message(shorten(str(error), 80))
            return
        wave, description = value
        self._set_picture(wave)
        self.info.configure(text=shorten(description, 70))

    def _update_time(self, seconds):
        self.time_label.configure(
            text=f"{format_time(seconds)} / {format_time(self.duration)}"
        )

    def _cancel_frame_job(self):
        if self._frame_job is not None:
            try:
                self.after_cancel(self._frame_job)
            except Exception:
                pass
            self._frame_job = None

    def _on_slide(self, value):
        self._update_time(float(value))
        self._cancel_frame_job()
        self._frame_job = self.after(140, self._load_frame)

    def _load_frame(self):
        self._frame_job = None
        if self.kind != "video" or not self.path:
            return
        path, seconds = self.path, self.current_seconds()
        self.loader.submit(lambda: grab_frame(path, seconds, BOX[0]), self._frame_ready)

    def _frame_ready(self, frame, error):
        if error:
            return
        self._set_picture(frame)