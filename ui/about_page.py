import customtkinter as ctk
import threading
import subprocess
import sys
import os
import shutil
import traceback
from pathlib import Path

from core.appdata import data_dir, open_path, load_config, save_config
from core.tools import tool_status, find_tool
from ui import theme
from ui.widgets import (
    Page, card, label, secondary_button, primary_button, shorten, entry,
    SquaredScrollableFrame, SquaredTextbox,
)

TOOL_INFO = {
    "ffmpeg": ("ffmpeg", "Needed for video and audio.", "ffmpeg", "Gyan.FFmpeg"),
    "ffprobe": ("ffprobe", "Reads video/audio details.", "ffmpeg", "Gyan.FFmpeg"),
    "ffplay": ("ffplay", "Plays the preview window.", "ffmpeg", "Gyan.FFmpeg"),
    "mpv": ("mpv", "In-app video player with controls.", "mpv", "shinchiro.mpv"),
    "soffice": ("LibreOffice", "Needed for Documents page.", "--cask libreoffice", "TheDocumentFoundation.LibreOffice"),
    "tesseract": ("Tesseract OCR", "Reads text from scanned PDFs.", "tesseract", "UB-Mannheim.TesseractOCR"),
}


class _StdoutRedirector:
    """Redirects print() statements to the UI text box in real-time."""
    def __init__(self, callback):
        self.callback = callback

    def write(self, text):
        if text:
            self.callback(text)

    def flush(self):
        pass


class AboutPage(Page):
    def __init__(self, parent, state=None):
        super().__init__(parent, "About", "What's installed and where things are kept.")
        self.state = state or {}
        self.installing = {}
        self.temp_path = None

        self.scroll = SquaredScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=0, pady=0)

        self.tools_card = card(self.scroll)
        self.tools_card.pack(fill="x", padx=32, pady=(18, 0))

        self.history_card = card(self.scroll)
        self.history_card.pack(fill="x", padx=32, pady=(14, 0))

        self.files_card = card(self.scroll)
        self.files_card.pack(fill="x", padx=32, pady=(14, 0))
        label(self.files_card, "Your files", 15, "bold").pack(fill="x", padx=16, pady=(14, 4))
        label(
            self.files_card,
            "Its all local man. Chill. Your settings and a log of any errors are kept in this folder:",
            13, color=theme.MUTED, wraplength=720, justify="left",
        ).pack(fill="x", padx=16)
        label(self.files_card, shorten(str(data_dir()), 90), 13).pack(fill="x", padx=16, pady=(6, 0))
        row = ctk.CTkFrame(self.files_card, fg_color="transparent", corner_radius=0)
        row.pack(fill="x", padx=16, pady=14)
        secondary_button(row, "Open folder", lambda: open_path(data_dir()), width=120).pack(side="left")

        self.settings_card = card(self.scroll)
        self.settings_card.pack(fill="x", padx=32, pady=(14, 0))
        label(self.settings_card, "Personalization & Settings", 15, "bold").pack(fill="x", padx=16, pady=(14, 8))

        config = load_config()

        row_name = ctk.CTkFrame(self.settings_card, fg_color="transparent", corner_radius=0)
        row_name.pack(fill="x", padx=16, pady=4)
        label(row_name, "App Name", 13, color=theme.MUTED, width=120).pack(side="left")
        self.name_var = ctk.StringVar(value=config.get("app_name", "Convertor"))
        entry(row_name, self.name_var).pack(side="left", fill="x", expand=True)

        row_msg = ctk.CTkFrame(self.settings_card, fg_color="transparent", corner_radius=0)
        row_msg.pack(fill="x", padx=16, pady=4)
        label(row_msg, "Success Message", 13, color=theme.MUTED, width=120).pack(side="left")
        self.msg_var = ctk.StringVar(value=config.get("custom_message", "Done! {count} file(s) processed."))
        entry(row_msg, self.msg_var).pack(side="left", fill="x", expand=True)

        row_sound = ctk.CTkFrame(self.settings_card, fg_color="transparent", corner_radius=0)
        row_sound.pack(fill="x", padx=16, pady=(8, 4))

        label(row_sound, "Completion Sound", 13, color=theme.MUTED, width=120).pack(side="left")

        sound_mode = config.get("sound_mode", "chime")
        self.labels = {
            "chime": "Chime (Soft System)",
            "tada": "Tada (System)",
            "pop": "Pop (Quick Beep)",
            "cute": "Cute Melody",
            "voice": "Speak the Message",
            "off": "Off",
        }

        self.sound_var = ctk.StringVar(value=self.labels.get(sound_mode, "Chime (Soft System)"))
        self.sound_menu = ctk.CTkOptionMenu(
            row_sound, values=list(self.labels.values()), variable=self.sound_var,
            width=180, height=28, corner_radius=0,
            fg_color=theme.PANEL, button_color=theme.BORDER,
            button_hover_color=theme.HOVER, text_color=theme.TEXT,
            dropdown_fg_color=theme.PANEL, dropdown_hover_color=theme.HOVER,
            dropdown_text_color=theme.TEXT, font=theme.font(12), dropdown_font=theme.font(12),
        )
        self.sound_menu.pack(side="right")

        row_save = ctk.CTkFrame(self.settings_card, fg_color="transparent", corner_radius=0)
        row_save.pack(fill="x", padx=16, pady=(12, 16))

        self.save_status = label(row_save, "", 12, color=theme.ACCENT)
        self.save_status.pack(side="left")

        self.save_btn = primary_button(row_save, "Save Settings", self.save_all_settings, width=140)
        self.save_btn.pack(side="right")

        self.test_card = card(self.scroll)
        self.test_card.pack(fill="x", padx=32, pady=(14, 14))
        label(self.test_card, "Diagnostics", 15, "bold").pack(fill="x", padx=16, pady=(14, 4))
        label(
            self.test_card,
            "Runs automated checks on the backend. "
            "It creates temporary files to test conversions. Works in both the source version and the packaged app.",
            13, color=theme.MUTED, wraplength=720, justify="left",
        ).pack(fill="x", padx=16)

        self.test_output = SquaredTextbox(
            self.test_card, height=200, font=theme.font(11),
            fg_color=theme.BG, text_color=theme.TEXT, border_width=1, border_color=theme.BORDER,
        )
        self.test_output.pack(fill="x", padx=16, pady=(10, 10))
        self.test_output.insert("1.0", "Test output will appear here...\n")

        btn_row = ctk.CTkFrame(self.test_card, fg_color="transparent", corner_radius=0)
        btn_row.pack(fill="x", padx=16, pady=(0, 14))

        self.run_test_btn = primary_button(btn_row, "Run Self-Test", self.run_selftest, width=140)
        self.run_test_btn.pack(side="left")

        self.delete_test_btn = secondary_button(btn_row, "Delete Test Files", self.delete_selftest_files, width=140)
        self.delete_test_btn.pack(side="left", padx=8)
        self.delete_test_btn.configure(state="disabled")

        self.refresh()

    def save_all_settings(self):
        config = load_config()
        config["app_name"] = self.name_var.get().strip() or "Convertor"
        config["custom_message"] = self.msg_var.get().strip() or "Done! {count} file(s) processed."

        reverse_labels = {v: k for k, v in self.labels.items()}
        config["sound_mode"] = reverse_labels.get(self.sound_var.get(), "chime")

        save_config(config)

        self.winfo_toplevel().title(config["app_name"])

        self.save_status.configure(text="Settings saved successfully!")
        self.save_btn.configure(text="Saved!", fg_color=theme.ACCENT_HOVER)

        def reset_btn():
            if self.winfo_exists():
                self.save_status.configure(text="")
                self.save_btn.configure(text="Save Settings", fg_color=theme.ACCENT)

        self.after(2000, reset_btn)

    def _append_test_log(self, text):
        if not self.winfo_exists():
            return
        self.test_output.insert("end", text)
        self.test_output.see("end")

    def run_selftest(self):
        self.run_test_btn.configure(state="disabled", text="Running...")
        self.delete_test_btn.configure(state="disabled")
        self.test_output.delete("1.0", "end")
        self.temp_path = None

        def task():
            old_stdout = sys.stdout
            sys.stdout = _StdoutRedirector(lambda text: self.after(0, self._append_test_log, text) if self.winfo_exists() else None)

            try:
                import importlib
                if "selftest" in sys.modules:
                    selftest = importlib.reload(sys.modules["selftest"])
                else:
                    import selftest
                
                passed, total, failed, root = selftest.run_all()
                self.temp_path = str(root)
            except SystemExit:
                passed, total, failed = 0, 0, []
            except Exception:
                self.after(0, self._append_test_log, f"\nSelf-test crashed:\n{traceback.format_exc()}\n") if self.winfo_exists() else None
                passed, total, failed = 0, 0, []
            finally:
                sys.stdout = old_stdout

            if self.winfo_exists():
                self.after(0, lambda: self._append_test_log(
                    f"\n--- Done. {passed} passed of {total}. ---\n"
                ))
                self.after(0, self._test_finished)

        threading.Thread(target=task, daemon=True).start()

    def _test_finished(self):
        if not self.winfo_exists():
            return
        self.run_test_btn.configure(state="normal", text="Run Self-Test")
        if self.temp_path and Path(self.temp_path).exists():
            self.delete_test_btn.configure(state="normal")
            self._append_test_log(f"\nTest files are in:\n{self.temp_path}\n")
        else:
            self._append_test_log("\n(No temp folder to delete.)\n")

    def delete_selftest_files(self):
        if not self.temp_path or not Path(self.temp_path).exists():
            return
        try:
            shutil.rmtree(self.temp_path, ignore_errors=True)
            self._append_test_log("\n--- Test files deleted. ---\n")
            self.delete_test_btn.configure(state="disabled")
            self.temp_path = None
        except Exception as e:
            self._append_test_log(f"\n--- Failed to delete: {e} ---\n")

    def install_homebrew(self, btn):
        btn.configure(text="Check Terminal", state="disabled")
        cmd = '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
        try:
            safe_cmd = cmd.replace('"', '\\"')
            applescript = f'tell application "Terminal" to do script "{safe_cmd}"'
            subprocess.Popen(["osascript", "-e", applescript])
            subprocess.Popen(["osascript", "-e", 'tell application "Terminal" to activate'])

            from tkinter import messagebox
            messagebox.showinfo(
                "Install Homebrew",
                "I have opened the Terminal and started the Homebrew installer.\n\n"
                "Please go to the Terminal window, type your Mac password when prompted, "
                "and press Enter.\n\n"
                "Once it finishes, come back to this app and click 'Check again'.",
            )
        except Exception:
            btn.configure(text="Failed", state="normal", fg_color=theme.ERROR)

    def install_tool(self, mac_pkg, win_pkg, btn):
        btn.configure(text="Installing...", state="disabled")

        def run_install():
            try:
                if sys.platform == "darwin":
                    brew_path = find_tool("brew") or "brew"
                    cmd = [brew_path, "install"] + mac_pkg.split()
                else:
                    cmd = ["winget", "install", win_pkg,
                           "--accept-package-agreements",
                           "--accept-source-agreements", "--silent"]

                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                subprocess.run(cmd, creationflags=flags, check=True)
                if self.winfo_exists():
                    self.after(0, lambda: self._install_done(btn, True))
            except Exception:
                if self.winfo_exists():
                    self.after(0, lambda: self._install_done(btn, False))

        threading.Thread(target=run_install, daemon=True).start()

    def _install_done(self, btn, success):
        if not self.winfo_exists():
            return
        if success:
            btn.configure(text="Installed! Restart App", state="disabled", fg_color=theme.ACCENT)
        else:
            btn.configure(text="Failed (Check log)", state="normal", fg_color=theme.ERROR)
        self.after(1000, self.refresh)

    def get_state(self):
        return {}

    def refresh(self):
        if not self.winfo_exists():
            return
            
        for child in self.tools_card.winfo_children():
            child.destroy()

        label(self.tools_card, "Helper programs", 15, "bold").pack(fill="x", padx=16, pady=(14, 4))

        statuses = tool_status()
        is_mac = sys.platform == "darwin"
        brew_missing = is_mac and not statuses.get("brew")

        if brew_missing:
            brew_row = ctk.CTkFrame(self.tools_card, fg_color=theme.BG, corner_radius=0)
            brew_row.pack(fill="x", padx=16, pady=(0, 10))
            label(brew_row, "Homebrew is missing. It is required to auto-install tools on Mac.",
                  12, color=theme.ERROR).pack(side="left", padx=10, pady=10)
            brew_btn = secondary_button(brew_row, "Install Homebrew", None, width=140)
            brew_btn.configure(command=lambda b=brew_btn: self.install_homebrew(b))
            brew_btn.pack(side="right", padx=10, pady=10)

        installed_ids = set()
        for key, path in statuses.items():
            if key not in TOOL_INFO or key == "brew":
                continue

            name, why, mac_pkg, win_pkg = TOOL_INFO[key]
            row = ctk.CTkFrame(self.tools_card, fg_color="transparent", corner_radius=0)
            row.pack(fill="x", padx=16, pady=3)

            mark = "Found" if path else "Not found"
            color = theme.ACCENT if path else theme.ERROR
            label(row, mark, 13, "bold", color=color, width=70).pack(side="left")
            label(row, name, 13, width=110).pack(side="left")
            label(row, why, 12, color=theme.MUTED).pack(side="left", fill="x", expand=True)

            if not path and win_pkg not in installed_ids:
                installed_ids.add(win_pkg)
                btn = secondary_button(row, "Install", None, width=70)
                btn.configure(command=lambda m=mac_pkg, w=win_pkg, b=btn: self.install_tool(m, w, b))
                btn.pack(side="right", padx=(10, 0))

        row = ctk.CTkFrame(self.tools_card, fg_color="transparent", corner_radius=0)
        row.pack(fill="x", padx=16, pady=14)
        secondary_button(row, "Check again", self.refresh, width=120).pack(side="left")

        for child in self.history_card.winfo_children():
            child.destroy()

        label(self.history_card, "Recent Conversions", 15, "bold").pack(fill="x", padx=16, pady=(14, 4))
        history = load_config().get("history", [])

        if not history:
            label(self.history_card, "No recent jobs yet.", 13, color=theme.MUTED).pack(
                fill="x", padx=16, pady=(0, 14)
            )
        else:
            for item in history:
                row = ctk.CTkFrame(self.history_card, fg_color="transparent", corner_radius=0)
                row.pack(fill="x", padx=16, pady=2)

                time_str = item.get("time", "")
                action = item.get("action", "")
                count = item.get("count", 0)
                dest = item.get("destination", "")

                text = f"[{time_str}] {action} ({count} file{'s' if count != 1 else ''})"
                label(row, shorten(text, 65), 12, color=theme.TEXT).pack(side="left", fill="x", expand=True)

                if Path(dest).exists():
                    secondary_button(row, "Open", lambda d=dest: open_path(d), width=60).pack(side="right")

            btn_clear = secondary_button(self.history_card, "Clear History", self.clear_history, width=120)
            btn_clear.pack(anchor="e", padx=16, pady=(6, 14))

    def clear_history(self):
        config = load_config()
        config["history"] = []
        save_config(config)
        self.refresh()