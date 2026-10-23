import customtkinter as ctk
import tkinter as tk

from core.appdata import load_config
from ui import theme


class SplashScreen(ctk.CTk):
    def __init__(self):
        # Load saved theme BEFORE creating the window, so the splash
        # matches the theme the user picked last time.
        config = load_config()
        theme.use(config.get("theme", "dark"))

        super().__init__(fg_color=theme.BG_TOP)
        self.overrideredirect(True)
        self.geometry("400x250")

        # Center on screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - 400) // 2
        y = (screen_h - 250) // 2
        self.geometry(f"+{x}+{y}")

        self.attributes("-topmost", True)
        self.configure(bg=theme.BG_TOP)

        # Main frame
        frame = ctk.CTkFrame(
            self,
            fg_color=theme.PANEL,
            corner_radius=0,
            border_width=1,
            border_color=theme.BORDER,
        )
        frame.pack(fill="both", expand=True)

        title = ctk.CTkLabel(
            frame,
            text="yo, wait",
            font=theme.font(32, "bold"),
            text_color=theme.TEXT,
        )
        title.pack(pady=(40, 10))

        sub = ctk.CTkLabel(
            frame,
            text="just give it a sec...",
            font=theme.font(13),
            text_color=theme.MUTED,
        )
        sub.pack(pady=(0, 30))

        self.progress = ctk.CTkProgressBar(
            frame,
            width=260,
            height=6,
            corner_radius=0,
            fg_color=theme.BG,
            progress_color=theme.ACCENT,
        )
        self.progress.pack(pady=(0, 20))
        self.progress.set(0)

        self.progress_val = 0.0
        self.animate()

    def animate(self):
        if self.progress_val < 1.0:
            self.progress_val += 0.05
            self.progress.set(self.progress_val)
            self.after(50, self.animate)
        else:
            self.destroy()


def show_splash():
    splash = SplashScreen()
    splash.mainloop()