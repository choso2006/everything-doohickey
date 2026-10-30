import customtkinter as ctk

from core.audio import (
    AUDIO_ALLOWED, AUDIO_FORMATS, change_speed_audio, change_volume,
    convert_audio, fade_audio, merge_audio, trim_audio, trim_silence,
)
from core.common import clean_name, to_seconds
from core.tools import HINTS, find_tool
from ui import theme
from ui.toolpage import ToolPage
from ui.widgets import (
    checkbox, entry, note, option_menu, read_float, setting_row, slider_row,
)

ACTIONS = ["Convert", "Trim", "Merge", "Change volume", "Change speed",
           "Fade in/out", "Trim silence"]
BITRATES = {
    "Small (96 kbps)": 96,
    "Normal (128 kbps)": 128,
    "High (192 kbps)": 192,
    "Best (320 kbps)": 320,
}
SPEEDS = ["0.5", "0.75", "1.25", "1.5", "2", "3"]


class AudioPage(ToolPage):
    ACTIONS = ACTIONS

    ACTION_DESCRIPTIONS = {
        "Convert": {
            "desc": "Convert audio files to modern, compatible formats.",
            "ex": "WAV ➔ MP3, M4A ➔ OGG, FLAC ➔ AAC",
            "icon": "🔁",
        },
        "Trim": {
            "desc": "Cut out specific sections of an audio track.",
            "ex": "Keep only 0:30 to 1:15 of a podcast",
            "icon": "✂️",
        },
        "Merge": {
            "desc": "Join multiple audio files into one continuous track.",
            "ex": "Combine several tracks into a single album file",
            "icon": "🔗",
        },
        "Change volume": {
            "desc": "Boost, lower, or normalize the volume of audio files.",
            "ex": "Increase volume by +6 dB, or normalize loudness for streaming",
            "icon": "🔊",
        },
        "Change speed": {
            "desc": "Speed up or slow down audio without pitch shift.",
            "ex": "Listen to a podcast at 1.5x speed",
            "icon": "⏩",
        },
        "Fade in/out": {
            "desc": "Add smooth professional fades to the start or end.",
            "ex": "Add a 2-second fade-out to the end of a song",
            "icon": "🌅",
        },
        "Trim silence": {
            "desc": "Remove dead air and background noise automatically.",
            "ex": "Cut the silence before a singer starts, or the gap after",
            "icon": "🔇",
        },
    }

    def __init__(self, parent, state=None):
        super().__init__(
            parent, "Audio",
            "Convert, trim, join and adjust music and recordings.", state,
        )
        R = self.remember
        self.format_var = R("format", ctk.StringVar(value="mp3"))
        self.bitrate_var = R("bitrate", ctk.StringVar(value="High (192 kbps)"))
        self.start_var = ctk.StringVar(value="0:00")
        self.end_var = ctk.StringVar(value="0:30")
        self.merge_name = R("merge_name", ctk.StringVar(value="merged"))
        self.db_var = R("db", ctk.DoubleVar(value=6))
        self.normalize_var = R("normalize", ctk.BooleanVar(value=False))
        self.speed_var = R("speed", ctk.StringVar(value="1.25"))
        self.fade_in = R("fade_in", ctk.StringVar(value="0.0"))
        self.fade_out = R("fade_out", ctk.StringVar(value="2.0"))
        self.silence_db = R("silence_db", ctk.DoubleVar(value=-40))
        self.silence_min = R("silence_min", ctk.DoubleVar(value=0.5))

        self.build()

    def current_extensions(self):
        return AUDIO_ALLOWED

    def is_ordered(self):
        return self.action_var.get() == "Merge"

    def build_settings(self):
        for child in self.settings.winfo_children():
            child.destroy()

        action = self.action_var.get()
        box = self.settings

        def menu_row(text, values, variable, width=None, command=None):
            row = setting_row(box, text)
            kwargs = {"width": width} if width else {}
            menu = option_menu(row, values, variable, command=command, **kwargs)
            menu.pack(side="left", **({} if width else {"fill": "x", "expand": True}))

        if action == "Convert":
            menu_row("Format", AUDIO_FORMATS, self.format_var, width=120)
            menu_row("Quality", list(BITRATES), self.bitrate_var)
            note(box, "Quality only matters for the small formats (MP3, M4A, "
                      "AAC, OGG, Opus). FLAC is lossless, and WAV and AIFF "
                      "are uncompressed and big. Cover art is left out.")

        elif action == "Trim":
            row = setting_row(box, "Start")
            entry(row, self.start_var, width=120).pack(side="left")
            row = setting_row(box, "End")
            entry(row, self.end_var, width=120).pack(side="left")
            note(box, "Times look like 45, 1:30 or 1:02:03.5. This works on "
                      "one file at a time. The cut is instant and loses no "
                      "quality. Press Play in the preview to find the right "
                      "moments first.")

        elif action == "Merge":
            row = setting_row(box, "Name")
            entry(row, self.merge_name).pack(side="left", fill="x", expand=True)
            menu_row("Format", AUDIO_FORMATS, self.format_var, width=120)
            menu_row("Quality", list(BITRATES), self.bitrate_var)
            note(box, "Joins the files in the order shown on the left, even if "
                      "they're different formats. Use the arrows to reorder.")

        elif action == "Change volume":
            checkbox(box, "Even out the loudness (normalize)",
                     self.normalize_var, command=self.rebuild_soon).pack(anchor="w")
            if not self.normalize_var.get():
                slider_row(box, "Change", self.db_var, -20, 20, " dB")
            note(box, "Normalize brings quiet and loud files to a similar "
                      "level. Otherwise each +6 dB roughly doubles the "
                      "loudness and each -6 dB halves it. Louder than the "
                      "original can distort. Files keep their own format, "
                      "and formats that can't be written become MP3.")

        elif action == "Fade in/out":
            row = setting_row(box, "Fade in")
            entry(row, self.fade_in, width=90).pack(side="left")
            ctk.CTkLabel(row, text="seconds", text_color=theme.MUTED,
                         font=theme.font(13)).pack(side="left", padx=6)
            row = setting_row(box, "Fade out")
            entry(row, self.fade_out, width=90).pack(side="left")
            ctk.CTkLabel(row, text="seconds", text_color=theme.MUTED,
                         font=theme.font(13)).pack(side="left", padx=6)
            note(box, "0 means no fade on that end. Fade out is measured from "
                      "the end of the file. Files keep their own format, "
                      "and formats that can't be written become MP3.")

        elif action == "Trim silence":
            slider_row(box, "Threshold", self.silence_db, -70, -20, " dB")
            slider_row(box, "Min length", self.silence_min, 0.1, 5, " s")
            note(box, "Removes silence from the start and the end of the "
                      "file. A threshold of -40 dB catches most background "
                      "hiss. Minimum length is how long the silence has to "
                      "last before it's cut. Middle silences are kept.")

        else:
            menu_row("Speed", SPEEDS, self.speed_var, width=120)
            note(box, "1.5 plays 50% faster, 0.5 plays at half speed. The "
                      "pitch stays the same, so voices don't sound like "
                      "chipmunks.")

    def make_job(self, files, output):
        if find_tool("ffmpeg") is None or find_tool("ffprobe") is None:
            raise ValueError(HINTS["ffmpeg"])

        action = self.action_var.get()
        kbps = BITRATES[self.bitrate_var.get()]

        if action == "Convert":
            return self.batch_job(
                files, output, convert_audio, hooks=True,
                fmt=self.format_var.get(), kbps=kbps,
            )

        if action == "Trim":
            if len(files) != 1:
                raise ValueError("Trim works on one file at a time. Remove the others from the list.")
            start, end = self.start_var.get().strip(), self.end_var.get().strip()
            if to_seconds(end) <= to_seconds(start):
                raise ValueError("The end time has to be after the start time.")
            return self.batch_job(
                files, output, trim_audio, hooks=True, start=start, end=end
            )

        if action == "Merge":
            if len(files) < 2:
                raise ValueError("Merging needs at least 2 files.")
            name = clean_name(self.merge_name.get(), "merged", AUDIO_ALLOWED)
            fmt = self.format_var.get()
            return self.tracked_job(
                f"Joining {len(files)} files...",
                lambda progress, cancel: merge_audio(
                    files, output, name, fmt, kbps, progress=progress, cancel=cancel
                ),
            )

        if action == "Change volume":
            if self.normalize_var.get():
                return self.batch_job(
                    files, output, change_volume, hooks=True,
                    normalize=True, kbps=kbps,
                )
            db = round(self.db_var.get())
            if db == 0:
                raise ValueError("0 dB would change nothing. Move the slider.")
            return self.batch_job(
                files, output, change_volume, hooks=True, db=float(db), kbps=kbps
            )

        if action == "Fade in/out":
            fi = read_float(self.fade_in.get() or "0", "Fade in", 0, 600)
            fo = read_float(self.fade_out.get() or "0", "Fade out", 0, 600)
            if fi <= 0 and fo <= 0:
                raise ValueError("Give at least one fade length.")
            return self.batch_job(
                files, output, fade_audio, hooks=True,
                fade_in=fi, fade_out=fo, kbps=kbps,
            )

        if action == "Trim silence":
            return self.batch_job(
                files, output, trim_silence, hooks=True,
                threshold_db=float(self.silence_db.get()),
                min_silence=float(self.silence_min.get()),
                kbps=kbps,
            )

        factor = read_float(self.speed_var.get(), "Speed", 0.25, 4)
        return self.batch_job(
            files, output, change_speed_audio, hooks=True, factor=factor, kbps=kbps
        )

    def done_message(self, result):
        if self.job_action == "Merge":
            return f"Done. Saved {result.done[0].name}"
        return super().done_message(result)