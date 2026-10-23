import customtkinter as ctk
import tkinter as tk
from ui import theme


def label(parent, text, size=13, weight="normal", color=None, **kwargs):
    return ctk.CTkLabel(
        parent, text=text, font=theme.font(size, weight),
        text_color=color or theme.TEXT, anchor="w", **kwargs,
    )


def note(parent, text):
    widget = label(parent, text, 12, color=theme.MUTED, wraplength=270, justify="left")
    widget.pack(fill="x", pady=(8, 0))
    return widget


def card(parent, **kwargs):
    return ctk.CTkFrame(
        parent, fg_color=theme.PANEL, corner_radius=0, **kwargs,
    )


def primary_button(parent, text, command, width=120, **kwargs):
    text_color = theme.get_contrast_text(theme.ACCENT)
    btn = ctk.CTkButton(
        parent, text=text, command=command, width=width, height=36,
        corner_radius=0, font=theme.font(13, "bold"),
        fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
        text_color=text_color, text_color_disabled=theme.MUTED, **kwargs,
    )
    btn._is_primary = True
    return btn


def secondary_button(parent, text, command, width=100, **kwargs):
    return ctk.CTkButton(
        parent, text=text, command=command, width=width, height=34,
        corner_radius=0, font=theme.font(13),
        fg_color=theme.BG, hover_color=theme.HOVER,
        border_width=1, border_color=theme.BORDER,
        text_color=theme.TEXT, text_color_disabled=theme.MUTED, **kwargs,
    )


def small_button(parent, text, command, width=28):
    return ctk.CTkButton(
        parent, text=text, command=command, width=width, height=24,
        corner_radius=0, font=theme.font(14), fg_color="transparent",
        hover_color=theme.HOVER, text_color=theme.MUTED,
    )


def option_menu(parent, values, variable, command=None, **kwargs):
    return ctk.CTkOptionMenu(
        parent, values=list(values), variable=variable, command=command,
        height=34, corner_radius=0,
        font=theme.font(13), dropdown_font=theme.font(13),
        fg_color=theme.BG, button_color=theme.BORDER,
        button_hover_color=theme.HOVER, text_color=theme.TEXT,
        dropdown_fg_color=theme.PANEL, dropdown_hover_color=theme.HOVER,
        dropdown_text_color=theme.TEXT, dynamic_resizing=False, **kwargs,
    )


def entry(parent, variable, **kwargs):
    return ctk.CTkEntry(
        parent, textvariable=variable, height=34, corner_radius=0,
        font=theme.font(13), fg_color=theme.BG,
        border_width=1, border_color=theme.BORDER, text_color=theme.TEXT, **kwargs,
    )


def checkbox(parent, text, variable, command=None, **kwargs):
    return ctk.CTkCheckBox(
        parent, text=text, variable=variable, command=command,
        font=theme.font(13), text_color=theme.TEXT,
        fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
        border_color=theme.MUTED, checkmark_color=theme.get_contrast_text(theme.ACCENT), corner_radius=0,
        checkbox_width=18, checkbox_height=18, **kwargs,
    )


def setting_row(parent, text):
    row = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
    row.pack(fill="x", pady=4)
    label(row, text, 13, color=theme.MUTED, width=84).pack(side="left")
    return row


def slider_row(parent, text, variable, low, high, suffix=""):
    row = setting_row(parent, text)
    value = label(row, "", 13, color=theme.MUTED, width=48)
    value.pack(side="right")

    def refresh(_=None):
        value.configure(text=f"{int(round(variable.get()))}{suffix}")

    ctk.CTkSlider(
        row, from_=low, to=high, number_of_steps=int(high - low),
        variable=variable, command=refresh,
        fg_color=theme.BG, progress_color=theme.ACCENT,
        button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
        corner_radius=0, button_corner_radius=0,
    ).pack(side="left", fill="x", expand=True, padx=(0, 8))
    refresh()
    return row


def shorten(text, limit=60):
    if len(text) <= limit:
        return text
    head = max(8, limit // 3)
    return text[:head] + "..." + text[-(limit - head - 3):]


def read_int(text, name, low, high):
    text = str(text).strip()
    if not text.lstrip("-").isdigit():
        raise ValueError(f"{name} must be a whole number.")
    number = int(text)
    if not low <= number <= high:
        raise ValueError(f"{name} must be between {low} and {high}.")
    return number


def read_float(text, name, low, high):
    try:
        number = float(str(text).strip().replace(",", "."))
    except ValueError:
        raise ValueError(f"{name} must be a number.")
    if not low <= number <= high:
        raise ValueError(f"{name} must be between {low:g} and {high:g}.")
    return number


# --- CUSTOM SQUARE COMPONENTS ---

class SquaredScrollableFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        kwargs.pop('border_width', None)
        kwargs.pop('border_color', None)
        kwargs['corner_radius'] = 0
        super().__init__(master, **kwargs)
        try:
            if hasattr(self, '_scrollbar'):
                self._scrollbar.configure(corner_radius=0, button_corner_radius=0)
        except Exception:
            pass

class SquaredTextbox(ctk.CTkTextbox):
    def __init__(self, master, **kwargs):
        kwargs['corner_radius'] = 0
        super().__init__(master, **kwargs)
        try:
            if hasattr(self, '_scrollbar'):
                self._scrollbar.configure(corner_radius=0, button_corner_radius=0)
        except Exception:
            pass

def textbox(parent, height=110, **kwargs):
    return SquaredTextbox(
        parent, height=height, font=theme.font(13),
        fg_color=theme.BG, border_width=1, border_color=theme.BORDER,
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
        if self.tooltip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2) - 40
        y = self.widget.winfo_rooty() - 30
        
        self.tooltip_window = tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.wm_attributes("-topmost", True)
        
        frame = ctk.CTkFrame(tw, fg_color=theme.PANEL, corner_radius=0, border_width=1, border_color=theme.BORDER)
        frame.pack()
        label = ctk.CTkLabel(frame, text=self.text, font=theme.font(11), text_color=theme.TEXT, height=20)
        label.pack(padx=8, pady=2)

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
        
        frame = ctk.CTkFrame(self, fg_color=theme.PANEL, corner_radius=0, border_width=1, border_color=theme.BORDER)
        frame.pack(fill="both", expand=True)
        
        label(frame, f"{icon} {title}", 14, "bold").pack(anchor="w", padx=12, pady=(10, 2))
        label(frame, message, 12, color=theme.MUTED).pack(anchor="w", padx=12)
        
        self.slide_in()
        
    def slide_in(self):
        self.current_y -= 10
        self.geometry(f"+{self.target_x}+{self.current_y}")
        if self.current_y > self.target_y:
            self.after(10, self.slide_in)
        else:
            self.after(3000, self.slide_out)
            
    def slide_out(self):
        self.current_y += 10
        self.geometry(f"+{self.target_x}+{self.current_y}")
        if self.current_y < self.winfo_screenheight():
            self.after(10, self.slide_out)
        else:
            self.destroy()

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
            self, textvariable=self.entry_var, height=34, corner_radius=0,
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

    def _cancel(self):
        self.destroy()

    def get_input(self):
        self.wait_window()
        return self.result


class Page(ctk.CTkFrame):
    def __init__(self, parent, title, subtitle):
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        label(self, title, 26, "bold").pack(fill="x", padx=32, pady=(24, 0))
        label(self, subtitle, 14, color=theme.MUTED).pack(fill="x", padx=32, pady=(2, 0))