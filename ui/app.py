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
from ui.widgets import label, primary_button, secondary_button, SmoothScrollableFrame, SidebarNavButton

PAGES = {
    "Images": "ui.images_page.ImagesPage",
    "PDFs": "ui.pdfs_page.PdfsPage",
    "Video": "ui.video_page.VideoPage",
    "Audio": "ui.audio_page.AudioPage",
    "Brushes": "ui.brushes_page.BrushesPage",
    "Documents": "ui.docs_page.DocsPage",
    "Files": "ui.files_page.FilesPage",
}

NAV_ICONS = {
    "Images": "🖼️",
    "PDFs": "📄",
    "Video": "📹",
    "Audio": "🎵",
    "Brushes": "🖌️",
    "Documents": "📝",
    "Files": "📦",
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
        
        # Enforce default settings for first-time users
        if "use_card_actions" not in config:
            config["use_card_actions"] = True
            save_config(config)
            
        saved_mode = config.get("theme", "dark")
        if saved_mode not in theme.PALETTES:
            saved_mode = "dark"
            
        theme.use(saved_mode)
        is_dark = theme.is_dark_mode(saved_mode)
        ctk.set_appearance_mode("dark" if is_dark else "light")

        super().__init__(fg_color=theme.BG_TOP)
        
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

        # Background Canvas
        self.bg_canvas = tk.Canvas(self, highlightthickness=0, bg=theme.BG_TOP)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.bind("<Configure>", self._queue_bg_update)
        self._bg_job = None

        self._accent_cache = {}
        self._destroying = False
        self._theme_menu_open = False

        # Navigation History
        self.current = "Images"
        self.nav_history = ["Images"]
        self.nav_index = 0

        self.wait_ticks = 0
        self.pages = {}
        self.nav_buttons = {}
        
        self._build_layout(app_name)
        
        self.page_config = config.get("pages", {})
        
        self.bind_all("<Control-o>", self._shortcut_open, add="+")
        self.bind_all("<Control-O>", self._shortcut_open_folder, add="+")
        self.bind_all("<Control-Return>", self._shortcut_start, add="+")
        self.bind_all("<Escape>", self._shortcut_cancel, add="+")
        self.bind_all("<Delete>", self._shortcut_delete, add="+")
        self.bind_all("<Control-v>", self._shortcut_paste, add="+")
        self.bind_all("<Command-v>", self._shortcut_paste, add="+")

        saved_page = config.get("last_page")
        self.show(saved_page if saved_page in PAGES else "Images", push_history=True)
        
        self.after(50, self._draw_bg)
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

    def _build_layout(self, app_name):
        # --- SIDEBAR ---
        self.sidebar = ctk.CTkFrame(
            self, width=180, corner_radius=0, fg_color=theme.SIDEBAR
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Title Row
        title_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent", corner_radius=0, height=36)
        title_frame.pack(fill="x", padx=12, pady=(24, 16))
        title_frame.pack_propagate(False)
        
        ctk.CTkLabel(title_frame, text="📁", anchor="w", font=theme.font(14)).place(x=12, rely=0.5, anchor="w")
        self.title_label = ctk.CTkLabel(title_frame, text=app_name, font=theme.font(18, "bold"), anchor="w", text_color=theme.TEXT)
        self.title_label.place(x=48, rely=0.5, anchor="w")

        # Nav Buttons
        for name in PAGES:
            self._create_nav_button(name)

        # --- BOTTOM ROW (Theme & About) ---
        self.bottom_row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.bottom_row.pack(side="bottom", fill="x", padx=12, pady=(0, 16))

        self.theme_btn = SidebarNavButton(
            self.bottom_row, icon="🎨", text=theme.current_mode().replace('_', ' ').title(),
            command=self._toggle_theme_menu
        )
        self.theme_btn.pack(fill="x", pady=2)

        self.about_btn = SidebarNavButton(
            self.bottom_row, icon="ℹ️", text="About",
            command=lambda: self.show("About", push_history=True)
        )
        self.about_btn.pack(fill="x", pady=2)
        self.nav_buttons["About"] = self.about_btn

        # --- THEME MENU (INLINE) ---
        self.theme_popup_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        
        self.theme_scroll = SmoothScrollableFrame(
            self.theme_popup_frame, fg_color=theme.PANEL, corner_radius=theme.RADIUS, height=120
        )
        self.theme_scroll.pack(fill="x", padx=12, pady=(0, 8))

        # Spacer (fills remaining space when theme menu is closed)
        self.spacer = ctk.CTkFrame(self.sidebar, fg_color="transparent", corner_radius=0)
        self.spacer.pack(fill="both", expand=True)

        # --- MAIN AREA ---
        self.main_area = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.main_area.pack(side="left", fill="both", expand=True)

        # Top Bar
        top_bar = ctk.CTkFrame(self.main_area, fg_color="transparent", height=50)
        top_bar.pack(fill="x", padx=20, pady=(10, 0))
        
        # Back/Forward Buttons
        self.back_btn = ctk.CTkButton(
            top_bar, text="◀", width=32, height=32, 
            fg_color=theme.BG_TOP, hover_color=theme.HOVER, 
            command=self._nav_back, text_color=theme.MUTED, 
            font=theme.font(14), corner_radius=theme.RADIUS
        )
        self.back_btn.pack(side="left")
        
        self.fwd_btn = ctk.CTkButton(
            top_bar, text="▶", width=32, height=32, 
            fg_color=theme.BG_TOP, hover_color=theme.HOVER, 
            command=self._nav_forward, text_color=theme.MUTED, 
            font=theme.font(14), corner_radius=theme.RADIUS
        )
        self.fwd_btn.pack(side="left", padx=(4, 0))
        
        self.top_title = ctk.CTkLabel(
            top_bar, text="Images", font=theme.font(14, "bold"), text_color=theme.TEXT
        )
        self.top_title.pack(side="left", padx=20)

        # Container for the pages
        self.page_container = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.page_container.pack(fill="both", expand=True, padx=20, pady=(10, 20))

    def _create_nav_button(self, name):
        icon = NAV_ICONS.get(name, "")
        btn = SidebarNavButton(
            self.sidebar, icon=icon, text=name,
            command=lambda n=name: self.show(n, push_history=True)
        )
        btn.pack(fill="x", padx=12, pady=2)
        self.nav_buttons[name] = btn

    def _toggle_theme_menu(self):
        if self.running_pages():
            messagebox.showinfo("Job running", "Please wait for the job to finish.")
            return
            
        if self._theme_menu_open:
            self.theme_popup_frame.pack_forget()
            self.spacer.pack(fill="both", expand=True)
            self._theme_menu_open = False
        else:
            self._populate_theme_menu()
            self.spacer.pack_forget()
            self.theme_popup_frame.pack(fill="x", side="bottom", before=self.bottom_row)
            self._theme_menu_open = True

    def _populate_theme_menu(self):
        for child in self.theme_scroll.winfo_children():
            child.destroy()
            
        current = theme.current_mode()
        for mode in sorted(theme.PALETTES.keys()):
            name = mode.replace("_", " ").title()
            is_current = (mode == current)
            
            btn = ctk.CTkButton(
                self.theme_scroll, text=name, anchor="w", height=28,
                fg_color=theme.SELECT if is_current else "transparent",
                text_color=theme.get_contrast_text(theme.SELECT) if is_current else theme.TEXT,
                hover_color=theme.HOVER, corner_radius=theme.RADIUS,
                font=theme.font(12),
                command=lambda m=mode: self._pick_theme(m)
            )
            btn.pack(fill="x", pady=1)

    def _pick_theme(self, mode):
        self._theme_menu_open = False
        self.theme_popup_frame.pack_forget()
        self.spacer.pack(fill="both", expand=True)
        self.change_theme(mode)

    # --- NAVIGATION HISTORY ---
    def _nav_back(self):
        if self.nav_index > 0:
            self.nav_index -= 1
            self.show(self.nav_history[self.nav_index], push_history=False)

    def _nav_forward(self):
        if self.nav_index < len(self.nav_history) - 1:
            self.nav_index += 1
            self.show(self.nav_history[self.nav_index], push_history=False)

    def _update_nav_buttons(self):
        if self.nav_index > 0:
            self.back_btn.configure(state="normal", text_color=theme.TEXT)
        else:
            self.back_btn.configure(state="disabled", text_color=theme.BORDER)

        if self.nav_index < len(self.nav_history) - 1:
            self.fwd_btn.configure(state="normal", text_color=theme.TEXT)
        else:
            self.fwd_btn.configure(state="disabled", text_color=theme.BORDER)

    def _copy_error(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", "Error traceback copied to clipboard.")

    def _load_page(self, name):
        if name in self.pages:
            return self.pages[name]

        try:
            if name == "About":
                page = AboutPage(self.page_container, state=self.page_config.get("About", {}))
            else:
                module_path, class_name = PAGES[name].rsplit(".", 1)
                import importlib
                module = importlib.import_module(module_path)
                page_class = getattr(module, class_name)
                page = page_class(self.page_container, state=self.page_config.get(name, {}))
                
            page.on_save = self.save_settings
            page.pack(fill="both", expand=True)
            page.pack_forget()
            self.pages[name] = page
            self._accent_cache.pop(name, None)
            return page
        except Exception as e:
            log_exception(f"building the {name} page")
            import traceback
            err_msg = traceback.format_exc()
            
            err_frame = ctk.CTkFrame(self.page_container, fg_color=theme.PANEL, corner_radius=0)
            err_frame.pack(fill="both", expand=True)

            top = ctk.CTkFrame(err_frame, fg_color="transparent")
            top.pack(fill="x", padx=20, pady=(20, 10))
            
            ctk.CTkLabel(top, text=f"Failed to load {name} page.", font=theme.font(18, "bold"), text_color=theme.ERROR).pack(side="left")
            
            btn = primary_button(top, "Copy Error", lambda: self._copy_error(err_msg), width=100)
            btn.pack(side="right")

            err_textbox = ctk.CTkTextbox(err_frame, text_color=theme.TEXT, fg_color=theme.BG, corner_radius=0)
            err_textbox.pack(fill="both", expand=True, padx=20, pady=(0, 20))
            err_textbox.insert("1.0", err_msg)
            err_textbox.configure(state="disabled")
            
            self.pages[name] = err_frame
            return err_frame

    def refresh_pages(self):
        for name, page in list(self.pages.items()):
            if name != "About":
                try:
                    page.destroy()
                except Exception:
                    pass
                del self.pages[name]
        
        if self.current != "About":
            self.show(self.current, push_history=False)

    def change_theme(self, mode):
        self.save_settings()
        self.page_config = load_config().get("pages", {})
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
        
        self.show(self.current, push_history=False)
        self._draw_bg()
        self.save_settings()

    def _apply_sidebar_theme(self):
        self.configure(fg_color=theme.BG_TOP)
        self.sidebar.configure(fg_color=theme.SIDEBAR)
        self.title_label.configure(text_color=theme.TEXT)
        self.top_title.configure(text_color=theme.TEXT)
        
        for button in self.nav_buttons.values():
            try:
                button.configure(text_color=theme.TEXT, hover_color=theme.HOVER, corner_radius=theme.RADIUS)
            except Exception:
                pass
                
        self.theme_btn.configure(
            text=theme.current_mode().replace('_', ' ').title(),
            text_color=theme.MUTED, hover_color=theme.HOVER, corner_radius=theme.RADIUS
        )
        self.about_btn.configure(
            text_color=theme.MUTED, hover_color=theme.HOVER, corner_radius=theme.RADIUS
        )
        
        if hasattr(self, 'theme_scroll'):
            self.theme_scroll.configure(fg_color=theme.PANEL)
            
        self.back_btn.configure(fg_color=theme.BG_TOP, hover_color=theme.HOVER, corner_radius=theme.RADIUS)
        self.fwd_btn.configure(fg_color=theme.BG_TOP, hover_color=theme.HOVER, corner_radius=theme.RADIUS)
        self._update_nav_buttons()

    def show(self, name, push_history=True):
        if name not in self.nav_buttons:
            return
            
        self.current = name
        self.top_title.configure(text=name)
        
        if push_history:
            self.nav_history = self.nav_history[:self.nav_index + 1]
            if not self.nav_history or self.nav_history[-1] != name:
                self.nav_history.append(name)
            self.nav_index = len(self.nav_history) - 1
            
        self._update_nav_buttons()
        
        for page in self.pages.values():
            page.pack_forget()
            
        for btn_name, btn in self.nav_buttons.items():
            if hasattr(btn, "set_selected"):
                btn.set_selected(btn_name == name)
            else:
                btn.configure(fg_color="transparent", text_color=theme.TEXT)

        page = self._load_page(name)
        if page:
            page.pack(fill="both", expand=True)

    def _queue_bg_update(self, event=None):
        if self._destroying:
            return
        if self._bg_job:
            return
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
        
        try:
            self.save_settings()
        except Exception:
            pass
            
        try:
            stop_player()
        except Exception:
            pass
            
        os._exit(0)

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