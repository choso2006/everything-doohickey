from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.audio import AUDIO_FORMATS
from core.common import clean_name, format_stamp, to_seconds
from core.media import play_media
from core.tools import find_tool, HINTS
from core.video import (
    ASPECT_RATIOS, VIDEO_ALLOWED, VIDEO_FORMATS, change_speed, compress_video,
    compress_video_to_size, convert_video, crop_video, extract_audio,
    extract_frames, merge_videos, remove_audio, replace_audio, rotate_video,
    screenshot, trim_video, video_to_gif,
)
from ui import theme
from ui.toolpage import ToolPage
from ui.widgets import (
    checkbox, entry, label, note, option_menu, read_float, read_int,
    secondary_button, setting_row, shorten,
)

ACTIONS = [
    "Convert", "Compress", "Compress to size", "Extract audio", "Trim",
    "Merge", "Make a GIF", "Change speed", "Rotate or flip", "Crop to shape",
    "Replace audio", "Remove sound", "Save a picture",
    "Save pictures every few seconds",
]
QUALITY = {
    "High quality": 20,
    "Balanced": 26,
    "Small file": 30,
    "Tiny file": 34,
}
HEIGHTS = {
    "Keep original": None,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
}
MATCH = "Match first video"
RESOLUTIONS = [MATCH, "1280x720", "1920x1080", "854x480", "3840x2160"]
FPS_CHOICES = [MATCH, "24", "25", "30", "60"]
SIZE_PICKS = ["Custom", "8 MB", "10 MB", "16 MB", "25 MB", "50 MB", "100 MB"]
SPEEDS = ["0.25", "0.5", "0.75", "1.5", "2", "3", "4"]
GIF_WIDTHS = ["240", "320", "480", "640", "800"]
GIF_FPS = ["8", "10", "12", "15", "20"]
ROTATIONS = {
    "No rotation": 0,
    "90\u00b0 clockwise": 90,
    "180\u00b0": 180,
    "90\u00b0 counter-clockwise": 270,
}
CROP_MODES = {"Fill (crop edges)": "crop", "Fit (black bars)": "pad"}
BITRATES = {"96 kbps": 96, "128 kbps": 128, "192 kbps": 192, "320 kbps": 320}


class VideoPage(ToolPage):
    ACTIONS = ACTIONS
    PREVIEW_PREFER = "video"

    def __init__(self, parent, state=None):
        super().__init__(
            parent, "Video",
            "Convert, shrink, trim, join and get things out of videos.", state,
        )
        R = self.remember
        self.format_var = R("format", ctk.StringVar(value="mp4"))
        self.fast_copy = R("fast_copy", ctk.BooleanVar(value=False))
        self.audio_var = R("audio_format", ctk.StringVar(value="mp3"))
        self.bitrate_var = R("bitrate", ctk.StringVar(value="192 kbps"))
        self.quality_var = R("quality", ctk.StringVar(value="Balanced"))
        self.height_var = R("height", ctk.StringVar(value="Keep original"))
        self.target_mb = R("target_mb", ctk.StringVar(value="25"))
        self.size_pick = ctk.StringVar(value="Custom")
        self.start_var = ctk.StringVar(value="0:00:00.00")
        self.end_var = ctk.StringVar(value="0:00:10.00")
        self.precise_var = R("precise", ctk.BooleanVar(value=False))
        self.merge_name = R("merge_name", ctk.StringVar(value="merged"))
        self.reencode_var = R("reencode", ctk.BooleanVar(value=False))
        self.res_var = R("resolution", ctk.StringVar(value=MATCH))
        self.fps_var = R("fps", ctk.StringVar(value=MATCH))
        self.gif_width = R("gif_width", ctk.StringVar(value="480"))
        self.gif_fps = R("gif_fps", ctk.StringVar(value="12"))
        self.gif_start = ctk.StringVar(value="")
        self.gif_end = ctk.StringVar(value="")
        self.speed_var = R("speed", ctk.StringVar(value="2"))
        self.rotate_var = R("rotate", ctk.StringVar(value="90\u00b0 clockwise"))
        self.flip_h = R("flip_h", ctk.BooleanVar(value=False))
        self.flip_v = R("flip_v", ctk.BooleanVar(value=False))
        self.shot_time = ctk.StringVar(value="0:00:00.00")
        self.picture_format = R("picture_format", ctk.StringVar(value="png"))
        self.every_var = R("every", ctk.StringVar(value="5"))
        self.crop_aspect = R("crop_aspect", ctk.StringVar(value="1:1 square"))
        self.crop_mode = R("crop_mode", ctk.StringVar(value="Fill (crop edges)"))
        self.new_audio = ctk.StringVar(value="")
        self.mix_audio = R("mix_audio", ctk.BooleanVar(value=False))
        self.audio_label = None

        self.build()

    def current_extensions(self):
        return VIDEO_ALLOWED

    def is_ordered(self):
        return self.action_var.get() == "Merge"

    def time_row(self, text, variable):
        row = setting_row(self.settings, text)
        entry(row, variable, width=120).pack(side="left")
        secondary_button(
            row, "Use preview",
            lambda: variable.set(format_stamp(self.preview.current_seconds())),
            width=96,
        ).pack(side="left", padx=(8, 0))
        return row

    def play_selection(self):
        try:
            start, end = to_seconds(self.start_var.get()), to_seconds(self.end_var.get())
        except ValueError as e:
            self.set_status(str(e), error=True)
            return
        if end <= start:
            self.set_status("The end time has to be after the start time.", error=True)
            return
        if self.preview.path is None:
            self.set_status("Click a video in the list first.", error=True)
            return
        play_media(self.preview.path, start, end)

    def pick_size(self, choice):
        if choice != "Custom":
            self.target_mb.set(choice.split()[0])

    def pick_audio(self):
        path = filedialog.askopenfilename(
            title="Choose the audio file",
            filetypes=[
                ("Audio", "*.mp3 *.wav *.m4a *.aac *.ogg *.opus *.flac *.aiff"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.new_audio.set(path)
            self._refresh_audio_label()

    def _refresh_audio_label(self):
        if self.audio_label is None:
            return
        try:
            if not self.audio_label.winfo_exists():
                return
        except Exception:
            return
        path = self.new_audio.get()
        if path:
            self.audio_label.configure(text=shorten(Path(path).name, 30))
        else:
            self.audio_label.configure(text="(none chosen)")

    def build_settings(self):
        self.audio_label = None
        for child in self.settings.winfo_children():
            child.destroy()

        action = self.action_var.get()
        box = self.settings

        def menu_row(text, values, variable, command=None, width=None):
            row = setting_row(box, text)
            kwargs = {"width": width} if width else {}
            menu = option_menu(row, values, variable, command=command, **kwargs)
            menu.pack(side="left", **({} if width else {"fill": "x", "expand": True}))
            return row

        if action == "Convert":
            menu_row("Format", VIDEO_FORMATS, self.format_var, width=120)
            menu_row("Quality", list(QUALITY), self.quality_var)
            checkbox(box, "Fast copy (no re-encoding)", self.fast_copy).pack(
                anchor="w", pady=(8, 0))
            note(box, "Re-encodes the video with the standard codecs for the "
                      "format, so it takes real time on long videos. MP4 and "
                      "MKV are the quick ones, WebM is much slower. Fast copy "
                      "just moves the video into a new container, instantly "
                      "and with no quality loss, but it only works between "
                      "compatible formats. Subtitles are left out. GIFs can "
                      "be converted to video too.")

        elif action == "Compress":
            menu_row("Quality", list(QUALITY), self.quality_var)
            menu_row("Size", list(HEIGHTS), self.height_var)
            note(box, "The result is always an MP4 (H.264 video, AAC audio), "
                      "which plays almost everywhere. Picking a smaller size "
                      "never enlarges a video that's already smaller. How "
                      "much you save depends on the video. To hit a specific "
                      "file size, use Compress to size.")

        elif action == "Compress to size":
            row = setting_row(box, "Under")
            entry(row, self.target_mb, width=90).pack(side="left")
            ctk.CTkLabel(row, text="MB", text_color=theme.MUTED,
                         font=theme.font(13)).pack(side="left", padx=6)
            menu_row("Quick pick", SIZE_PICKS, self.size_pick, command=self.pick_size)
            note(box, "Works out the video quality that fits your size, then "
                      "encodes in two passes so it lands just under the "
                      "limit. Long videos in a small size get a lower "
                      "resolution automatically, because squeezing a big "
                      "picture into few bits looks blocky. Videos already "
                      "under the size are skipped. The result is an MP4.")

        elif action == "Extract audio":
            menu_row("Format", AUDIO_FORMATS, self.audio_var, width=120)
            menu_row("Bitrate", list(BITRATES), self.bitrate_var, width=120)
            note(box, "Pulls the sound out of the video. MP3, M4A, AAC, OGG and "
                      "Opus are small. FLAC is lossless and WAV and AIFF are "
                      "uncompressed and big. Bitrate only matters for the "
                      "small formats. A video with no sound will fail.")

        elif action == "Trim":
            self.time_row("Start", self.start_var)
            self.time_row("End", self.end_var)
            secondary_button(box, "Play this part", self.play_selection, width=130).pack(
                anchor="w", pady=(8, 0))
            checkbox(box, "Exact cut (slower)", self.precise_var).pack(
                anchor="w", pady=(10, 0))
            note(box, "Drag the slider in the preview to a moment, then press "
                      "Use preview next to Start or End. You can also type "
                      "times like 45, 1:30 or 1:02:03.5. This works on one "
                      "video at a time. The default cut is instant and loses "
                      "no quality, but it can start a second or two early "
                      "because videos can only be cut cleanly at certain "
                      "frames. Exact cut re-encodes to land on the right frame.")

        elif action == "Merge":
            row = setting_row(box, "Name")
            entry(row, self.merge_name).pack(side="left", fill="x", expand=True)
            checkbox(
                box, "Re-encode (works with any clips)", self.reencode_var,
                command=self.rebuild_soon,
            ).pack(anchor="w", pady=(8, 0))
            if self.reencode_var.get():
                menu_row("Size", RESOLUTIONS, self.res_var)
                menu_row("Frame rate", FPS_CHOICES, self.fps_var)
                menu_row("Quality", list(QUALITY), self.quality_var)
                note(box, "Slower, but it works with any mix of clips. Clips "
                          "without sound get silence so everything lines up, "
                          "and smaller clips get black bars instead of being "
                          "stretched. The result is always an MP4. Phone "
                          "videos recorded sideways can confuse 'Match first "
                          "video', so pick a size yourself if one comes out "
                          "wrong.")
            else:
                note(box, "Joins the videos in the order shown on the left. "
                          "It's instant and loses no quality, but every clip "
                          "must have the same format, codec, size, frame "
                          "rate and audio, like clips from one camera. If "
                          "they don't match you'll be told, and you can tick "
                          "Re-encode instead.")

        elif action == "Make a GIF":
            menu_row("Width", GIF_WIDTHS, self.gif_width, width=120)
            menu_row("Frames/sec", GIF_FPS, self.gif_fps, width=120)
            self.time_row("Start", self.gif_start)
            self.time_row("End", self.gif_end)
            note(box, "Leave Start and End empty to use the whole video. GIFs "
                      "get big fast, so keep them short, small and at a low "
                      "frame rate. The limit is 2 minutes. Videos with sound "
                      "lose it, since GIFs have none.")

        elif action == "Change speed":
            menu_row("Speed", SPEEDS, self.speed_var, width=120)
            note(box, "2 plays twice as fast, 0.5 plays in slow motion. The "
                      "sound speeds up or slows down with it but keeps its "
                      "pitch. The result is an MP4.")

        elif action == "Rotate or flip":
            menu_row("Rotate", list(ROTATIONS), self.rotate_var)
            checkbox(box, "Flip left to right", self.flip_h).pack(anchor="w", pady=(6, 0))
            checkbox(box, "Flip upside down", self.flip_v).pack(anchor="w", pady=(6, 0))
            note(box, "Re-encodes the video turned the way you pick, which "
                      "fixes sideways phone videos. The result is an MP4.")

        elif action == "Crop to shape":
            menu_row("Aspect", list(ASPECT_RATIOS), self.crop_aspect)
            menu_row("Method", list(CROP_MODES), self.crop_mode)
            note(box, "Fill cuts the edges to reach the chosen shape. Fit "
                      "keeps everything and adds black bars. Both re-encode "
                      "to MP4. Useful for phone screens (9:16) or social "
                      "media (1:1, 4:5).")

        elif action == "Replace audio":
            row = setting_row(box, "Audio")
            ctk.CTkButton(
                row, text="Choose file", width=110, height=34, corner_radius=6,
                font=theme.font(13), fg_color=theme.PANEL, hover_color=theme.HOVER,
                border_width=1, border_color=theme.BORDER, text_color=theme.TEXT,
                command=self.pick_audio,
            ).pack(side="left")
            self.audio_label = label(row, "", 12, color=theme.MUTED)
            self.audio_label.pack(side="left", padx=(8, 0))
            self._refresh_audio_label()
            checkbox(box, "Mix with the video's own sound", self.mix_audio).pack(
                anchor="w", pady=(10, 0)
            )
            note(box, "The video is copied without re-encoding, so it stays "
                      "the same quality. The audio track is replaced (or "
                      "mixed in). The result is an MP4.")

        elif action == "Remove sound":
            note(box, "Makes a silent copy of the video. It's instant and the "
                      "picture isn't touched.")

        elif action == "Save a picture":
            self.time_row("At", self.shot_time)
            menu_row("Format", ["png", "jpg"], self.picture_format, width=120)
            note(box, "Saves one still picture from the video at that moment. "
                      "Drag the preview slider, then press Use preview. "
                      "PNG is sharpest, JPG is smaller.")

        else:
            row = setting_row(box, "Every")
            entry(row, self.every_var, width=90).pack(side="left")
            ctk.CTkLabel(row, text="seconds", text_color=theme.MUTED,
                         font=theme.font(13)).pack(side="left", padx=6)
            menu_row("Format", ["png", "jpg"], self.picture_format, width=120)
            note(box, "Saves a picture every few seconds, in a subfolder named "
                      "after the video. Up to 2000 pictures per video.")

    def make_job(self, files, output):
        if find_tool("ffmpeg") is None or find_tool("ffprobe") is None:
            raise ValueError(HINTS["ffmpeg"])

        action = self.action_var.get()
        job = self.batch_job
        quality = QUALITY[self.quality_var.get()]

        if action == "Convert":
            return job(files, output, convert_video, hooks=True,
                       target_format="." + self.format_var.get(), crf=quality,
                       fast_copy=self.fast_copy.get())

        if action == "Compress":
            self.report_savings = True
            return job(files, output, compress_video, hooks=True, crf=quality,
                       max_height=HEIGHTS[self.height_var.get()])

        if action == "Compress to size":
            target = read_float(self.target_mb.get(), "Size", 0.2, 100000)
            self.report_savings = True
            return job(files, output, compress_video_to_size, hooks=True,
                       target_mb=target)

        if action == "Extract audio":
            return job(files, output, extract_audio, hooks=True,
                       fmt="." + self.audio_var.get(),
                       kbps=BITRATES[self.bitrate_var.get()])

        if action == "Trim":
            if len(files) != 1:
                raise ValueError(
                    "Trim works on one video at a time. Remove the others from the list."
                )
            start, end = self.start_var.get().strip(), self.end_var.get().strip()
            if not start or not end:
                raise ValueError("Type a start time and an end time.")
            if to_seconds(end) <= to_seconds(start):
                raise ValueError("The end time has to be after the start time.")
            return job(files, output, trim_video, hooks=True, start=start,
                       end=end, precise=self.precise_var.get())

        if action == "Merge":
            if len(files) < 2:
                raise ValueError("Merging needs at least 2 videos.")
            name = clean_name(self.merge_name.get(), "merged", VIDEO_ALLOWED) + ".mp4"
            reencode = self.reencode_var.get()
            resolution = None
            if self.res_var.get() != MATCH:
                resolution = tuple(int(x) for x in self.res_var.get().split("x"))
            fps = None if self.fps_var.get() == MATCH else int(self.fps_var.get())
            return self.tracked_job(
                f"Joining {len(files)} videos...",
                lambda progress, cancel: merge_videos(
                    files, output, output_name=name, reencode=reencode,
                    resolution=resolution, fps=fps, crf=quality,
                    progress=progress, cancel=cancel,
                ),
            )

        if action == "Make a GIF":
            start, end = self.gif_start.get().strip(), self.gif_end.get().strip()
            for value in (start, end):
                if value:
                    to_seconds(value)
            return job(files, output, video_to_gif, hooks=True,
                       fps=int(self.gif_fps.get()), width=int(self.gif_width.get()),
                       start=start or None, end=end or None)

        if action == "Change speed":
            factor = read_float(self.speed_var.get(), "Speed", 0.25, 4)
            if abs(factor - 1) < 0.01:
                raise ValueError("Speed 1 would change nothing.")
            return job(files, output, change_speed, hooks=True, factor=factor)

        if action == "Rotate or flip":
            degrees = ROTATIONS[self.rotate_var.get()]
            if not degrees and not self.flip_h.get() and not self.flip_v.get():
                raise ValueError("Pick a rotation or tick a flip.")
            return job(files, output, rotate_video, hooks=True, degrees=degrees,
                       flip_h=self.flip_h.get(), flip_v=self.flip_v.get())

        if action == "Crop to shape":
            aspect = ASPECT_RATIOS[self.crop_aspect.get()]
            if aspect is None:
                raise ValueError("Pick an aspect other than Original.")
            return job(files, output, crop_video, hooks=True,
                       aspect=aspect, mode=CROP_MODES[self.crop_mode.get()])

        if action == "Replace audio":
            audio = self.new_audio.get().strip()
            if not audio or not Path(audio).exists():
                raise ValueError("Choose an audio file first.")
            mix = self.mix_audio.get()
            return job(files, output, lambda v, out, **kw: replace_audio(
                v, audio, out, mix=mix, **kw
            ), hooks=True)

        if action == "Remove sound":
            return job(files, output, remove_audio, hooks=True)

        if action == "Save a picture":
            to_seconds(self.shot_time.get())
            return job(files, output, screenshot, hooks=True,
                       at=self.shot_time.get().strip(),
                       fmt="." + self.picture_format.get())

        every = read_float(self.every_var.get(), "Seconds between pictures", 0.1, 3600)
        return job(files, output, extract_frames, hooks=True, every=every,
                   fmt="." + self.picture_format.get())

    def done_message(self, result):
        if self.job_action == "Merge":
            return f"Done. Saved {Path(result.done[0]).name}"
        return super().done_message(result)