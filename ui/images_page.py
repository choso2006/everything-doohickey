import customtkinter as ctk

from core.common import clean_name
from core.images import (
    ALLOWED, OUTPUT_FORMATS, WATERMARK_POSITIONS, adjust_image, compress_image,
    compress_image_to_size, convert_image, images_to_animation, resize_image,
    rotate_image, strip_metadata, watermark_image,
)
from ui import theme
from ui.toolpage import ToolPage
from ui.widgets import (
    checkbox, entry, note, option_menu, read_float, read_int, setting_row,
    slider_row,
)

ACTIONS = [
    "Convert", "Compress", "Compress to size", "Resize", "Rotate or flip",
    "Adjust colors", "Watermark", "Strip metadata", "Make animation",
]
RESIZE_MODES = ["Width", "Height", "Percent", "Fit inside box", "Exact size"]
ROTATIONS = {
    "No rotation": 0,
    "90\u00b0 clockwise": 90,
    "180\u00b0": 180,
    "90\u00b0 counter-clockwise": 270,
}
ANIMATION_FORMATS = ["gif", "webp", "png"]
KEEP_NOTE = (
    "Photos carry hidden info like camera model, dates and GPS location. "
    "Leave this off to remove it."
)


class ImagesPage(ToolPage):
    ACTIONS = ACTIONS

    def __init__(self, parent, state=None):
        super().__init__(
            parent, "Images",
            "Convert, compress, resize, edit and clean up pictures.", state,
        )
        R = self.remember
        self.format_var = R("format", ctk.StringVar(value="jpg"))
        self.quality_var = R("quality", ctk.DoubleVar(value=90))
        self.compress_var = R("compress_quality", ctk.DoubleVar(value=70))
        self.size_value = R("size_value", ctk.StringVar(value="500"))
        self.size_unit = R("size_unit", ctk.StringVar(value="KB"))
        self.resize_mode = R("resize_mode", ctk.StringVar(value="Width"))
        self.width_var = R("width", ctk.StringVar(value="1280"))
        self.height_var = R("height", ctk.StringVar(value="720"))
        self.percent_var = R("percent", ctk.StringVar(value="50"))
        self.rotate_var = R("rotate", ctk.StringVar(value="90\u00b0 clockwise"))
        self.flip_h = R("flip_h", ctk.BooleanVar(value=False))
        self.flip_v = R("flip_v", ctk.BooleanVar(value=False))
        self.brightness = R("brightness", ctk.DoubleVar(value=100))
        self.contrast = R("contrast", ctk.DoubleVar(value=100))
        self.color = R("color", ctk.DoubleVar(value=100))
        self.gray = R("gray", ctk.BooleanVar(value=False))
        self.mark_text = R("mark_text", ctk.StringVar(value="Your name"))
        self.mark_position = R("mark_position", ctk.StringVar(value="Bottom right"))
        self.mark_size = R("mark_size", ctk.DoubleVar(value=5))
        self.mark_opacity = R("mark_opacity", ctk.DoubleVar(value=60))
        self.mark_color = R("mark_color", ctk.StringVar(value="White"))
        self.keep_meta = R("keep_meta", ctk.BooleanVar(value=False))
        self.anim_format = R("anim_format", ctk.StringVar(value="gif"))
        self.anim_ms = R("anim_ms", ctk.StringVar(value="200"))
        self.anim_loop = R("anim_loop", ctk.BooleanVar(value=True))
        self.anim_name = R("anim_name", ctk.StringVar(value="animation"))
        self.anim_width = R("anim_width", ctk.StringVar(value=""))

        self.build()

    def current_extensions(self):
        return ALLOWED

    def is_ordered(self):
        return self.action_var.get() == "Make animation"

    # ---------- settings panel ----------

    def build_settings(self):
        for child in self.settings.winfo_children():
            child.destroy()

        action = self.action_var.get()
        box = self.settings

        if action == "Convert":
            row = setting_row(box, "Format")
            option_menu(row, OUTPUT_FORMATS, self.format_var, width=120).pack(side="left")
            slider_row(box, "Quality", self.quality_var, 1, 100)
            checkbox(box, "Keep metadata", self.keep_meta).pack(anchor="w", pady=(6, 0))
            note(box, "Quality applies to JPG, WebP, AVIF and HEIC. See-through "
                      "pictures get a white background when saved as JPG. "
                      "Animated GIF, WebP and PNG keep their animation. ICO "
                      "files are made square with several icon sizes inside. "
                      + KEEP_NOTE)

        elif action == "Compress":
            slider_row(box, "Quality", self.compress_var, 1, 100)
            checkbox(box, "Keep metadata", self.keep_meta).pack(anchor="w", pady=(6, 0))
            note(box, "Lower quality means a smaller file. It applies to JPG, "
                      "WebP, AVIF and HEIC. PNG can't lose quality, so it only "
                      "gets lossless optimizing. BMP can't be compressed, "
                      "convert it first. Every file keeps its own format. "
                      + KEEP_NOTE)

        elif action == "Compress to size":
            row = setting_row(box, "Under")
            entry(row, self.size_value, width=90).pack(side="left")
            option_menu(row, ["KB", "MB"], self.size_unit, width=80).pack(
                side="left", padx=(8, 0)
            )
            checkbox(box, "Keep metadata", self.keep_meta).pack(anchor="w", pady=(6, 0))
            note(box, "Lowers the quality as little as possible to get each "
                      "picture under this size, and shrinks it too if it has "
                      "to. Pictures already under the limit are copied "
                      "untouched. Works for JPG, PNG, WebP, AVIF and HEIC.")

        elif action == "Resize":
            row = setting_row(box, "Resize by")
            option_menu(
                row, RESIZE_MODES, self.resize_mode, command=self.rebuild_soon
            ).pack(side="left", fill="x", expand=True)
            mode = self.resize_mode.get()
            if mode in ("Width", "Exact size", "Fit inside box"):
                row = setting_row(box, "Width")
                entry(row, self.width_var, width=110).pack(side="left")
                label_px = ctk.CTkLabel(row, text="px", text_color=theme.MUTED,
                                        font=theme.font(13))
                label_px.pack(side="left", padx=6)
            if mode in ("Height", "Exact size", "Fit inside box"):
                row = setting_row(box, "Height")
                entry(row, self.height_var, width=110).pack(side="left")
                label_px = ctk.CTkLabel(row, text="px", text_color=theme.MUTED,
                                        font=theme.font(13))
                label_px.pack(side="left", padx=6)
            if mode == "Percent":
                row = setting_row(box, "Percent")
                entry(row, self.percent_var, width=110).pack(side="left")
                ctk.CTkLabel(row, text="%", text_color=theme.MUTED,
                             font=theme.font(13)).pack(side="left", padx=6)
            checkbox(box, "Keep metadata", self.keep_meta).pack(anchor="w", pady=(6, 0))
            note(box, {
                "Width": "The height follows automatically so nothing gets squashed.",
                "Height": "The width follows automatically so nothing gets squashed.",
                "Percent": "50 means half the size, 200 means double.",
                "Fit inside box": "Keeps the proportions and fits the picture inside this box.",
                "Exact size": "Forces this exact size. The picture can look stretched.",
            }[mode] + " Every file keeps its own format.")

        elif action == "Rotate or flip":
            row = setting_row(box, "Rotate")
            option_menu(row, list(ROTATIONS), self.rotate_var).pack(
                side="left", fill="x", expand=True
            )
            checkbox(box, "Flip left to right", self.flip_h).pack(anchor="w", pady=(6, 0))
            checkbox(box, "Flip upside down", self.flip_v).pack(anchor="w", pady=(6, 0))
            checkbox(box, "Keep metadata", self.keep_meta).pack(anchor="w", pady=(6, 0))
            note(box, "Rotation is applied to the picture itself, so it looks "
                      "the same in every app. Animations keep animating.")

        elif action == "Adjust colors":
            slider_row(box, "Brightness", self.brightness, 20, 200, "%")
            slider_row(box, "Contrast", self.contrast, 20, 200, "%")
            slider_row(box, "Color", self.color, 0, 200, "%")
            checkbox(box, "Black and white", self.gray).pack(anchor="w", pady=(6, 0))
            checkbox(box, "Keep metadata", self.keep_meta).pack(anchor="w", pady=(6, 0))
            note(box, "100% means unchanged. Use the preview panel to see the "
                      "original, and open the result afterwards to compare.")

        elif action == "Watermark":
            row = setting_row(box, "Text")
            entry(row, self.mark_text).pack(side="left", fill="x", expand=True)
            row = setting_row(box, "Position")
            option_menu(row, WATERMARK_POSITIONS, self.mark_position).pack(
                side="left", fill="x", expand=True
            )
            row = setting_row(box, "Color")
            option_menu(row, ["White", "Black"], self.mark_color, width=120).pack(side="left")
            slider_row(box, "Size", self.mark_size, 2, 25, "%")
            slider_row(box, "Opacity", self.mark_opacity, 10, 100, "%")
            checkbox(box, "Keep metadata", self.keep_meta).pack(anchor="w", pady=(6, 0))
            note(box, "Size is a percent of the picture's width. Tiled repeats "
                      "the text diagonally across the whole picture. Plain "
                      "English letters and numbers work best.")

        elif action == "Strip metadata":
            note(box, "Removes camera info, dates and GPS location from the "
                      "file. The picture is rebuilt from its pixels only, so "
                      "nothing hidden comes along. Photos are rotated the "
                      "right way up first, so they don't end up sideways. "
                      "Every file keeps its own format.")

        else:
            row = setting_row(box, "Name")
            entry(row, self.anim_name).pack(side="left", fill="x", expand=True)
            row = setting_row(box, "Format")
            option_menu(row, ANIMATION_FORMATS, self.anim_format, width=120).pack(side="left")
            row = setting_row(box, "Frame time")
            entry(row, self.anim_ms, width=90).pack(side="left")
            ctk.CTkLabel(row, text="ms", text_color=theme.MUTED,
                         font=theme.font(13)).pack(side="left", padx=6)
            row = setting_row(box, "Width")
            entry(row, self.anim_width, width=90).pack(side="left")
            ctk.CTkLabel(row, text="px (blank = first picture)", text_color=theme.MUTED,
                         font=theme.font(12)).pack(side="left", padx=6)
            checkbox(box, "Loop forever", self.anim_loop).pack(anchor="w", pady=(6, 0))
            note(box, "Joins the pictures into one animation, in the order "
                      "shown on the left. Use the arrows to reorder. Pictures "
                      "of other sizes are fitted inside the first one's size. "
                      "200 ms per frame is 5 frames a second.")

    # ---------- building the job ----------

    def make_job(self, files, output):
        action = self.action_var.get()
        keep = self.keep_meta.get()

        if action == "Convert":
            return self.batch_job(
                files, output, convert_image,
                target_format="." + self.format_var.get(),
                quality=int(self.quality_var.get()), keep_metadata=keep,
            )

        if action == "Compress":
            self.report_savings = True
            return self.batch_job(
                files, output, compress_image,
                quality=int(self.compress_var.get()), keep_metadata=keep,
            )

        if action == "Compress to size":
            amount = read_float(self.size_value.get(), "Size", 2, 1_000_000)
            kb = amount * (1024 if self.size_unit.get() == "MB" else 1)
            if kb < 2:
                raise ValueError("Size must be at least 2 KB.")
            self.report_savings = True
            return self.batch_job(
                files, output, compress_image_to_size,
                target_kb=kb, keep_metadata=keep,
            )

        if action == "Resize":
            mode = self.resize_mode.get()
            options = {"keep_metadata": keep}
            if mode == "Width":
                options["width"] = read_int(self.width_var.get(), "Width", 1, 30000)
            elif mode == "Height":
                options["height"] = read_int(self.height_var.get(), "Height", 1, 30000)
            elif mode == "Percent":
                options["percent"] = read_float(self.percent_var.get(), "Percent", 1, 1000)
            else:
                w = read_int(self.width_var.get(), "Width", 1, 30000)
                h = read_int(self.height_var.get(), "Height", 1, 30000)
                if mode == "Fit inside box":
                    options["fit"] = (w, h)
                else:
                    options["width"], options["height"] = w, h
            return self.batch_job(files, output, resize_image, **options)

        if action == "Rotate or flip":
            degrees = ROTATIONS[self.rotate_var.get()]
            if not degrees and not self.flip_h.get() and not self.flip_v.get():
                raise ValueError("Pick a rotation or tick a flip.")
            return self.batch_job(
                files, output, rotate_image, degrees=degrees,
                flip_h=self.flip_h.get(), flip_v=self.flip_v.get(),
                keep_metadata=keep,
            )

        if action == "Adjust colors":
            values = (int(self.brightness.get()), int(self.contrast.get()),
                      int(self.color.get()), self.gray.get())
            if values == (100, 100, 100, False):
                raise ValueError("Nothing to change yet. Move a slider or tick Black and white.")
            return self.batch_job(
                files, output, adjust_image,
                brightness=values[0], contrast=values[1], color=values[2],
                grayscale=values[3], keep_metadata=keep,
            )

        if action == "Watermark":
            text = self.mark_text.get().strip()
            if not text:
                raise ValueError("Type the watermark text.")
            return self.batch_job(
                files, output, watermark_image, text=text,
                position=self.mark_position.get(),
                size_percent=int(self.mark_size.get()),
                opacity=int(self.mark_opacity.get()),
                color=self.mark_color.get().lower(), keep_metadata=keep,
            )

        if action == "Strip metadata":
            return self.batch_job(files, output, strip_metadata)

        if len(files) < 2:
            raise ValueError("An animation needs at least 2 pictures.")
        frame_ms = read_int(self.anim_ms.get(), "Frame time", 20, 10000)
        width = None
        if self.anim_width.get().strip():
            width = read_int(self.anim_width.get(), "Width", 16, 8000)
        name = clean_name(self.anim_name.get(), "animation")
        fmt = self.anim_format.get()
        loop = self.anim_loop.get()
        return self.single_job(
            f"Building the animation from {len(files)} pictures...",
            lambda: images_to_animation(
                files, output, name, fmt, frame_ms, loop, width
            ),
        )

    def done_message(self, result):
        if self.job_action == "Make animation":
            return f"Done. Saved {result.done[0].name}"
        return super().done_message(result)
