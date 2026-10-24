import time
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
import tempfile
import datetime

import customtkinter as ctk
from PIL import Image, ImageGrab

from core.appdata import data_dir, log_exception, open_path, load_config, save_config
from core.batch import BatchResult, list_files, run_batch
from core.common import Cancelled, format_size, format_time
from core.sounds import play
from ui import theme
from ui.preview import PreviewPanel
from ui.runner import JobRunner
from ui.widgets import (
    Page, card, label, option_menu, primary_button, secondary_button,
    shorten, small_button, SquaredScrollableFrame, ToastNotification,
    SquaredInputDialog
)


class ToolPage(Page):
    ACTIONS = []
    PREVIEW_PREFER = "image"
    SORT_MODES = ["Added", "Name", "Size", "Date"]
    MAX_PRESETS = 8

    BUILTIN_PRESETS = {
        "ImagesPage": {
            "WebP (Web Ready)": {"action": "Convert", "format": "webp", "quality": 80},
            "JPG (1080px Width)": {"action": "Convert", "format": "jpg", "quality": 90, "resize_mode": "Width", "width": "1080"},
            "Compress to 200KB": {"action": "Compress to size", "size_value": "200", "size_unit": "KB"},
        },
        "VideoPage": {
            "Discord (10MB)": {"action": "Compress to size", "target_mb": "10"},
            "1080p MP4": {"action": "Convert", "format": "mp4", "quality": "High quality"},
            "TikTok (9:16)": {"action": "Crop to shape", "crop_aspect": "9:16 portrait", "crop_mode": "Fill (crop edges)"},
        },
        "AudioPage": {
            "MP3 (320kbps)": {"action": "Convert", "format": "mp3", "bitrate": "Best (320 kbps)"},
            "Trim Silence": {"action": "Trim silence", "silence_db": -40, "silence_min": 0.5},
        },
        "PdfsPage": {
            "Compress to 5MB": {"action": "Compress to size", "target_mb": "5"},
            "Lock with Password": {"action": "Lock"},
            "Compress (Strong)": {"action": "Compress", "level": "Strong"},
        }
    }

    def __init__(self, parent, title, subtitle, state=None):
        super().__init__(parent, title, subtitle)

        self.state = state or {}
        self.vars = {}
        self.files = []
        self.row_widgets = {}
        self.selected = None
        self.rows_ordered = False
        self.cancellable = False
        self.report_savings = False
        self.job_action = ""
        self.last_output = None
        self.on_save = None
        self._started_at = 0.0

        self._undo_job = None
        self._undo_data = None
        self.recent_folders = list(self.state.get("recent_folders", []))

        self.output_folder = None
        saved_output = self.state.get("output")
        if saved_output and Path(saved_output).is_dir():
            self.output_folder = Path(saved_output)

        self.presets = list(self.state.get("folder_presets", []))

        self.action_var = ctk.StringVar(value=self.ACTIONS[0])
        saved_action = self.state.get("action")
        if saved_action in self.ACTIONS:
            self.action_var.set(saved_action)

        self.sort_var = ctk.StringVar(value=self.state.get("sort", "Added"))
        self.filter_var = ctk.StringVar(value="")
        self.same_folder_var = ctk.BooleanVar(value=self.state.get("same_folder", False))

        self.preset_var = ctk.StringVar(value="Select Preset...")

        self.runner = JobRunner(self, self.on_file, self.on_progress, self.on_finished)

    def build_settings(self):
        raise NotImplementedError

    def make_job(self, files, output):
        raise NotImplementedError

    def current_extensions(self):
        raise NotImplementedError

    def is_ordered(self):
        return False

    def done_message(self, result):
        count = len(result.done)
        config = load_config()
        custom = config.get("custom_message", "Done! {count} files converted.")

        try:
            text = custom.replace("{count}", str(count))
        except Exception:
            text = f"Done! {count} files converted."

        if self.report_savings and result.sources:
            try:
                before = sum(Path(s).stat().st_size for s in result.sources)
                after = sum(Path(d).stat().st_size for d in result.done)
                if before > 0 and after < before:
                    saved = before - after
                    text += (f" Saved {format_size(saved)} "
                             f"({round(100 * saved / before)}%).")
                elif before > 0:
                    text += " No size change."
            except (OSError, TypeError):
                pass
        return text

    def remember(self, name, variable):
        self.vars[name] = variable
        if name in self.state:
            try:
                variable.set(self.state[name])
            except Exception:
                pass
        return variable

    def get_state(self):
        saved = {
            "action": self.action_var.get(),
            "same_folder": self.same_folder_var.get()
        }
        if self.output_folder:
            saved["output"] = str(self.output_folder)
        if self.presets:
            saved["folder_presets"] = list(self.presets)
        if self.recent_folders:
            saved["recent_folders"] = list(self.recent_folders)
        if self.sort_var.get() != "Added":
            saved["sort"] = self.sort_var.get()
        for name, variable in self.vars.items():
            try:
                saved[name] = variable.get()
            except Exception:
                pass
        return saved

    # ---------- SETTINGS PRESETS ----------
    def get_all_presets(self):
        builtins = self.BUILTIN_PRESETS.get(self.__class__.__name__, {})
        config = load_config()
        saved = config.get("saved_presets", {}).get(self.__class__.__name__, {})

        merged = dict(builtins)
        merged.update(saved)
        return merged

    def apply_preset(self, choice):
        if not choice or choice == "Select Preset...":
            return

        presets = self.get_all_presets()
        if choice not in presets:
            return

        preset = presets[choice]

        if "action" in preset:
            self.action_var.set(preset["action"])
            self.action_menu.set(preset["action"])

        for key, value in preset.items():
            if key == "action":
                continue
            if key in self.vars:
                try:
                    self.vars[key].set(value)
                except Exception:
                    pass

        self.build_settings()
        if self.rows_ordered != self.is_ordered():
            self.render_rows()
        # Keep the dropdown on this preset so Delete knows what to target.

    def prompt_save_preset(self):
        dialog = SquaredInputDialog(self, "Save Preset", "Name this preset:")
        name = dialog.get_input()
        if not name:
            return

        name = name.strip()
        if not name:
            return
        current_state = self.get_state()

        config = load_config()
        if "saved_presets" not in config:
            config["saved_presets"] = {}
        if self.__class__.__name__ not in config["saved_presets"]:
            config["saved_presets"][self.__class__.__name__] = {}

        config["saved_presets"][self.__class__.__name__][name] = current_state
        save_config(config)

        self.set_status(f"Saved preset: {name}")

        # Refresh the list, then select the newly-saved preset without firing apply_preset
        presets = list(self.get_all_presets().keys())
        self.preset_menu.configure(values=["Select Preset..."] + presets, command=None)
        self.preset_var.set(name)
        self.preset_menu.set(name)
        self.preset_menu.configure(command=self.apply_preset)

    def delete_preset(self):
        current = self.preset_var.get()
        if not current or current == "Select Preset...":
            self.set_status("Select a preset first.", error=True)
            return

        config = load_config()
        saved = config.get("saved_presets", {}).get(self.__class__.__name__, {})

        if current in saved:
            del saved[current]
            save_config(config)
            self.set_status(f"Deleted preset: {current}")
            self.refresh_preset_menu()
        else:
            self.set_status("Cannot delete built-in preset.", error=True)

    def refresh_preset_menu(self):
        presets = list(self.get_all_presets().keys())
        self.preset_menu.configure(values=["Select Preset..."] + presets)
        self.preset_var.set("Select Preset...")
        self.preset_menu.set("Select Preset...")
    # ---------------------------------------

    def batch_job(self, files, output, action, hooks=False, **options):
        def job(on_file, on_progress, should_cancel):
            if self.same_folder_var.get():
                def wrapper(file, out_dir, **kw):
                    return action(file, file.parent, **kw)
                actual_action = wrapper
            else:
                actual_action = action

            return run_batch(
                files, output, actual_action,
                on_file=on_file, on_progress=on_progress,
                should_cancel=should_cancel, wants_hooks=hooks, **options,
            )
        return job, True

    def single_job(self, message, work):
        def job(on_file, on_progress, should_cancel):
            on_file(0, 0, message)
            return BatchResult(done=[work()])
        return job, False

    def tracked_job(self, message, work):
        def job(on_file, on_progress, should_cancel):
            on_file(0, 0, message)
            try:
                path = work(on_progress, should_cancel)
            except Cancelled:
                return BatchResult(cancelled=True)
            return BatchResult(done=[path])
        return job, True

    def paste_from_clipboard(self):
        if self.runner.running:
            return

        try:
            clipboard = ImageGrab.grabclipboard()
            if clipboard is None:
                return

            if isinstance(clipboard, Image.Image):
                temp_dir = Path(tempfile.gettempdir()) / "Convertor_Paste"
                temp_dir.mkdir(parents=True, exist_ok=True)
                filename = f"pasted_{int(time.time())}.png"
                path = temp_dir / filename
                clipboard.save(path)
                self.add_files([path])
                self.set_status("Pasted image.")

            elif isinstance(clipboard, list):
                paths = [Path(p) for p in clipboard]
                self.add_files(paths)
                self.set_status(f"Pasted {len(paths)} files.")

        except Exception as e:
            self.set_status(f"Paste failed: {e}", error=True)

    def build(self):
        bottom = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        bottom.pack(side="bottom", fill="x", padx=32, pady=(0, 20))

        status_row = ctk.CTkFrame(bottom, fg_color="transparent", corner_radius=0)
        status_row.pack(fill="x")

        self.status = label(status_row, "Ready", 13, color=theme.MUTED,
                            wraplength=660, justify="left")
        self.status.pack(side="left", fill="x", expand=True)

        self.undo_btn = secondary_button(status_row, "Undo", self._undo_remove, width=70)

        progress_row = ctk.CTkFrame(bottom, fg_color="transparent", corner_radius=0)
        progress_row.pack(fill="x", pady=(8, 12))
        self.progress = ctk.CTkProgressBar(
            progress_row, height=8, corner_radius=0,
            fg_color=theme.BORDER, progress_color=theme.ACCENT,
        )
        self.progress.pack(side="left", fill="x", expand=True)
        self.progress.set(0)
        self.eta_label = label(progress_row, "", 12, color=theme.MUTED, width=90)
        self.eta_label.pack(side="left", padx=(10, 0))

        buttons = ctk.CTkFrame(bottom, fg_color="transparent", corner_radius=0)
        buttons.pack(fill="x")
        self.start_btn = primary_button(buttons, "Start", self.start)
        self.start_btn.pack(side="right")
        self.cancel_btn = secondary_button(buttons, "Cancel", self.cancel)
        self.cancel_btn.pack(side="right", padx=8)
        self.cancel_btn.configure(state="disabled")

        body = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        body.pack(fill="both", expand=True, padx=32, pady=(14, 12))
        body.grid_columnconfigure(0, weight=3, uniform="cols")
        body.grid_columnconfigure(1, weight=2, uniform="cols")
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color="transparent", corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.preview = PreviewPanel(left, prefer=self.PREVIEW_PREFER)
        self.preview.pack(side="bottom", fill="x", pady=(10, 0))

        files_card = card(left)
        files_card.pack(side="top", fill="both", expand=True)

        top = ctk.CTkFrame(files_card, fg_color="transparent", corner_radius=0)
        top.pack(fill="x", padx=16, pady=(12, 4))
        label(top, "Files", 15, "bold").pack(side="left")
        self.count_label = label(top, "", 12, color=theme.MUTED)
        self.count_label.pack(side="right")

        tools = ctk.CTkFrame(files_card, fg_color="transparent", corner_radius=0)
        tools.pack(fill="x", padx=16, pady=(0, 8))

        self.filter_entry = ctk.CTkEntry(
            tools, textvariable=self.filter_var, height=30, corner_radius=0,
            font=theme.font(12), fg_color=theme.BG,
            border_color=theme.BORDER, text_color=theme.TEXT,
            placeholder_text="Filter...",
        )
        self.filter_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.sort_menu = option_menu(tools, self.SORT_MODES, self.sort_var,
                                     command=lambda *_: self.render_rows(), width=110)
        self.sort_menu.pack(side="left")
        self.filter_var.trace_add("write", lambda *_: self.render_rows())

        file_buttons = ctk.CTkFrame(files_card, fg_color="transparent", corner_radius=0)
        file_buttons.pack(side="bottom", fill="x", padx=16, pady=12)

        self.add_files_btn = secondary_button(file_buttons, "Add", self.pick_files)
        self.add_files_btn.pack(side="left")

        self.add_folder_btn = secondary_button(file_buttons, "Folder", self.pick_folder)
        self.add_folder_btn.pack(side="left", padx=8)

        self.clear_btn = secondary_button(file_buttons, "Clear", self.clear_files, width=80)
        self.clear_btn.pack(side="right")

        self.file_list = SquaredScrollableFrame(
            files_card, fg_color=theme.BG,
            scrollbar_button_color=theme.BORDER,
            scrollbar_button_hover_color=theme.MUTED,
        )
        self.file_list.pack(side="top", fill="both", expand=True, padx=16, pady=(0, 8))

        self.empty_frame = ctk.CTkFrame(self.file_list, fg_color="transparent", corner_radius=0)
        empty_icon = ctk.CTkLabel(self.empty_frame, text="📂", font=theme.font(48), text_color=theme.BORDER, corner_radius=0)
        empty_icon.pack(pady=(30, 10))
        empty_title = label(self.empty_frame, "No files", 16, "bold")
        empty_title.pack()
        empty_desc = label(self.empty_frame, "Drag files here or press Ctrl+V.", 13, color=theme.MUTED, justify="center")
        empty_desc.pack(pady=(4, 16))
        primary_button(self.empty_frame, "Browse", self.pick_files, width=120).pack(pady=(0, 30))

        self._empty_widgets = (empty_icon, empty_title, empty_desc)
        for w in self._empty_widgets:
            w.bind("<Button-1>", lambda e: self.pick_files())

        right = SquaredScrollableFrame(
            body, fg_color=theme.PANEL,
            scrollbar_button_color=theme.BORDER,
            scrollbar_button_hover_color=theme.MUTED,
        )
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        label(right, "Action", 15, "bold").pack(fill="x", padx=16, pady=(8, 8))
        self.action_menu = option_menu(
            right, self.ACTIONS, self.action_var, command=self.action_changed
        )
        self.action_menu.pack(fill="x", padx=16)

        # ---- PRESETS UI ----
        label(right, "Presets", 15, "bold").pack(fill="x", padx=16, pady=(18, 4))
        preset_row = ctk.CTkFrame(right, fg_color="transparent", corner_radius=0)
        preset_row.pack(fill="x", padx=16, pady=0)

        self.preset_menu = option_menu(preset_row, ["Select Preset..."], self.preset_var, command=self.apply_preset)
        self.preset_menu.pack(side="left", fill="x", expand=True)

        self.save_preset_btn = secondary_button(preset_row, "Save", self.prompt_save_preset, width=60)
        self.save_preset_btn.pack(side="right", padx=(8, 0))

        self.delete_preset_btn = secondary_button(preset_row, "Del", self.delete_preset, width=50)
        self.delete_preset_btn.pack(side="right", padx=(4, 0))

        self.refresh_preset_menu()
        # --------------------

        self.settings = ctk.CTkFrame(right, fg_color="transparent", corner_radius=0)
        self.settings.pack(fill="x", padx=16, pady=(14, 0))

        label(right, "Save to", 15, "bold").pack(fill="x", padx=16, pady=(18, 8))

        self.output_label = label(right, "", 12, color=theme.MUTED)
        self.output_label.pack(fill="x", padx=16)

        self.same_folder_chk = ctk.CTkCheckBox(
            right, text="Same folder as original", variable=self.same_folder_var,
            font=theme.font(12), text_color=theme.MUTED,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            checkbox_width=16, checkbox_height=16, corner_radius=0, command=self.refresh_output_label
        )
        self.same_folder_chk.pack(fill="x", padx=16, pady=(4, 8))

        output_buttons = ctk.CTkFrame(right, fg_color="transparent", corner_radius=0)
        output_buttons.pack(fill="x", padx=16, pady=(0, 14))

        self.output_btn = secondary_button(
            output_buttons, "Choose", self.pick_output, width=100
        )
        self.output_btn.pack(side="left")

        self.recent_btn = secondary_button(
            output_buttons, "Recent", self.show_recent_menu, width=80
        )
        self.recent_btn.pack(side="left", padx=8)

        self.presets_btn = secondary_button(
            output_buttons, "Saved", self.show_presets_menu, width=80
        )
        self.presets_btn.pack(side="left")

        self.open_btn = secondary_button(
            output_buttons, "Open", self.open_output, width=70
        )
        self.open_btn.pack(side="left", padx=8)
        self.open_btn.configure(state="disabled")

        self.rows_ordered = self.is_ordered()
        self.build_settings()
        self.update_files_view()
        self.refresh_output_label()
        self.after(200, self.enable_drop)

    def rebuild_soon(self, *_):
        self.after(20, self.build_settings)

    def action_changed(self, _value=None):
        self.build_settings()
        if self.rows_ordered != self.is_ordered():
            self.render_rows()

        allowed = self.current_extensions()
        wrong = [f for f in self.files if allowed and f.suffix.lower() not in allowed]
        if wrong:
            self.set_status(
                f"{len(wrong)} files don't fit this action. Remove them or change action.",
                error=True,
            )

    def enable_drop(self):
        window = self.winfo_toplevel()
        if not getattr(window, "dnd_ready", False):
            return
        try:
            from tkinterdnd2 import DND_FILES
            widgets = [self.file_list, self.empty_frame, self.preview, *self._empty_widgets]
            for widget in widgets:
                try:
                    widget.drop_target_register(DND_FILES)
                    widget.dnd_bind("<<Drop>>", self.on_drop)
                except Exception:
                    pass
        except Exception:
            log_exception("drag and drop setup")

    def on_drop(self, event):
        if self.runner.running:
            return
        try:
            paths = [Path(p) for p in self.tk.splitlist(event.data)]
        except Exception:
            return
        expanded = []
        allowed = self.current_extensions()
        for path in paths:
            if path.is_dir():
                expanded.extend(list_files(path, allowed))
            else:
                expanded.append(path)
        self.add_files(expanded)

    def pick_files(self):
        patterns = tuple(f"*{ext}" for ext in self.current_extensions())
        filetypes = [("Supported", patterns), ("All", "*.*")] if patterns else [("All", "*.*")]
        paths = filedialog.askopenfilenames(
            title="Choose files",
            filetypes=filetypes,
        )
        self.add_files(paths)

    def pick_folder(self):
        folder = filedialog.askdirectory(title="Choose a folder")
        if not folder:
            return
        try:
            found = list_files(folder, self.current_extensions())
        except FileNotFoundError as e:
            self.set_status(str(e), error=True)
            return
        if not found:
            self.set_status("No supported files found.", error=True)
            return
        self.add_files(found)

    def visible_files(self):
        files = list(self.files)
        query = self.filter_var.get().strip().lower()
        if query:
            files = [f for f in files if query in f.name.lower()]
        if not self.is_ordered():
            key = self.sort_var.get()
            try:
                if key == "Name":
                    files.sort(key=lambda f: f.name.lower())
                elif key == "Size":
                    files.sort(key=lambda f: f.stat().st_size)
                elif key == "Date":
                    files.sort(key=lambda f: f.stat().st_mtime)
            except OSError:
                pass
        return files

    def add_files(self, paths):
        allowed = self.current_extensions()
        added, skipped, first_new = 0, 0, None
        for p in paths:
            path = Path(p)
            if allowed and path.suffix.lower() not in allowed:
                skipped += 1
                continue
            if path in self.files:
                continue
            self.files.append(path)
            first_new = first_new or path
            added += 1

        if added:
            self.render_rows()
            self._hide_undo()
        self.update_files_view()
        if self.selected is None and first_new is not None:
            self.select(first_new)
        if skipped:
            self.set_status(f"Added {added}, skipped {skipped} unsupported.", error=not added)
        elif added:
            self.set_status(f"Added {added} files.")

    def make_row(self, path, number):
        row = ctk.CTkFrame(self.file_list, fg_color="transparent", corner_radius=0)
        row.pack(fill="x", pady=1)

        small_button(row, "\u00d7", lambda p=path: self.remove_file(p)).pack(
            side="right", padx=(0, 4)
        )
        if self.is_ordered():
            for symbol, step in (("\u2193", 1), ("\u2191", -1)):
                small_button(
                    row, symbol, lambda p=path, s=step: self.move_file(p, s)
                ).pack(side="right")

        try:
            size_text = format_size(path.stat().st_size)
        except OSError:
            size_text = "?? KB"

        text = shorten(path.name, 35)
        if self.is_ordered():
            text = f"{number}. {text}"
        name = label(row, text, 13)
        name.pack(side="left", fill="x", expand=True, padx=(8, 0))

        size_label = label(row, size_text, 11, color=theme.MUTED)
        size_label.pack(side="right", padx=(0, 8))

        def on_enter(e):
            if path != self.selected:
                row.configure(fg_color=theme.HOVER)
        def on_leave(e):
            if path != self.selected:
                row.configure(fg_color="transparent")

        for widget in (row, name, size_label):
            widget.bind("<Button-1>", lambda _e, p=path: self.select(p))
            widget.bind("<Button-3>", lambda e, p=path: self._show_context_menu(e, p))
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)

        if path == self.selected:
            row.configure(fg_color=theme.SELECT)
        return row

    def _show_context_menu(self, event, path):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Open", command=lambda: self._open_file(path))
        menu.add_command(label="Show in Folder", command=lambda: self._show_in_explorer(path))
        menu.add_separator()
        menu.add_command(label="Copy Path", command=lambda: self._copy_path(path))
        menu.add_command(label="Remove", command=lambda: self.remove_file(path))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _open_file(self, path):
        try:
            open_path(path)
        except Exception as e:
            self.set_status(f"Could not open: {e}", error=True)

    def _show_in_explorer(self, path):
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", "-R", str(path)], check=False)
            elif os.name == "nt":
                subprocess.run(["explorer", "/select,", str(path)], check=False)
            else:
                open_path(path.parent)
        except Exception as e:
            self.set_status(f"Could not open folder: {e}", error=True)

    def _copy_path(self, path):
        self.clipboard_clear()
        self.clipboard_append(str(path))
        self.set_status("Path copied.")

    def select(self, path):
        if path is not None and path not in self.row_widgets:
            return
        self.selected = path
        for other, row in self.row_widgets.items():
            row.configure(fg_color=theme.SELECT if other == path else "transparent")
        self.preview.show(path)

    def render_rows(self):
        for row in self.row_widgets.values():
            try:
                row.destroy()
            except Exception:
                pass
        self.row_widgets.clear()
        self.rows_ordered = self.is_ordered()
        for number, path in enumerate(self.visible_files(), start=1):
            self.row_widgets[path] = self.make_row(path, number)

    def move_file(self, path, step):
        if self.runner.running or path not in self.files:
            return
        i = self.files.index(path)
        j = i + step
        if 0 <= j < len(self.files):
            self.files[i], self.files[j] = self.files[j], self.files[i]
            self.render_rows()

    def remove_file(self, path):
        if self.runner.running or path not in self.files:
            return

        index = self.files.index(path)
        self.files.remove(path)

        self._undo_data = (path, index)
        self._undo_job = self.after(5000, self._hide_undo)
        self.undo_btn.pack(side="left", padx=(10, 0))

        if path in self.row_widgets:
            self.row_widgets.pop(path).destroy()
        self.update_files_view()

        if path == self.selected:
            self.selected = None
            if self.files:
                self.select(self.files[min(index, len(self.files) - 1)])
            else:
                self.preview.show(None)

    def _undo_remove(self):
        if not self._undo_data:
            return
        path, index = self._undo_data
        self._undo_data = None
        self._hide_undo()

        if path not in self.files:
            index = min(index, len(self.files))
            self.files.insert(index, path)
            self.render_rows()
            self.update_files_view()
            self.select(path)
            self.set_status("Restored.")

    def _hide_undo(self):
        self.undo_btn.pack_forget()
        if self._undo_job:
            try:
                self.after_cancel(self._undo_job)
            except Exception:
                pass
            self._undo_job = None

    def remove_selected(self):
        if self.selected is not None:
            self.remove_file(self.selected)

    def clear_files(self):
        if self.runner.running:
            return
        self._undo_data = None
        self._hide_undo()
        for row in self.row_widgets.values():
            try:
                row.destroy()
            except Exception:
                pass
        self.row_widgets.clear()
        self.files.clear()
        self.selected = None
        self.preview.show(None)
        self.update_files_view()

    def update_files_view(self):
        count = len(self.files)
        hidden = count - len(self.row_widgets)
        text = "1 file" if count == 1 else f"{count} files"
        if hidden > 0:
            text += f" ({hidden} hidden)"
        self.count_label.configure(text=text)

        if count:
            self.empty_frame.pack_forget()
        else:
            self.empty_frame.pack(fill="both", expand=True)

    def pick_output(self):
        folder = filedialog.askdirectory(title="Save to...")
        if not folder:
            return
        self._set_output(Path(folder))

    def _set_output(self, folder):
        self.output_folder = folder
        self._remember_preset(str(folder))

        folder_str = str(folder)
        if folder_str in self.recent_folders:
            self.recent_folders.remove(folder_str)
        self.recent_folders.insert(0, folder_str)
        del self.recent_folders[5:]

        self.refresh_output_label()

    def _remember_preset(self, folder):
        if folder in self.presets:
            self.presets.remove(folder)
        self.presets.insert(0, folder)
        del self.presets[self.MAX_PRESETS:]
        if self.on_save:
            self.on_save()

    def show_presets_menu(self):
        menu = tk.Menu(self, tearoff=0)
        if not self.presets:
            menu.add_command(label="(None saved)", state="disabled")
        for preset in self.presets:
            menu.add_command(
                label=shorten(preset, 56),
                command=lambda p=preset: self.apply_folder_preset(p),
            )
        if self.presets:
            menu.add_separator()
            menu.add_command(label="Remove all", command=self._clear_presets)
        try:
            menu.tk_popup(
                self.presets_btn.winfo_rootx(),
                self.presets_btn.winfo_rooty() + self.presets_btn.winfo_height(),
            )
        finally:
            menu.grab_release()

    def show_recent_menu(self):
        menu = tk.Menu(self, tearoff=0)
        if not self.recent_folders:
            menu.add_command(label="(None yet)", state="disabled")
        for folder in self.recent_folders:
            menu.add_command(
                label=shorten(folder, 56),
                command=lambda p=folder: self.apply_folder_preset(p),
            )
        try:
            menu.tk_popup(
                self.recent_btn.winfo_rootx(),
                self.recent_btn.winfo_rooty() + self.recent_btn.winfo_height(),
            )
        finally:
            menu.grab_release()

    def apply_folder_preset(self, folder):
        if Path(folder).is_dir():
            self._set_output(Path(folder))
        else:
            self.set_status("Folder gone.", error=True)

    def _clear_presets(self):
        self.presets.clear()
        if self.on_save:
            self.on_save()

    def refresh_output_label(self):
        if self.same_folder_var.get():
            text = "Saving next to original"
            self.output_label.configure(text=text, text_color=theme.ACCENT)
            self.output_btn.configure(state="disabled")
            self.recent_btn.configure(state="disabled")
            self.presets_btn.configure(state="disabled")
        else:
            if self.output_folder:
                text = shorten(str(self.output_folder), 56)
            else:
                text = "Automatic: next to original file"
            self.output_label.configure(text=text, text_color=theme.MUTED)
            self.output_btn.configure(state="normal")
            self.recent_btn.configure(state="normal")
            self.presets_btn.configure(state="normal")

    def open_output(self):
        if self.last_output and Path(self.last_output).exists():
            open_path(self.last_output)

    def start(self):
        if self.runner.running:
            return

        files = list(self.files)
        if not files:
            self.set_status("Add some files first.", error=True)
            return

        allowed = self.current_extensions()
        wrong = [f.name for f in files if allowed and f.suffix.lower() not in allowed]
        if wrong:
            shown = ", ".join(wrong[:3])
            more = f" (+{len(wrong) - 3})" if len(wrong) > 3 else ""
            self.set_status(
                f"Wrong file type: {shown}{more}. Remove them first.", error=True,
            )
            return

        if self.same_folder_var.get():
            output = files[0].parent
        else:
            temp_dir = Path(tempfile.gettempdir()) / "Convertor_Paste"
            if files[0].parent == temp_dir:
                output = self.output_folder or Path.home() / "Downloads"
            else:
                output = self.output_folder or files[0].parent / "Convertor output"

        self.report_savings = False
        self.job_action = self.action_var.get()
        try:
            job, cancellable = self.make_job(files, output)
        except ValueError as e:
            self.set_status(str(e), error=True)
            return

        self.last_output = output
        self.cancellable = cancellable
        self._started_at = time.monotonic()
        self.eta_label.configure(text="")
        self.set_running(True)
        self.progress.set(0)
        if not cancellable:
            self.progress.configure(mode="indeterminate")
            self.progress.start()
        self.set_status("Working...")
        self._hide_undo()
        self.runner.start(job)

    def cancel(self):
        self.runner.cancel()
        self.cancel_btn.configure(state="disabled")
        self.set_status("Stopping...")

    def on_file(self, number, total, name):
        if total == 0:
            self.set_status(name)
        else:
            self.set_status(f"{number}/{total}: {name}")

    def on_progress(self, fraction):
        if not self.cancellable:
            return
        fraction = max(0.0, min(1.0, fraction))
        self.progress.set(fraction)
        if fraction > 0.02 and self._started_at:
            elapsed = time.monotonic() - self._started_at
            remain = elapsed * (1 - fraction) / fraction
            self.eta_label.configure(text=f"{format_time(remain)} left")
        else:
            self.eta_label.configure(text="")

    def on_finished(self, result, error):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.eta_label.configure(text="")
        self.set_running(False)

        if self.on_save:
            self.on_save()

        config = load_config()
        sound_mode = config.get("sound_mode", "chime")
        custom_msg = config.get("custom_message", "Done! {count} files converted.")

        if error:
            self.progress.set(0)
            self.set_status(f"Error: {error}", error=True)
            play("error", sound_mode, "")
            ToastNotification(self.winfo_toplevel(), "Error", str(error), icon="❌")
            return

        done = len(result.done)
        if done:
            self.open_btn.configure(state="normal")

        if result.cancelled:
            self.set_status(f"Stopped. {done} finished.")
        elif result.failed:
            self.progress.set(1)
            self.set_status(f"Finished: {result.summary()}.", error=True)
            play("error", sound_mode, "")
            ToastNotification(self.winfo_toplevel(), "Some files failed", result.summary(), icon="⚠️")
            self.show_failures(result.failed)
        else:
            self.progress.set(1)
            msg = self.done_message(result)
            self.set_status(msg)

            speak_text = custom_msg.replace("{count}", str(done)).replace("file(s)", "files")
            play("success", sound_mode, speak_text)
            ToastNotification(self.winfo_toplevel(), "Success", msg, icon="✅")

            if done and self.last_output:
                history = config.get("history", [])
                entry = {
                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "action": self.job_action,
                    "count": done,
                    "destination": str(self.last_output)
                }
                history.insert(0, entry)
                config["history"] = history[:10]
                save_config(config)

    def show_failures(self, failed):
        lines = [f"{name}: {reason[:160]}" for name, reason in failed[:8]]
        if len(failed) > 8:
            lines.append(f"...and {len(failed) - 8} more")
        if messagebox.askyesno(
            "Some files failed",
            "\n\n".join(lines) + "\n\nOpen the error log?",
        ):
            log_path = data_dir() / "log.txt"
            if log_path.exists():
                open_path(log_path)

    def set_running(self, running):
        state = "disabled" if running else "normal"
        for widget in (self.start_btn, self.add_files_btn, self.add_folder_btn,
                       self.clear_btn, self.output_btn, self.action_menu,
                       self.presets_btn, self.recent_btn, self.filter_entry, self.sort_menu,
                       self.preset_menu, self.save_preset_btn, self.delete_preset_btn):
            widget.configure(state=state)
        if not running:
            self.refresh_output_label()
        self.cancel_btn.configure(
            state="normal" if running and self.cancellable else "disabled"
        )

    def set_status(self, text, error=False):
        self.status.configure(
            text=text, text_color=theme.ERROR if error else theme.MUTED
        )
        if "Restored" not in text and "copied" not in text:
            self._hide_undo()