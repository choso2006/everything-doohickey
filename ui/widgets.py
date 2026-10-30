import customtkinter as ctk
import tkinter as tk
from ui import theme
from core.tools import find_tool
from core.common import format_size

KEYS_TO_SHOW = {
    "ImagesPage": {
        "Convert": ["format", "quality"],
        "Compress": ["compress_quality"],
        "Compress to size": ["size_value", "size_unit"],
        "Resize": ["resize_mode", "width", "height", "percent"],
        "Rotate or flip": ["rotate", "flip_h", "flip_v"],
        "Adjust colors": ["brightness", "contrast", "color", "gray"],
        "Watermark": ["mark_text", "mark_position", "mark_size", "mark_opacity"],
        "Make animation": ["anim_format", "anim_ms", "anim_width", "anim_loop"],
    },
    "PdfsPage": {
        "Compress": ["level"],
        "Compress to size": ["target_mb"],
        "Rotate pages": ["rotation"],
        "Page numbers": ["number_pos", "number_start"],
        "PDF to images": ["format", "dpi"],
        "Watermark": ["mark_text", "mark_size", "mark_opacity"],
    },
    "VideoPage": {
        "Convert": ["format", "quality"],
        "Compress": ["quality", "height"],
        "Compress to size": ["target_mb"],
        "Extract audio": ["audio_format", "bitrate"],
        "Merge": ["merge_name", "reencode", "resolution", "fps"],
        "Make a GIF": ["gif_width", "gif_fps"],
        "Change speed": ["speed"],
        "Rotate or flip": ["rotate", "flip_h", "flip_v"],
        "Crop to shape": ["crop_aspect", "crop_mode"],
        "Replace audio": ["mix_audio"],
        "Save a picture": ["picture_format"],
        "Save pictures every few seconds": ["every", "picture_format"],
    },
    "AudioPage": {
        "Convert": ["format", "bitrate"],
        "Merge": ["format", "bitrate", "merge_name"],
        "Change volume": ["db", "normalize"],
        "Change speed": ["speed"],
        "Fade in/out": ["fade_in", "fade_out"],
        "Trim silence": ["silence_db", "silence_min"],
    },
    "DocsPage": {
        "Convert": ["target"]
    }
}

def _darken_color(hex_color, factor=0.2):
    hex_color = hex_color.lstrip('#')
    r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    r, g, b = int(r * factor), int(g * factor), int(b * factor)
    return f"#{r:02x}{g:02x}{b:02x}"

def label(parent, text, size=13, weight="normal", color=None, **kwargs):
    return ctk.CTkLabel(
        parent, text=text, font=theme.font(size, weight),
        text_color=color or theme.TEXT, anchor="w", **kwargs,
    )

class CollapsibleHelp(ctk.CTkFrame):
    def __init__(self, parent, text, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.is_open = False
        
        self.toggle_btn = ctk.CTkButton(
            self, text="ⓘ Show Help", font=theme.font(12), height=24,
            corner_radius=0, # Square rectangle
            fg_color="transparent", hover_color=theme.HOVER, 
            text_color=theme.ACCENT, anchor="w",
            command=self._toggle
        )
        self.toggle_btn.pack(fill="x", pady=(4, 0))
        
        self.text_lbl = label(self, text, 12, color=theme.MUTED, wraplength=270, justify="left")

    def _toggle(self):
        if self.is_open:
            self.text_lbl.pack_forget()
            self.toggle_btn.configure(text="ⓘ Show Help")
            self.is_open = False
        else:
            self.text_lbl.pack(fill="x", pady=(4, 4))
            self.toggle_btn.configure(text="ⓘ Hide Help")
            self.is_open = True

def note(parent, text):
    widget = CollapsibleHelp(parent, text)
    widget.pack(fill="x", pady=(4, 0))
    return widget

def card(parent, **kwargs):
    return ctk.CTkFrame(
        parent, fg_color=theme.PANEL, corner_radius=theme.RADIUS, 
        border_width=theme.BORDER_WIDTH, border_color=theme.BORDER, **kwargs,
    )

def primary_button(parent, text, command, width=120, **kwargs):
    physics = kwargs.pop("physics", False)
    kwargs.setdefault("height", 34)
    text_color = theme.get_contrast_text(theme.ACCENT)
    btn = ctk.CTkButton(
        parent, text=text, width=width,
        corner_radius=theme.RADIUS, font=theme.font(13, "bold"),
        fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
        text_color=text_color, text_color_disabled=theme.MUTED, **kwargs,
    )
    btn._is_primary = True
    
    if physics:
        def _cmd():
            btn.configure(fg_color=theme.ACCENT_HOVER, border_width=2, border_color=theme.TEXT)
            btn.after(150, lambda: btn.configure(fg_color=theme.ACCENT, border_width=0))
            if command: command()
        btn.configure(command=_cmd)
    else:
        btn.configure(command=command)
        
    return btn

def secondary_button(parent, text, command, width=100, **kwargs):
    physics = kwargs.pop("physics", False)
    kwargs.setdefault("height", 32)
    btn = ctk.CTkButton(
        parent, text=text, width=width,
        corner_radius=theme.RADIUS, font=theme.font(13),
        fg_color="transparent", hover_color=theme.HOVER,
        border_width=theme.BORDER_WIDTH, border_color=theme.BORDER,
        text_color=theme.TEXT, text_color_disabled=theme.MUTED, **kwargs,
    )
    
    if physics:
        def _cmd():
            btn.configure(fg_color=theme.HOVER, border_width=2, border_color=theme.TEXT)
            btn.after(150, lambda: btn.configure(fg_color="transparent", border_width=theme.BORDER_WIDTH, border_color=theme.BORDER))
            if command: command()
        btn.configure(command=_cmd)
    else:
        btn.configure(command=command)
        
    return btn

def small_button(parent, text, command, width=28):
    return ctk.CTkButton(
        parent, text=text, command=command, width=width, height=24,
        corner_radius=theme.RADIUS, font=theme.font(14), fg_color="transparent",
        hover_color=theme.HOVER, text_color=theme.MUTED,
    )

class ScrollingLabel(tk.Canvas):
    def __init__(self, master, text, font, text_color, bg_color, **kwargs):
        super().__init__(master, bg=bg_color, highlightthickness=0, height=24, width=10, **kwargs)
        self.text = text
        self.font = font
        self.text_color = text_color
        self._text_id = self.create_text(0, 12, text=self.text, font=self.font, fill=self.text_color, anchor="w")
        self._offset = 0
        self._scrolling = False
        self._width = 0
        self._after_id = None
        
        self.bind("<Configure>", self._on_configure)
        self.bind("<Destroy>", lambda e: self._stop_scroll())

    def _on_configure(self, event):
        self._width = event.width
        self._stop_scroll()
        if self._after_id: self.after_cancel(self._after_id)
        self._after_id = self.after(100, self._check_scroll)

    def _stop_scroll(self):
        self._scrolling = False
        self.coords(self._text_id, 0, 12)

    def _check_scroll(self):
        if not self.winfo_exists(): return
        self.update_idletasks()
        bbox = self.bbox(self._text_id)
        if not bbox: 
            self._after_id = self.after(100, self._check_scroll)
            return
        
        text_width = bbox[2] - bbox[0]

        if text_width > self._width:
            self._scrolling = True
            self._offset = self._width
            self._scroll_loop()
        else:
            self._scrolling = False
            self.coords(self._text_id, 0, 12)

    def _scroll_loop(self):
        if not self._scrolling or not self.winfo_exists(): return
        bbox = self.bbox(self._text_id)
        if not bbox: return
        text_width = bbox[2] - bbox[0]

        self._offset -= 1.25

        if self._offset < -text_width:
            self._offset = self._width
            self._after_id = self.after(600, self._scroll_loop)
        else:
            self.coords(self._text_id, self._offset, 12)
            self._after_id = self.after(15, self._scroll_loop)


class SidebarNavButton(ctk.CTkFrame):
    def __init__(self, master, icon="", text="", command=None, **kwargs):
        kwargs.pop("height", None)
        kwargs.pop("anchor", None)
        kwargs.pop("border_spacing", None)
        
        super().__init__(master, height=36, corner_radius=theme.RADIUS, fg_color="transparent", **kwargs)
        self.pack_propagate(False)
        
        self.command = command
        self._is_selected = False
        
        # Thick colorful accent line on the left (6px)
        self.accent_line = ctk.CTkFrame(self, width=6, height=24, fg_color="transparent", corner_radius=0)
        self.accent_line.place(x=0, rely=0.5, anchor="w")
        
        self.icon_lbl = ctk.CTkLabel(self, text=icon, anchor="w", font=theme.font(14))
        self.icon_lbl.place(x=12, rely=0.5, anchor="w")
        
        self.text_lbl = ctk.CTkLabel(self, text=text, anchor="w", font=theme.font(13))
        self.text_lbl.place(x=48, rely=0.5, anchor="w")
        
        for w in (self, self.icon_lbl, self.text_lbl):
            w.bind("<Button-1>", self._click)
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)
            w.configure(cursor="hand2")
            
    def _click(self, e):
        if self.command: self.command()
        
    def _enter(self, e):
        if not self._is_selected:
            self.configure(fg_color=theme.HOVER)
            self.accent_line.configure(fg_color=theme.ACCENT)
            
    def _leave(self, e):
        if not self._is_selected:
            self.configure(fg_color="transparent")
            self.accent_line.configure(fg_color="transparent")
            
    def set_selected(self, selected):
        self._is_selected = selected
        if selected:
            self.configure(fg_color=theme.SELECT)
            tc = theme.get_contrast_text(theme.SELECT)
            self.icon_lbl.configure(text_color=tc)
            self.text_lbl.configure(text_color=tc)
            self.accent_line.configure(fg_color=theme.ACCENT)
        else:
            self.configure(fg_color="transparent")
            self.icon_lbl.configure(text_color=theme.TEXT)
            self.text_lbl.configure(text_color=theme.TEXT)
            self.accent_line.configure(fg_color="transparent")

    def configure(self, **kwargs):
        if "text" in kwargs: self.text_lbl.configure(text=kwargs.pop("text"))
        if "text_color" in kwargs:
            tc = kwargs.pop("text_color")
            self.icon_lbl.configure(text_color=tc)
            self.text_lbl.configure(text_color=tc)
        if "hover_color" in kwargs: kwargs.pop("hover_color")
        if "corner_radius" in kwargs: kwargs.pop("corner_radius")
        super().configure(**kwargs)


class DropdownItem(tk.Label):
    def __init__(self, master, text, command):
        super().__init__(master, text=text, anchor="w", bg=theme.PANEL, fg=theme.TEXT, font=(theme.FONT_FAMILY, 10))
        self.command = command
        self.configure(padx=10, pady=6)
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.configure(cursor="hand2")
            
    def _click(self, e): self.command()
    def _enter(self, e): self.configure(bg=theme.HOVER)
    def _leave(self, e): self.configure(bg=theme.PANEL)


class CustomDropdown(tk.Frame):
    def __init__(self, master, values, variable, command=None, **kwargs):
        super().__init__(master, height=32, bg=theme.PANEL, highlightthickness=0, **kwargs)
        self.pack_propagate(False)
        self.grid_propagate(False)
        
        self.values = values
        self.variable = variable
        self.command = command
        self._state = "normal"
        self.dropdown = None
        
        self.canvas = tk.Canvas(self, bg=theme.PANEL, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        
        self.variable.trace_add("write", lambda *a: self._redraw())
        self.bind("<Configure>", self._redraw)
        
        for w in (self, self.canvas):
            w.bind("<Button-1>", self._open_menu)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.configure(cursor="hand2")

    def _redraw(self, event=None):
        self.canvas.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w > 1 and h > 1:
            self.canvas.create_rectangle(1, 1, w-1, h-1, outline=theme.BORDER, dash=(4, 4), width=1, tags="border")
            text_val = self.variable.get()
            self.canvas.create_text(10, h/2, text=text_val, anchor="w", fill=theme.TEXT, font=(theme.FONT_FAMILY, 10))
            self.canvas.create_text(w-9, h/2 - 1, text="⏷", anchor="e", fill=theme.TEXT, font=("Segoe UI", 12, "bold"))

    def _on_enter(self, e):
        if self._state == "normal":
            self.canvas.configure(bg=theme.HOVER)
            self._redraw()

    def _on_leave(self, e):
        if self._state == "normal":
            self.canvas.configure(bg=theme.PANEL)
            self._redraw()

    def _open_menu(self, event=None):
        if self._state != "normal": return
        if self.dropdown:
            self._close()
            return

        self.dropdown = tk.Toplevel(self)
        self.dropdown.withdraw()
        self.dropdown.overrideredirect(True)
        self.dropdown.attributes("-topmost", True)
        self.dropdown.configure(bg=theme.BORDER)

        inner_frame = tk.Frame(self.dropdown, bg=theme.PANEL)
        inner_frame.pack(fill="both", expand=True, padx=1, pady=1)

        scroll = SmoothScrollableFrame(inner_frame, fg_color=theme.PANEL, scrollbar_button_color=theme.BORDER, scrollbar_button_hover_color=theme.MUTED, corner_radius=0)
        scroll.pack(fill="both", expand=True)

        def _on_mousewheel(event):
            scroll._parent_canvas.yview_scroll(int(-1 * (event.delta / 120) * 20), "units")
            return "break"

        self.dropdown.bind("<MouseWheel>", _on_mousewheel)
        inner_frame.bind("<MouseWheel>", _on_mousewheel)
        scroll.bind("<MouseWheel>", _on_mousewheel)
        scroll._parent_canvas.bind("<MouseWheel>", _on_mousewheel)

        for v in self.values:
            item = DropdownItem(scroll, text=v, command=lambda val=v: self._select(val))
            item.pack(fill="x", expand=True)
            item.bind("<MouseWheel>", _on_mousewheel)

        self.dropdown.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2 
        w = self.winfo_width()
        if w < 50: w = 200
        h = min(len(self.values) * 30 + 2, 250)
        self.dropdown.geometry(f"{w}x{h}+{x}+{y}")
        self.dropdown.deiconify()
        self.dropdown.lift()
        self.dropdown.after(200, lambda: self.dropdown.bind("<FocusOut>", lambda e: self._close()))
        self.dropdown.focus_force()

    def _select(self, val):
        self.variable.set(val)
        if self.command: self.command(val)
        self._close()

    def _close(self):
        if self.dropdown:
            self.dropdown.destroy()
            self.dropdown = None

    def set(self, value): self.variable.set(value)

    def configure(self, **kwargs):
        if "values" in kwargs: self.values = kwargs.pop("values")
        if "command" in kwargs: self.command = kwargs.pop("command")
        if "state" in kwargs:
            self._state = kwargs.pop("state")
            if self._state == "disabled":
                self.canvas.configure(bg=theme.PANEL, cursor="arrow")
                for w in (self, self.canvas): w.unbind("<Button-1>")
                self._redraw()
            else:
                self.canvas.configure(bg=theme.PANEL, cursor="hand2")
                for w in (self, self.canvas): w.bind("<Button-1>", self._open_menu)
                self._redraw()
        super().configure(**kwargs)


class ActionCard(ctk.CTkFrame):
    def __init__(self, master, action, info, is_current, command):
        super().__init__(master, fg_color=theme.PANEL, corner_radius=theme.RADIUS, 
                         border_width=1, border_color=theme.ACCENT if is_current else theme.BORDER,
                         height=140) # Fixed height prevents squishing
        
        self.command = command
        self.action = action
        self._is_current = is_current
        
        top = ctk.CTkFrame(self, fg_color="transparent", height=36)
        top.pack(fill="x", padx=16, pady=(16, 4))
        top.pack_propagate(False)
        
        icon = info.get("icon", "📄")
        
        ctk.CTkLabel(top, text=icon, font=theme.font(24), anchor="w").place(x=0, rely=0.5, anchor="w")
        ctk.CTkLabel(top, text=action, font=theme.font(16, "bold"), text_color=theme.TEXT, anchor="w").place(x=36, rely=0.5, anchor="w")
        
        desc_lbl = ctk.CTkLabel(self, text=info.get("desc", ""), font=theme.font(12), text_color=theme.MUTED, 
                     wraplength=230, justify="left", anchor="w")
        desc_lbl.pack(fill="x", padx=16, pady=(0, 10))
        self.bind("<Configure>", lambda e: desc_lbl.configure(wraplength=max(10, e.width - 32)))
        
        ex_text = info.get("ex", "")
        if ex_text:
            ex_box = ctk.CTkFrame(self, fg_color=theme.BG, corner_radius=theme.RADIUS, border_width=1, border_color=theme.BORDER)
            ex_box.pack(fill="x", padx=16, pady=(0, 16))
            
            canvas = ScrollingLabel(
                ex_box, 
                text=f"e.g., {ex_text}", 
                font=theme.font(11), 
                text_color=theme.MUTED, 
                bg_color=theme.BG
            )
            canvas.pack(fill="x", padx=8, pady=4)
            
        for w in (self, *self.winfo_children()):
            w.bind("<Button-1>", self._click)
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)
            w.configure(cursor="hand2")
            
        for child in self.winfo_children():
            for subchild in child.winfo_children():
                subchild.bind("<Button-1>", self._click)
                subchild.bind("<Enter>", self._enter)
                subchild.bind("<Leave>", self._leave)
                subchild.configure(cursor="hand2")
                
    def _click(self, e): self.command(self.action)
    def _enter(self, e): 
        self.configure(fg_color=theme.HOVER, border_color=theme.ACCENT)
    def _leave(self, e): 
        self.configure(fg_color=theme.PANEL, border_color=theme.ACCENT if self._is_current else theme.BORDER)


class ActionSelector(ctk.CTkToplevel):
    def __init__(self, parent, current_action, actions_list, descriptions, on_select, page=None):
        super().__init__(parent)
        self.overrideredirect(True)
        self.on_select = on_select
        self.current_action = current_action
        self.parent = parent
        self.page = page

        self.backdrop = tk.Toplevel(parent)
        self.backdrop.overrideredirect(True)
        tint_color = _darken_color(theme.ACCENT, 0.15)
        self.backdrop.configure(bg=tint_color)
        
        self.backdrop.attributes("-alpha", 0.0)
        self.backdrop.bind("<Button-1>", lambda e: self.destroy())

        self.configure(fg_color=tint_color)
        self.attributes("-alpha", 0.0)
        self.transient(parent)
        self.lift()

        self.inner_frame = ctk.CTkFrame(self, fg_color=theme.BG_TOP, corner_radius=theme.RADIUS, border_width=1, border_color=theme.BORDER)
        self.inner_frame.pack(fill="both", expand=True, padx=2, pady=2)

        close_btn = ctk.CTkButton(
            self.inner_frame, text="❌", width=36, height=36, 
            corner_radius=0, fg_color="transparent", hover_color=theme.ERROR, 
            text_color=theme.TEXT, font=theme.font(16),
            command=self.destroy
        )
        close_btn.place(relx=1.0, rely=0.0, x=-16, y=16, anchor="ne")
        close_btn.lift()
        
        ctk.CTkLabel(self.inner_frame, text="CONVERSION & EDITS", font=theme.font(24, "bold"), text_color=theme.TEXT).pack(pady=(20, 10))
        
        scroll = SmoothScrollableFrame(
            self.inner_frame, 
            fg_color=theme.BG_TOP,
            scrollbar_button_color=theme.BORDER,
            scrollbar_button_hover_color=theme.MUTED
        )
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        scroll.grid_columnconfigure(0, weight=1, uniform="col")
        scroll.grid_columnconfigure(1, weight=1, uniform="col")
        scroll.grid_columnconfigure(2, weight=1, uniform="col")

        for idx, action in enumerate(actions_list):
            info = descriptions.get(action, {"desc": "No description available.", "ex": ""})
            card = ActionCard(scroll, action, info, action == current_action, self._pick)
            card.grid(row=idx // 3, column=idx % 3, padx=10, pady=10, sticky="nsew")

        # --- SUMMARY BOX (File Flow left, Info right) ---
        self.summary_frame = ctk.CTkFrame(self.inner_frame, fg_color=theme.PANEL, corner_radius=theme.RADIUS, border_width=1, border_color=theme.BORDER)
        self.summary_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        self.summary_frame.grid_columnconfigure(0, weight=1, uniform="sum")
        self.summary_frame.grid_columnconfigure(1, weight=1, uniform="sum")
        
        # Left Column: Icon, Title & File Flow
        self.left_summary = ctk.CTkFrame(self.summary_frame, fg_color="transparent")
        self.left_summary.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        
        top_row = ctk.CTkFrame(self.left_summary, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 4))
        self.summary_icon = ctk.CTkLabel(top_row, text="📄", font=theme.font(32))
        self.summary_icon.pack(side="left", padx=(0, 12))
        
        right_top = ctk.CTkFrame(top_row, fg_color="transparent")
        right_top.pack(side="left", fill="both", expand=True)
        self.summary_header = ctk.CTkLabel(right_top, text="CONVERSION SUMMARY & PREVIEW", font=theme.font(14, "bold"), text_color=theme.ACCENT)
        self.summary_header.pack(anchor="w")
        self.summary_title = ctk.CTkLabel(right_top, text="", font=theme.font(16, "bold"), text_color=theme.TEXT)
        self.summary_title.pack(anchor="w", pady=(2, 0))
        
        self.flow_frame = ctk.CTkFrame(self.left_summary, fg_color="transparent")
        self.flow_frame.pack(fill="x", pady=(8, 0))
        
        # Right Column: Description, Help & Info
        self.right_summary = ctk.CTkFrame(self.summary_frame, fg_color="transparent")
        self.right_summary.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        
        self.desc_lbl = ctk.CTkLabel(self.right_summary, text="", font=theme.font(12), text_color=theme.MUTED, justify="left", anchor="w", wraplength=300)
        self.desc_lbl.pack(fill="x", pady=(0, 8))
        
        self.help_lbl = ctk.CTkLabel(self.right_summary, text="", font=theme.font(12), text_color=theme.ACCENT, justify="left", anchor="w", wraplength=300)
        # Don't pack it yet
        
        self.info_frame = ctk.CTkFrame(self.right_summary, fg_color="transparent")
        self.info_frame.pack(fill="x")

        self._update_summary(current_action, descriptions)

        self.bind("<Escape>", lambda e: self.destroy())
        
        self.parent_bind_id = self.parent.bind("<Configure>", self._on_resize, add="+")
        self._on_resize()
        
        self._fade_in(0)

    def _on_resize(self, event=None):
        if not self.winfo_exists(): return
        try:
            x = self.parent.winfo_rootx()
            y = self.parent.winfo_rooty()
            w = self.parent.winfo_width()
            h = self.parent.winfo_height()
            
            self.backdrop.geometry(f"{w}x{h}+{x}+{y}")
            
            mw = int(w * 0.9)
            mh = int(h * 0.9)
            mx = x + (w - mw) // 2
            my = y + (h - mh) // 2
            self.geometry(f"{mw}x{mh}+{mx}+{my}")
        except Exception:
            pass

    def _fade_in(self, step=0):
        if not self.winfo_exists(): return
        b_alpha = min(0.75, step * 0.075)
        m_alpha = min(1.0, step * 0.1)
        
        try:
            self.backdrop.attributes("-alpha", b_alpha)
            self.attributes("-alpha", m_alpha)
        except Exception:
            pass
            
        if step < 10:
            self.after(15, lambda: self._fade_in(step + 1))
        else:
            self.focus_force()

    def _pick(self, action):
        self.destroy()
        self.on_select(action)
        
    def _make_chip(self, text, is_output=False):
        chip = ctk.CTkFrame(self.flow_frame, fg_color=theme.PANEL, corner_radius=theme.RADIUS, border_width=1, border_color=theme.ACCENT if is_output else theme.BORDER)
        icon = "✨" if is_output else "📄"
        color = theme.ACCENT if is_output else theme.MUTED
        ctk.CTkLabel(chip, text=icon, font=theme.font(12)).pack(side="left", padx=(6, 2), pady=4)
        ctk.CTkLabel(chip, text=shorten(text, 20), font=theme.font(11), text_color=color).pack(side="left", padx=(0, 6), pady=4)
        return chip

    def _guess_output_name(self, action):
        page_name = self.page.__class__.__name__ if self.page else ""
        files = getattr(self.page, 'files', [])
        orig_ext = files[0].suffix.lower() if files else ""

        if page_name == "ImagesPage":
            if action == "Convert": return f"Output.{self.page.vars['format'].get()}"
            if action == "Make animation": return f"animation.{self.page.vars['anim_format'].get()}"
            return f"Output{orig_ext}" 

        elif page_name == "PdfsPage":
            if action == "PDF to images": return f"Output.{self.page.vars['format'].get()}"
            if action in ("PDF to text", "OCR scanned PDF"): return "Output.txt"
            if action == "Merge": return "Merged.pdf"
            if action == "Images to PDF": return "Output.pdf"
            if action in ("Split into pages", "Extract pictures"): return "Output (folder)"
            return "Output.pdf" 

        elif page_name == "VideoPage":
            if action == "Extract audio": return f"Output.{self.page.vars['audio_format'].get()}"
            if action == "Make a GIF": return "Output.gif"
            if action in ("Save a picture", "Save pictures every few seconds"): return f"Output.{self.page.vars['picture_format'].get()}"
            return "Output.mp4" 

        elif page_name == "AudioPage":
            if action in ("Convert", "Merge"): return f"Output.{self.page.vars['format'].get()}"
            return f"Output{orig_ext or '.mp3'}"

        elif page_name == "DocsPage":
            return f"Output.{self.page.vars['target'].get().lower()}"

        elif page_name == "FilesPage":
            if action == "Split File": return "Output (folder)"
            return f"Output{orig_ext}"

        elif page_name == "BrushesPage":
            if "-> CSP" in action: return "Output.sut"
            if "-> Procreate" in action: return "Output.brush"
            return "Output (folder)"

        return "Output"

    def _update_summary(self, action, descriptions):
        info = descriptions.get(action, {})
        
        self.summary_icon.configure(text=info.get("icon", "📄"))
        self.summary_header.configure(text=f"CONVERSION SUMMARY & PREVIEW (Selected: {action})")
        
        files = getattr(self.page, 'files', []) if self.page else []
        count = len(files)
        
        if count == 0:
            self.summary_title.configure(text="No files selected yet")
        elif "Merge" in action or "Images to PDF" in action:
            self.summary_title.configure(text=f"Combining {count} file{'s' if count != 1 else ''} into 1 file")
        elif "Split" in action:
            self.summary_title.configure(text=f"Splitting {count} file{'s' if count != 1 else ''}")
        else:
            self.summary_title.configure(text=f"Processing {count} file{'s' if count != 1 else ''}")
            
        self.desc_lbl.configure(text=info.get("desc", ""))
        
        help_text = info.get("help", "")
        if help_text:
            self.help_lbl.configure(text=help_text)
            self.help_lbl.pack(fill="x", pady=(0, 8), after=self.desc_lbl)
        else:
            self.help_lbl.pack_forget()
        
        for child in self.flow_frame.winfo_children(): child.destroy()
        for child in self.info_frame.winfo_children(): child.destroy()
        
        # --- LEFT: File Flow ---
        if count > 0:
            for f in files[:2]:
                self._make_chip(f.name, is_output=False).pack(side="left", padx=2)
            if count > 2:
                ctk.CTkLabel(self.flow_frame, text=f"+{count-2}", font=theme.font(11), text_color=theme.MUTED).pack(side="left", padx=4)
                
            ctk.CTkLabel(self.flow_frame, text="➔", font=theme.font(16, "bold"), text_color=theme.ACCENT).pack(side="left", padx=8)
            
            out_name = self._guess_output_name(action)
            self._make_chip(out_name, is_output=True).pack(side="left", padx=2)
        else:
            ctk.CTkLabel(self.flow_frame, text="Add files to see the output preview.", font=theme.font(12), text_color=theme.MUTED).pack(anchor="w")
            
        # --- RIGHT: Info & Warnings ---
        info_lines = []
        
        if count > 0:
            try:
                total_size = sum(f.stat().st_size for f in files)
                info_lines.append(f"Total size: {format_size(total_size)}")
            except Exception:
                pass
                
        page_name = self.page.__class__.__name__ if self.page else ""
        display_keys = KEYS_TO_SHOW.get(page_name, {}).get(action, [])
        
        settings_strs = []
        if self.page and hasattr(self.page, 'vars'):
            for key in display_keys:
                if key in self.page.vars:
                    try:
                        val = self.page.vars[key].get()
                        if isinstance(val, bool): 
                            if val: settings_strs.append(key.replace('_', ' ').title())
                        elif isinstance(val, str) and not val.strip():
                            continue
                        else:
                            settings_strs.append(f"{key.replace('_', ' ').title()}: {val}")
                    except Exception:
                        pass
                        
        if settings_strs:
            info_lines.append(" • ".join(settings_strs))
                        
        warn = ""
        if action == "Merge" and count < 2:
            warn = "⚠️ Needs at least 2 files."
        elif action == "Trim" and count != 1:
            warn = "⚠️ Works on exactly 1 file."
        elif action == "OCR scanned PDF" and not find_tool("tesseract"):
            warn = "⚠️ Tesseract OCR is not installed."
        elif action == "Replace audio" and self.page and hasattr(self.page, 'vars') and not self.page.vars.get('new_audio', {}).get():
            warn = "⚠️ Choose an audio file first."
            
        if info_lines:
            ctk.CTkLabel(self.info_frame, text="\n".join(info_lines), font=theme.font(12), text_color=theme.MUTED, anchor="w", justify="left").pack(fill="x", pady=(0, 4))
            
        if warn:
            ctk.CTkLabel(self.info_frame, text=warn, font=theme.font(12, "bold"), text_color=theme.ERROR, anchor="w").pack(fill="x", pady=(0, 4))

    def destroy(self):
        if hasattr(self, 'parent_bind_id'):
            try:
                self.parent.unbind("<Configure>", self.parent_bind_id)
            except Exception:
                pass
        if hasattr(self, 'backdrop') and self.backdrop and self.backdrop.winfo_exists():
            self.backdrop.destroy()
        super().destroy()


class ActionButton(tk.Frame):
    def __init__(self, master, values, variable, command=None, descriptions=None, page=None, **kwargs):
        super().__init__(master, height=32, bg=theme.PANEL, highlightthickness=0, **kwargs)
        self.pack_propagate(False)
        self.grid_propagate(False)
        
        self.values = values
        self.variable = variable
        self.command = command
        self.descriptions = descriptions or {}
        self.page = page
        self._state = "normal"
        
        self.canvas = tk.Canvas(self, bg=theme.PANEL, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        
        self.variable.trace_add("write", lambda *a: self._redraw())
        self.bind("<Configure>", self._redraw)
        
        for w in (self, self.canvas):
            w.bind("<Button-1>", self._open_modal)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.configure(cursor="hand2")

    def _redraw(self, event=None):
        self.canvas.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w > 1 and h > 1:
            self.canvas.create_rectangle(1, 1, w-1, h-1, outline=theme.BORDER, dash=(4, 4), width=1, tags="border")
            text_val = self.variable.get()
            self.canvas.create_text(10, h/2, text=text_val, anchor="w", fill=theme.TEXT, font=(theme.FONT_FAMILY, 10))
            self.canvas.create_text(w-9, h/2 - 1, text="⏷", anchor="e", fill=theme.TEXT, font=("Segoe UI", 12, "bold"))

    def _on_enter(self, e):
        if self._state == "normal":
            self.canvas.configure(bg=theme.HOVER)
            self._redraw()

    def _on_leave(self, e):
        if self._state == "normal":
            self.canvas.configure(bg=theme.PANEL)
            self._redraw()

    def _open_modal(self, event=None):
        if self._state != "normal": return
        ActionSelector(self.winfo_toplevel(), self.variable.get(), self.values, self.descriptions, self._select, page=self.page)

    def _select(self, val):
        self.variable.set(val)
        if self.command: self.command(val)

    def set(self, value): self.variable.set(value)

    def configure(self, **kwargs):
        if "values" in kwargs: self.values = kwargs.pop("values")
        if "command" in kwargs: self.command = kwargs.pop("command")
        if "state" in kwargs:
            self._state = kwargs.pop("state")
            if self._state == "disabled":
                self.canvas.configure(bg=theme.PANEL, cursor="arrow")
                for w in (self, self.canvas): w.unbind("<Button-1>")
                self._redraw()
            else:
                self.canvas.configure(bg=theme.PANEL, cursor="hand2")
                for w in (self, self.canvas): w.bind("<Button-1>", self._open_modal)
                self._redraw()
        super().configure(**kwargs)


def option_menu(parent, values, variable, command=None, **kwargs):
    return CustomDropdown(parent, values=values, variable=variable, command=command, **kwargs)

def action_button(parent, values, variable, command=None, descriptions=None, page=None, **kwargs):
    return ActionButton(parent, values=values, variable=variable, command=command, descriptions=descriptions, page=page, **kwargs)

def entry(parent, variable, **kwargs):
    return ctk.CTkEntry(
        parent, textvariable=variable, height=32, corner_radius=theme.RADIUS,
        font=theme.font(13), fg_color=theme.BG,
        border_width=theme.BORDER_WIDTH, border_color=theme.BORDER, text_color=theme.TEXT, **kwargs,
    )

def checkbox(parent, text, variable, command=None, **kwargs):
    return ctk.CTkCheckBox(
        parent, text=text, variable=variable, command=command,
        font=theme.font(13), text_color=theme.TEXT,
        fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
        border_color=theme.BORDER, 
        checkmark_color=theme.get_contrast_text(theme.ACCENT), corner_radius=theme.RADIUS,
        checkbox_width=18, checkbox_height=18, **kwargs,
    )

def setting_row(parent, text):
    row = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
    row.pack(fill="x", pady=6)
    label(row, text, 13, color=theme.MUTED, width=84).pack(side="left")
    return row

def slider_row(parent, text, variable, low, high, suffix=""):
    row = setting_row(parent, text)
    value = label(row, "", 13, color=theme.MUTED, width=48)
    value.pack(side="right")
    def refresh(_=None): value.configure(text=f"{int(round(variable.get()))}{suffix}")
    ctk.CTkSlider(
        row, from_=low, to=high, number_of_steps=int(high - low),
        variable=variable, command=refresh,
        fg_color=theme.BORDER, progress_color=theme.ACCENT,
        button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
        corner_radius=0, button_corner_radius=0, height=16, button_length=16
    ).pack(side="left", fill="x", expand=True, padx=(0, 8))
    refresh()
    return row

def shorten(text, limit=60):
    if len(text) <= limit: return text
    head = max(8, limit // 3)
    return text[:head] + "..." + text[-(limit - head - 3):]

def read_int(text, name, low, high):
    text = str(text).strip()
    if not text.lstrip("-").isdigit(): raise ValueError(f"{name} must be a whole number.")
    number = int(text)
    if not low <= number <= high: raise ValueError(f"{name} must be between {low} and {high}.")
    return number

def read_float(text, name, low, high):
    try: number = float(str(text).strip().replace(",", "."))
    except ValueError: raise ValueError(f"{name} must be a number.")
    if not low <= number <= high: raise ValueError(f"{name} must be between {low:g} and {high:g}.")
    return number

class SmoothScrollableFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        kwargs.pop('border_width', None)
        kwargs.pop('border_color', None)
        kwargs['corner_radius'] = theme.RADIUS
        super().__init__(master, **kwargs)
        try:
            if hasattr(self, '_scrollbar'):
                self._scrollbar.configure(width=14, corner_radius=theme.RADIUS, button_corner_radius=theme.RADIUS)
        except Exception: pass

SquaredScrollableFrame = SmoothScrollableFrame

class SmoothTextbox(ctk.CTkTextbox):
    def __init__(self, master, **kwargs):
        kwargs['corner_radius'] = theme.RADIUS
        super().__init__(master, **kwargs)
        try:
            if hasattr(self, '_scrollbar'):
                self._scrollbar.configure(width=14, corner_radius=theme.RADIUS, button_corner_radius=theme.RADIUS)
        except Exception: pass

SquaredTextbox = SmoothTextbox

def textbox(parent, height=110, **kwargs):
    return SmoothTextbox(
        parent, height=height, font=theme.font(13),
        fg_color=theme.BG, border_width=theme.BORDER_WIDTH, border_color=theme.BORDER,
        text_color=theme.TEXT, **kwargs,
    )

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text: return
        x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2) - 40
        y = self.widget.winfo_rooty() - 30
        self.tooltip_window = tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.wm_attributes("-topmost", True)
        frame = ctk.CTkFrame(tw, fg_color=theme.PANEL, corner_radius=theme.RADIUS, border_width=1, border_color=theme.BORDER)
        frame.pack()
        ctk.CTkLabel(frame, text=self.text, font=theme.font(11), text_color=theme.TEXT, height=20).pack(padx=8, pady=2)
    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class ToastNotification(ctk.CTkToplevel):
    def __init__(self, parent, title, message, icon="✅"):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry("320x80")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.target_x = screen_w - 340
        self.target_y = screen_h - 120
        self.current_y = screen_h
        self.geometry(f"320x80+{self.target_x}+{self.current_y}")
        self.configure(bg=theme.PANEL)
        frame = ctk.CTkFrame(self, fg_color=theme.PANEL, corner_radius=theme.RADIUS, border_width=1, border_color=theme.BORDER)
        frame.pack(fill="both", expand=True)
        label(frame, f"{icon} {title}", 14, "bold").pack(anchor="w", padx=12, pady=(10, 2))
        label(frame, message, 12, color=theme.MUTED).pack(anchor="w", padx=12)
        self.slide_in()
    def slide_in(self):
        self.current_y -= 10
        self.geometry(f"+{self.target_x}+{self.current_y}")
        if self.current_y > self.target_y: self.after(10, self.slide_in)
        else: self.after(3000, self.slide_out)
    def slide_out(self):
        self.current_y += 10
        self.geometry(f"+{self.target_x}+{self.current_y}")
        if self.current_y < self.winfo_screenheight(): self.after(10, self.slide_out)
        else: self.destroy()

class SquaredInputDialog(ctk.CTkToplevel):
    def __init__(self, parent, title="Input", text="Enter value:"):
        super().__init__(parent)
        self.title(title)
        self.geometry("320x180")
        self.configure(fg_color=theme.BG_TOP)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.result = None
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 320) // 2
        y = (self.winfo_screenheight() - 180) // 2
        self.geometry(f"+{x}+{y}")
        self.entry_var = ctk.StringVar()
        label(self, text, 13).pack(pady=(24, 8))
        self.entry = ctk.CTkEntry(
            self, textvariable=self.entry_var, height=34, corner_radius=theme.RADIUS,
            font=theme.font(13), fg_color=theme.BG, border_width=1,
            border_color=theme.BORDER, text_color=theme.TEXT
        )
        self.entry.pack(fill="x", padx=24, pady=4)
        self.entry.bind("<Return>", lambda e: self._ok())
        btn_row = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        btn_row.pack(fill="x", padx=24, pady=(16, 16))
        primary_button(btn_row, "OK", self._ok, width=100).pack(side="right")
        secondary_button(btn_row, "Cancel", self._cancel, width=100).pack(side="right", padx=8)
        self.after(100, self.entry.focus)
    def _ok(self):
        self.result = self.entry_var.get()
        self.destroy()
    def _cancel(self): self.destroy()
    def get_input(self):
        self.wait_window()
        return self.result

class DashedSeparator(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", height=1, **kwargs)
        self.canvas = tk.Canvas(self, height=1, highlightthickness=0, bg=theme.PANEL)
        self.canvas.pack(fill="x", expand=True, padx=16, pady=12)
        self.bind("<Configure>", self._draw_separator)
        
    def _draw_separator(self, event=None):
        self.canvas.delete("all")
        w = self.winfo_width()
        if w > 1: self.canvas.create_line(0, 0, w, 0, dash=(4, 4), fill=theme.BORDER)

class Page(ctk.CTkFrame):
    def __init__(self, parent, title, subtitle):
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        label(self, title, 24, "bold").pack(fill="x", padx=32, pady=(10, 0))
        label(self, subtitle, 13, color=theme.MUTED).pack(fill="x", padx=32, pady=(0, 0))