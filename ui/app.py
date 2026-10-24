import customtkinter as ctk
import tkinter as tk
import sys
import os
import threading
import time
from pathlib import Path
from tkinter import messagebox
from PIL import Image, ImageTk, ImageOps

from core.appdata import load_config, log_exception, save_config
from core.media import stop_player
from core.tools import app_dir
from ui import theme
from ui.about_page import AboutPage
from ui.widgets import label, primary_button, secondary_button

PAGES = {
    "Images": "ui.images_page.ImagesPage",
    "PDFs": "ui.pdfs_page.PdfsPage",
    "Video": "ui.video_page.VideoPage",
    "Audio": "ui.audio_page.AudioPage",
    "Documents": "ui.docs_page.DocsPage",
    "Files": "ui.files_page.FilesPage",
}

try:
    from tkinterdnd2 import TkinterDnD
    class Window(ctk.CTk, TkinterDnD.DnDWrapper):
        pass
except Exception:
    TkinterDnD = None
    Window = ctk.CTk


class App(Window):
    def __init__(self):
        config = load_config()
        saved_mode = config.get("theme", "dark")
        if saved_mode not in theme.PALETTES:
            saved_mode = "dark"
            
        theme.use(saved_mode)
        is_dark = theme.is_dark_mode(saved_mode)
        ctk.set_appearance_mode("dark" if is_dark else "light")

        super().__init__(fg_color=theme.BG_TOP)
        
        # HIDE MAIN WINDOW AND SHOW SPLASH
        self.withdraw()
        from ui.splash import SplashScreen
        self.splash = SplashScreen(self)
        self.splash.update()
        
        app_name = config.get("app_name", "Convertor")
        self.title(app_name)

        icon_ico = app_dir() / "icon.ico"
        icon_png = app_dir() / "icon.png"
        try:
            if sys.platform == "win32" and icon_ico.exists():
                self.iconbitmap(str(icon_ico))
            elif icon_png.exists():
                img = Image.open(icon_png)
                self._icon_img = ImageTk.PhotoImage(img)
                self.iconphoto(True, self._icon_img)
        except Exception:
            pass

        geometry = config.get("geometry")
        restored = False
        if geometry:
            try:
                self.geometry(geometry)
                restored = True
            except Exception:
                pass
        if not restored:
            width = min(1180, self.winfo_screenwidth() - 40)
            height = min(820, self.winfo_screenheight() - 90)
            self.geometry(f"{width}x{height}")
        self.minsize(980, 640)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.dnd_ready = False
        if TkinterDnD is not None:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
                self.dnd_ready = True
            except Exception:
                log_exception("drag and drop is not available")

        self.bg_canvas = tk.Canvas(self, highlightthickness=0, bg=theme.BG_TOP)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.bind("<Configure>", self._queue_bg_update)
        self._bg_job = None

        self._accent_cache = {}
        self._destroying = False

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.current = "Images"
        self.wait_ticks = 0
        self.pages = {}
        self.nav_buttons = {}
        self.nav_indicators = {}
        
        self._build_sidebar(app_name)
        
        self.page_config = config.get("pages", {})
        
        self.bind_all("<Control-o>", self._shortcut_open, add="+")
        self.bind_all("<Control-O>", self._shortcut_open_folder, add="+")
        self.bind_all("<Control-Return>", self._shortcut_start, add="+")
        self.bind_all("<Escape>", self._shortcut_cancel, add="+")
        self.bind_all("<Delete>", self._shortcut_delete, add="+")
        self.bind_all("<Control-v>", self._shortcut_paste, add="+")
        self.bind_all("<Command-v>", self._shortcut_paste, add="+")

        saved_page = config.get("last_page")
        self.show(saved_page if saved_page in PAGES else "Images")
        
        self.after(50, self._draw_bg)

        # END SPLASH AND SHOW MAIN WINDOW
        self.after(600, self._close_splash)
        
        self.report_callback_exception = self._safe_callback_error

    def _close_splash(self):
        if hasattr(self, 'splash') and self.splash.winfo_exists():
            self.splash.destroy()
        self.deiconify()

    def _safe_callback_error(self, exc_type, exc_val, tb):
        if self._destroying:
            return
        if isinstance(exc_val, tk.TclError):
            s = str(exc_val).lower()
            if ("invalid command name" in s or 
                "check_dpi_scaling" in s or
                "application has been destroyed" in s):
                return
        import traceback
        text = "".join(traceback.format_exception(exc_type, exc_val, tb))
        log_exception("window callback")
        print(text)

    def _build_sidebar(self, app_name):
        self.sidebar = ctk.CTkFrame(
            self, width=190, corner_radius=0, fg_color=theme.SIDEBAR
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.pack_propagate(False)

        self.title_label = ctk.CTkLabel(
            self.sidebar, text=app_name, font=theme.font(18, "bold"),
            text_color=theme.TEXT, anchor="w",
        )
        self.title_label.pack(fill="x", padx=20, pady=(24, 20))

        for name in PAGES:
            self._create_nav_button(name)
            
        self._create_nav_button("About")

        spacer = ctk.CTkFrame(self.sidebar, fg_color="transparent", corner_radius=0)
        spacer.pack(fill="both", expand=True)

        bottom_row = ctk.CTkFrame(self.sidebar, fg_color="transparent", corner_radius=0)
        bottom_row.pack(fill="x", padx=12, pady=(0, 12))

        theme_names = sorted([k.capitalize() for k in theme.PALETTES.keys()])
        
        self.theme_var = ctk.StringVar(value=theme.current_mode().capitalize())
        self.theme_menu = ctk.CTkOptionMenu(
            bottom_row, values=theme_names,
            variable=self.theme_var, command=self.change_theme,
            width=125, height=28, corner_radius=0,
            fg_color=theme.PANEL, button_color=theme.BORDER,
            button_hover_color=theme.HOVER, text_color=theme.TEXT,
            dropdown_fg_color=theme.PANEL, dropdown_hover_color=theme.HOVER,
            dropdown_text_color=theme.TEXT, font=theme.font(12),
            dropdown_font=theme.font(12),
        )
        self.theme_menu.pack(side="left")

    def _create_nav_button(self, name):
        row = ctk.CTkFrame(self.sidebar, fg_color="transparent", corner_radius=0)
        row.pack(fill="x", padx=12, pady=2)
        
        indicator = ctk.CTkFrame(row, width=4, height=24, fg_color="transparent", corner_radius=0)
        indicator.pack(side="left", padx=(0, 4))
        self.nav_indicators[name] = indicator
        
        btn = ctk.CTkButton(
            row, text=name, anchor="w", height=36,
            corner_radius=0, font=theme.font(14),
            fg_color="transparent", hover_color=theme.HOVER,
            text_color=theme.TEXT,
            command=lambda n=name: self.show(n),
        )
        btn.pack(side="left", fill="x", expand=True)
        self.nav_buttons[name] = btn

    def _load_page(self, name):
        if name in self.pages:
            return self.pages[name]

        try:
            if name == "About":
                page = AboutPage(self, state=self.page_config.get("About", {}))
            else:
                module_path, class_name = PAGES[name].rsplit(".", 1)
                import importlib
                module = importlib.import_module(module_path)
                page_class = getattr(module, class_name)
                page = page_class(self, state=self.page_config.get(name, {}))
                
            page.on_save = self.save_settings
            page.grid(row=0, column=1, sticky="nsew")
            page.grid_remove()
            self.pages[name] = page
            self._accent_cache.pop(name, None)
            return page
        except Exception:
            log_exception(f"building the {name} page")
            return None

    def change_theme(self, choice):
        if self.running_pages():
            messagebox.showinfo("Job running", "Please wait for the job to finish.")
            self.theme_var.set(theme.current_mode().capitalize())
            return

        self.save_settings()
        self.page_config = load_config().get("pages", {})
        mode = choice.lower()
        theme.use(mode)
        
        is_dark = theme.is_dark_mode(mode)
        ctk.set_appearance_mode("dark" if is_dark else "light")
        
        self.configure(fg_color=theme.BG_TOP)
        self._apply_sidebar_theme()
        
        for name, page in list(self.pages.items()):
            try:
                page.destroy()
            except Exception:
                pass
            del self.pages[name]
        self._accent_cache.clear()
        
        self.show(self.current)
        self._draw_bg()
        self.save_settings()

    def _apply_sidebar_theme(self):
        self.configure(fg_color=theme.BG_TOP)
        self.sidebar.configure(fg_color=theme.SIDEBAR)
        self.title_label.configure(text_color=theme.TEXT)
        for button in self.nav_buttons.values():
            try:
                button.configure(text_color=theme.TEXT, hover_color=theme.HOVER)
            except Exception:
                pass
        self.theme_menu.configure(
            fg_color=theme.PANEL, button_color=theme.BORDER,
            button_hover_color=theme.HOVER, text_color=theme.TEXT,
            dropdown_fg_color=theme.PANEL, dropdown_hover_color=theme.HOVER,
            dropdown_text_color=theme.TEXT,
        )

    def show(self, name):
        if name not in self.nav_buttons:
            return
            
        self.current = name
        
        for page in self.pages.values():
            page.grid_remove()
        for btn_name, btn in self.nav_buttons.items():
            btn.configure(fg_color="transparent")
            self.nav_indicators[btn_name].configure(fg_color="transparent")

        page = self._load_page(name)
        if page:
            page.grid()
            
        self.nav_buttons[name].configure(fg_color=theme.PANEL)
        self.nav_indicators[name].configure(fg_color=theme.ACCENT)

    def _queue_bg_update(self, event=None):
        if self._destroying:
            return
        # If an update is already scheduled for the next frame, ignore this one.
        if self._bg_job:
            return
            
        # Draw the background 15 milliseconds from now (approx 60 FPS)
        self._bg_job = self.after(15, self._draw_bg)

    def _draw_bg(self):
        self._bg_job = None
        if self._destroying or not self.bg_canvas.winfo_exists():
            return
        try:
            if not self.winfo_viewable():
                return
        except Exception:
            return
        
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1 or h <= 1:
            return
        
        try:
            self.bg_canvas.delete("bg_gradient")
            
            r1, g1, b1 = self._hex_to_rgb(theme.BG_TOP)
            r2, g2, b2 = self._hex_to_rgb(theme.BG_BOTTOM)
            
            steps = 30
            band_h = h / steps
            
            for i in range(steps):
                ratio = i / (steps - 1)
                r = int(r1 + (r2 - r1) * ratio)
                g = int(g1 + (g2 - g1) * ratio)
                b = int(b1 + (b2 - b1) * ratio)
                color = f"#{r:02x}{g:02x}{b:02x}"
                y1 = i * band_h
                y2 = (i + 1) * band_h
                self.bg_canvas.create_rectangle(
                    0, y1, w, y2, fill=color, outline="", tags="bg_gradient"
                )
        except Exception:
            pass

    def _hex_to_rgb(self, hex_color):
        h = hex_color.lstrip('#')
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    def on_close(self):
        if self._destroying:
            return
        
        busy = self.running_pages()
        if busy:
            if not messagebox.askyesno("Job running", "A job is still running. Stop it and quit?"):
                return
            for page in busy:
                page.runner.cancel()
        
        self._destroying = True
        
        if self._bg_job:
            try:
                self.after_cancel(self._bg_job)
            except Exception:
                pass
            self._bg_job = None
        
        try:
            self.save_settings()
        except Exception:
            pass
        try:
            stop_player()
        except Exception:
            pass
        
        try:
            self.withdraw()
        except Exception:
            pass
        
        def hard_exit():
            time.sleep(0.8)
            os._exit(0)
        
        threading.Thread(target=hard_exit, daemon=True).start()

    def _current_page(self):
        return self.pages.get(self.current)

    def _shortcut_paste(self, _event=None):
        page = self._current_page()
        if not page or not hasattr(page, "paste_from_clipboard"):
            return
        focus = self.focus_get()
        if focus:
            try:
                if focus.winfo_class() in ("Entry", "TEntry", "Text"):
                    return
            except Exception:
                pass
        try:
            page.paste_from_clipboard()
        except Exception:
            pass
        return "break"

    def _shortcut_open(self, _event=None):
        page = self._current_page()
        if not page or not hasattr(page, "pick_files"): return "break"
        if getattr(page, "runner", None) and page.runner.running: return "break"
        try: page.pick_files()
        except: pass
        return "break"

    def _shortcut_open_folder(self, _event=None):
        page = self._current_page()
        if not page or not hasattr(page, "pick_folder"): return "break"
        if getattr(page, "runner", None) and page.runner.running: return "break"
        try: page.pick_folder()
        except: pass
        return "break"

    def _shortcut_start(self, _event=None):
        page = self._current_page()
        if not page or not hasattr(page, "start"): return "break"
        if getattr(page, "runner", None) and page.runner.running: return "break"
        try: page.start()
        except: pass
        return "break"

    def _shortcut_cancel(self, _event=None):
        page = self._current_page()
        if not page or not hasattr(page, "cancel"): return
        if not getattr(page, "runner", None) or not page.runner.running: return
        try: page.cancel()
        except: pass
        return "break"

    def _shortcut_delete(self, _event=None):
        focus = self.focus_get()
        if focus:
            try:
                if focus.winfo_class() in ("Entry", "TEntry", "Text"): return
            except: pass
        page = self._current_page()
        if not page or not hasattr(page, "remove_selected"): return
        try: page.remove_selected()
        except: pass
        return "break"

    def save_settings(self):
        data = load_config()
        data["last_page"] = self.current
        data["theme"] = theme.current_mode()
        data["geometry"] = self.geometry()
        
        if "pages" not in data:
            data["pages"] = {}
            
        for name, page in self.pages.items():
            try:
                data["pages"][name] = page.get_state()
            except Exception:
                log_exception(f"saving {name} settings")
                
        save_config(data)

    def running_pages(self):
        return [p for p in self.pages.values()
                if hasattr(p, "runner") and p.runner.running]