import customtkinter as ctk
import sys

DARK = {
    "BG_TOP": "#1e1e21", "BG_BOTTOM": "#121214", "BG": "#18181a",
    "SIDEBAR": "#151517", "PANEL": "#242427", "BORDER": "#303034",
    "HOVER": "#2a2a2e", "SELECT": "#2c3b38", "TEXT": "#e8e8e8",
    "MUTED": "#8c8c93", "ACCENT": "#3f8f84", "ACCENT_HOVER": "#357a70", "ERROR": "#d0645a",
}
LIGHT = {
    "BG_TOP": "#f8f8fa", "BG_BOTTOM": "#e4e4eb", "BG": "#eeeeef",
    "SIDEBAR": "#e8e8ec", "PANEL": "#ffffff", "BORDER": "#d0d0d6",
    "HOVER": "#ececef", "SELECT": "#d4ece6", "TEXT": "#1a1a1c",
    "MUTED": "#6a6a72", "ACCENT": "#2f7d72", "ACCENT_HOVER": "#256359", "ERROR": "#b8463c",
}
PINK = {
    "BG_TOP": "#fff0f7", "BG_BOTTOM": "#ffd1e8", "BG": "#ffe1f0",
    "SIDEBAR": "#ffd9eb", "PANEL": "#ffffff", "BORDER": "#ffb3d9",
    "HOVER": "#ffcce6", "SELECT": "#ff99cc", "TEXT": "#4d0033",
    "MUTED": "#a3668f", "ACCENT": "#ff3399", "ACCENT_HOVER": "#cc0066", "ERROR": "#e6005c",
}
AERO = {
    "BG_TOP": "#d4f0ff", "BG_BOTTOM": "#8ce6c1", "BG": "#b0ebd8",
    "SIDEBAR": "#ffffff", "PANEL": "#f0faff", "BORDER": "#81d4fa",
    "HOVER": "#b3e5fc", "SELECT": "#69f0ae", "TEXT": "#004b6b",
    "MUTED": "#5599bb", "ACCENT": "#00c853", "ACCENT_HOVER": "#009624", "ERROR": "#ff5c5c",
}
AQUA = {
    "BG_TOP": "#e0ffff", "BG_BOTTOM": "#00ced1", "BG": "#b0e0e6",
    "SIDEBAR": "#afeeee", "PANEL": "#ffffff", "BORDER": "#48d1cc",
    "HOVER": "#40e0d0", "SELECT": "#00fa9a", "TEXT": "#003333",
    "MUTED": "#008b8b", "ACCENT": "#00bfff", "ACCENT_HOVER": "#1e90ff", "ERROR": "#ff4500",
}
BLUE = {
    "BG_TOP": "#1e3a8a", "BG_BOTTOM": "#0f172a", "BG": "#172554",
    "SIDEBAR": "#1e293b", "PANEL": "#0f172a", "BORDER": "#334155",
    "HOVER": "#334155", "SELECT": "#1d4ed8", "TEXT": "#e2e8f0",
    "MUTED": "#94a3b8", "ACCENT": "#3b82f6", "ACCENT_HOVER": "#2563eb", "ERROR": "#ef4444",
}
CYBERPUNK = {
    "BG_TOP": "#2b0033", "BG_BOTTOM": "#000000", "BG": "#1a0022",
    "SIDEBAR": "#110015", "PANEL": "#220030", "BORDER": "#4a004a",
    "HOVER": "#3a003a", "SELECT": "#550055", "TEXT": "#00ffff",
    "MUTED": "#ff00ff", "ACCENT": "#fcee0a", "ACCENT_HOVER": "#ff00ff", "ERROR": "#ff003c",
}
GOLDEN = {
    "BG_TOP": "#fffbeb", "BG_BOTTOM": "#fcd34d", "BG": "#fde68a",
    "SIDEBAR": "#fef3c7", "PANEL": "#ffffff", "BORDER": "#fbbf24",
    "HOVER": "#fcd34d", "SELECT": "#f59e0b", "TEXT": "#451a03",
    "MUTED": "#92400e", "ACCENT": "#d97706", "ACCENT_HOVER": "#b45309", "ERROR": "#dc2626",
}
GREEN = {
    "BG_TOP": "#064e3b", "BG_BOTTOM": "#022c22", "BG": "#043b2b",
    "SIDEBAR": "#022c22", "PANEL": "#064e3b", "BORDER": "#047857",
    "HOVER": "#065f46", "SELECT": "#059669", "TEXT": "#ecfdf5",
    "MUTED": "#6ee7b7", "ACCENT": "#10b981", "ACCENT_HOVER": "#059669", "ERROR": "#f87171",
}
INFERNO = {
    "BG_TOP": "#450a0a", "BG_BOTTOM": "#000000", "BG": "#2a0505",
    "SIDEBAR": "#1a0000", "PANEL": "#3a0808", "BORDER": "#7f1d1d",
    "HOVER": "#5a0c0c", "SELECT": "#991b1b", "TEXT": "#fef2f2",
    "MUTED": "#fca5a5", "ACCENT": "#f97316", "ACCENT_HOVER": "#ea580c", "ERROR": "#ef4444",
}
ORANGE = {
    "BG_TOP": "#fff7ed", "BG_BOTTOM": "#fed7aa", "BG": "#ffedd5",
    "SIDEBAR": "#ffedd5", "PANEL": "#ffffff", "BORDER": "#fdba74",
    "HOVER": "#fed7aa", "SELECT": "#f97316", "TEXT": "#431407",
    "MUTED": "#9a3412", "ACCENT": "#ea580c", "ACCENT_HOVER": "#c2410c", "ERROR": "#dc2626",
}
PURPLE = {
    "BG_TOP": "#4c1d95", "BG_BOTTOM": "#2e1065", "BG": "#3b0764",
    "SIDEBAR": "#2e1065", "PANEL": "#4c1d95", "BORDER": "#6b21a8",
    "HOVER": "#581c87", "SELECT": "#7e22ce", "TEXT": "#f3e8ff",
    "MUTED": "#d8b4fe", "ACCENT": "#a855f7", "ACCENT_HOVER": "#9333ea", "ERROR": "#f87171",
}
PURPPINK = {
    "BG_TOP": "#4a044e", "BG_BOTTOM": "#2e1065", "BG": "#3b0764",
    "SIDEBAR": "#2e1065", "PANEL": "#4a044e", "BORDER": "#86198f",
    "HOVER": "#701a75", "SELECT": "#a21caf", "TEXT": "#fdf4ff",
    "MUTED": "#f0abfc", "ACCENT": "#d946ef", "ACCENT_HOVER": "#c026d3", "ERROR": "#f87171",
}
RED = {
    "BG_TOP": "#7f1d1d", "BG_BOTTOM": "#450a0a", "BG": "#5a0c0c",
    "SIDEBAR": "#450a0a", "PANEL": "#7f1d1d", "BORDER": "#991b1b",
    "HOVER": "#5a0c0c", "SELECT": "#b91c1c", "TEXT": "#fef2f2",
    "MUTED": "#fca5a5", "ACCENT": "#ef4444", "ACCENT_HOVER": "#dc2626", "ERROR": "#fbbf24",
}
WHITE = {
    "BG_TOP": "#ffffff", "BG_BOTTOM": "#f3f4f6", "BG": "#f9fafb",
    "SIDEBAR": "#f3f4f6", "PANEL": "#ffffff", "BORDER": "#e5e7eb",
    "HOVER": "#f3f4f6", "SELECT": "#e0e7ff", "TEXT": "#111827",
    "MUTED": "#6b7280", "ACCENT": "#4f46e5", "ACCENT_HOVER": "#4338ca", "ERROR": "#ef4444",
}
YELLOW = {
    "BG_TOP": "#fefce8", "BG_BOTTOM": "#fef08a", "BG": "#fef9c3",
    "SIDEBAR": "#fef9c3", "PANEL": "#ffffff", "BORDER": "#fde047",
    "HOVER": "#fef08a", "SELECT": "#eab308", "TEXT": "#422006",
    "MUTED": "#854d0e", "ACCENT": "#ca8a04", "ACCENT_HOVER": "#a16207", "ERROR": "#dc2626",
}
RAINBOW = {
    "BG_TOP": "#ff9a9e", "BG_BOTTOM": "#a1c4fd", "BG": "#fbc2eb",
    "SIDEBAR": "#ffecd2", "PANEL": "#ffffff", "BORDER": "#ffb6c1",
    "HOVER": "#ffc0cb", "SELECT": "#ff1493", "TEXT": "#1e1b4b",
    "MUTED": "#8b4513", "ACCENT": "#ff0844", "ACCENT_HOVER": "#ffb199", "ERROR": "#dc143c",
}
NEON = {
    "BG_TOP": "#000000", "BG_BOTTOM": "#050505", "BG": "#050505",
    "SIDEBAR": "#000000", "PANEL": "#0a0a0a",
    "BORDER": "#1a5c1a",
    "HOVER": "#151515", "SELECT": "#2a2a2a", "TEXT": "#39ff14",
    "MUTED": "#cc44cc", "ACCENT": "#ff00ff", "ACCENT_HOVER": "#cc00cc", "ERROR": "#ff0000",
}
BLACK = {
    "BG_TOP": "#000000", "BG_BOTTOM": "#0a0a0a", "BG": "#050505",
    "SIDEBAR": "#000000", "PANEL": "#111111", "BORDER": "#222222",
    "HOVER": "#1a1a1a", "SELECT": "#2a2a2a", "TEXT": "#ffffff",
    "MUTED": "#888888", "ACCENT": "#555555", "ACCENT_HOVER": "#777777", "ERROR": "#ff3333",
}
MINT = {
    "BG_TOP": "#e6fffa", "BG_BOTTOM": "#81e6d9", "BG": "#b2f5ea",
    "SIDEBAR": "#ffffff", "PANEL": "#ffffff", "BORDER": "#4fd1c5",
    "HOVER": "#b2f5ea", "SELECT": "#38b2ac", "TEXT": "#234e52",
    "MUTED": "#319795", "ACCENT": "#38b2ac", "ACCENT_HOVER": "#319795", "ERROR": "#e53e3e",
}
LAVENDER = {
    "BG_TOP": "#faf5ff", "BG_BOTTOM": "#e9d8fd", "BG": "#f3e8ff",
    "SIDEBAR": "#ffffff", "PANEL": "#ffffff", "BORDER": "#d6bcfa",
    "HOVER": "#e9d8fd", "SELECT": "#b794f4", "TEXT": "#44337a",
    "MUTED": "#805ad5", "ACCENT": "#9f7aea", "ACCENT_HOVER": "#805ad5", "ERROR": "#e53e3e",
}
MIDNIGHT = {
    "BG_TOP": "#0f172a", "BG_BOTTOM": "#020617", "BG": "#0b1120",
    "SIDEBAR": "#020617", "PANEL": "#1e293b", "BORDER": "#334155",
    "HOVER": "#1e293b", "SELECT": "#475569", "TEXT": "#f8fafc",
    "MUTED": "#94a3b8", "ACCENT": "#fbbf24", "ACCENT_HOVER": "#f59e0b", "ERROR": "#ef4444",
}
ROSE_GOLD = {
    "BG_TOP": "#fff5f5", "BG_BOTTOM": "#fed7d7", "BG": "#fed7e2",
    "SIDEBAR": "#ffffff", "PANEL": "#ffffff", "BORDER": "#fbb6ce",
    "HOVER": "#fbb6ce", "SELECT": "#ed64a6", "TEXT": "#521b41",
    "MUTED": "#97266d", "ACCENT": "#b83280", "ACCENT_HOVER": "#97266d", "ERROR": "#c53030",
}
MATRIX = {
    "BG_TOP": "#000000", "BG_BOTTOM": "#000000", "BG": "#050505",
    "SIDEBAR": "#000000", "PANEL": "#0a0a0a", "BORDER": "#003300",
    "HOVER": "#002200", "SELECT": "#005500", "TEXT": "#00ff00",
    "MUTED": "#008800", "ACCENT": "#00ff00", "ACCENT_HOVER": "#00cc00", "ERROR": "#ff0000",
}

PALETTES = {
    "dark": DARK, "light": LIGHT, "pink": PINK, "aero": AERO,
    "aqua": AQUA, "blue": BLUE, "cyberpunk": CYBERPUNK, "golden": GOLDEN,
    "green": GREEN, "inferno": INFERNO, "orange": ORANGE, "purple": PURPLE,
    "purppink": PURPPINK, "red": RED, "white": WHITE, "yellow": YELLOW,
    "rainbow": RAINBOW, "neon": NEON, "black": BLACK,
    "mint": MINT, "lavender": LAVENDER, "midnight": MIDNIGHT, "rosegold": ROSE_GOLD, "matrix": MATRIX,
}

LIGHT_THEMES = {
    "light", "pink", "aero", "aqua", "golden", "orange", "white", "yellow", "rainbow",
    "mint", "lavender", "rosegold"
}

_mode = "dark"

for _k, _v in DARK.items():
    globals()[_k] = _v


def use(mode):
    global _mode
    mode = str(mode).lower()
    if mode not in PALETTES:
        mode = "dark"
    _mode = mode
    for key, value in PALETTES[_mode].items():
        globals()[key] = value


def current_mode():
    return _mode


def is_dark_mode(mode):
    return mode not in LIGHT_THEMES


def get_contrast_text(hex_color):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminance > 0.6 else "#ffffff"


if sys.platform == "darwin":
    FONT_FAMILY = "SF Pro Display"
elif sys.platform == "win32":
    FONT_FAMILY = "Segoe UI"
else:
    FONT_FAMILY = "Helvetica"


def font(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)