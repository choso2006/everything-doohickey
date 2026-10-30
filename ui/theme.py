import customtkinter as ctk
import sys

# --- THEMES ---
# Fixed: Gently contrasting dark theme with a noticeable highlight
DARK = {
    "BG_TOP": "#18181b", "BG_BOTTOM": "#09090b", "BG": "#121214",
    "SIDEBAR": "#111113", "PANEL": "#27272a", "BORDER": "#3f3f46",
    "HOVER": "#3f3f46", "SELECT": "#4338ca", "TEXT": "#f4f4f5",
    "MUTED": "#a1a1aa", "ACCENT": "#6366f1", "ACCENT_HOVER": "#4f46e5", "ERROR": "#ef4444",
}
# Fixed: Crisp light theme with a soft but visible blue highlight
LIGHT = {
    "BG_TOP": "#f8fafc", "BG_BOTTOM": "#e2e8f0", "BG": "#f1f5f9",
    "SIDEBAR": "#f1f5f9", "PANEL": "#ffffff", "BORDER": "#cbd5e1",
    "HOVER": "#e2e8f0", "SELECT": "#bfdbfe", "TEXT": "#0f172a",
    "MUTED": "#64748b", "ACCENT": "#4f46e5", "ACCENT_HOVER": "#4338ca", "ERROR": "#dc2626",
}

# Fixed: True Frutiger Aero (Glossy Blue & Lime Green)
AERO = {
    "BG_TOP": "#d4f0ff", "BG_BOTTOM": "#8ce6c1", "BG": "#b0ebd8",
    "SIDEBAR": "#ffffff", "PANEL": "#f0faff", "BORDER": "#81d4fa",
    "HOVER": "#b3e5fc", "SELECT": "#69f0ae", "TEXT": "#004b6b",
    "MUTED": "#5599bb", "ACCENT": "#00c853", "ACCENT_HOVER": "#009624", "ERROR": "#ff5c5c",
}

PINK = {
    "BG_TOP": "#fdf2f8", "BG_BOTTOM": "#fbcfe8", "BG": "#fce7f3",
    "SIDEBAR": "#fdf2f8", "PANEL": "#ffffff", "BORDER": "#fbcfe8",
    "HOVER": "#fce7f3", "SELECT": "#f472b6", "TEXT": "#831843",
    "MUTED": "#9d174d", "ACCENT": "#ec4899", "ACCENT_HOVER": "#db2777", "ERROR": "#e11d48",
}
AQUA = {
    "BG_TOP": "#ecfeff", "BG_BOTTOM": "#a5f3fc", "BG": "#cffafe",
    "SIDEBAR": "#cffafe", "PANEL": "#ffffff", "BORDER": "#67e8f9",
    "HOVER": "#a5f3fc", "SELECT": "#22d3ee", "TEXT": "#164e63",
    "MUTED": "#0891b2", "ACCENT": "#06b6d4", "ACCENT_HOVER": "#0891b2", "ERROR": "#ef4444",
}
BLUE = {
    "BG_TOP": "#1e3a8a", "BG_BOTTOM": "#0f172a", "BG": "#172554",
    "SIDEBAR": "#0f172a", "PANEL": "#1e293b", "BORDER": "#334155",
    "HOVER": "#334155", "SELECT": "#2563eb", "TEXT": "#e2e8f0",
    "MUTED": "#94a3b8", "ACCENT": "#3b82f6", "ACCENT_HOVER": "#2563eb", "ERROR": "#ef4444",
}
CYBERPUNK = {
    "BG_TOP": "#120024", "BG_BOTTOM": "#000000", "BG": "#0a0014",
    "SIDEBAR": "#05000a", "PANEL": "#280044", "BORDER": "#4a004a",
    "HOVER": "#3a003a", "SELECT": "#7e22ce", "TEXT": "#00ffff",
    "MUTED": "#ff00ff", "ACCENT": "#fcee0a", "ACCENT_HOVER": "#e5d509", "ERROR": "#ff003c",
}
GOLDEN = {
    "BG_TOP": "#fffbeb", "BG_BOTTOM": "#fde68a", "BG": "#fef3c7",
    "SIDEBAR": "#fffbeb", "PANEL": "#ffffff", "BORDER": "#fcd34d",
    "HOVER": "#fef3c7", "SELECT": "#fcd34d", "TEXT": "#451a03",
    "MUTED": "#92400e", "ACCENT": "#d97706", "ACCENT_HOVER": "#b45309", "ERROR": "#dc2626",
}
GREEN = {
    "BG_TOP": "#052e16", "BG_BOTTOM": "#022c22", "BG": "#064e3b",
    "SIDEBAR": "#022c22", "PANEL": "#14532d", "BORDER": "#166534",
    "HOVER": "#166534", "SELECT": "#15803d", "TEXT": "#ecfdf5",
    "MUTED": "#86efac", "ACCENT": "#22c55e", "ACCENT_HOVER": "#16a34a", "ERROR": "#f87171",
}
INFERNO = {
    "BG_TOP": "#450a0a", "BG_BOTTOM": "#000000", "BG": "#2a0505",
    "SIDEBAR": "#1a0000", "PANEL": "#3a0808", "BORDER": "#7f1d1d",
    "HOVER": "#5a0c0c", "SELECT": "#ea580c", "TEXT": "#fef2f2",
    "MUTED": "#fca5a5", "ACCENT": "#f97316", "ACCENT_HOVER": "#ea580c", "ERROR": "#ef4444",
}
ORANGE = {
    "BG_TOP": "#fff7ed", "BG_BOTTOM": "#fed7aa", "BG": "#ffedd5",
    "SIDEBAR": "#fff7ed", "PANEL": "#ffffff", "BORDER": "#fdba74",
    "HOVER": "#ffedd5", "SELECT": "#fdba74", "TEXT": "#431407",
    "MUTED": "#9a3412", "ACCENT": "#ea580c", "ACCENT_HOVER": "#c2410c", "ERROR": "#dc2626",
}
PURPLE = {
    "BG_TOP": "#4c1d95", "BG_BOTTOM": "#2e1065", "BG": "#3b0764",
    "SIDEBAR": "#2e1065", "PANEL": "#5b21b6", "BORDER": "#6b21a8",
    "HOVER": "#6b21a8", "SELECT": "#7e22ce", "TEXT": "#f3e8ff",
    "MUTED": "#d8b4fe", "ACCENT": "#a855f7", "ACCENT_HOVER": "#9333ea", "ERROR": "#f87171",
}
PURPPINK = {
    "BG_TOP": "#4a044e", "BG_BOTTOM": "#2e1065", "BG": "#3b0764",
    "SIDEBAR": "#2e1065", "PANEL": "#701a75", "BORDER": "#86198f",
    "HOVER": "#86198f", "SELECT": "#c026d3", "TEXT": "#fdf4ff",
    "MUTED": "#f0abfc", "ACCENT": "#d946ef", "ACCENT_HOVER": "#c026d3", "ERROR": "#f87171",
}
RED = {
    "BG_TOP": "#7f1d1d", "BG_BOTTOM": "#450a0a", "BG": "#5a0c0c",
    "SIDEBAR": "#450a0a", "PANEL": "#991b1b", "BORDER": "#b91c1c",
    "HOVER": "#b91c1c", "SELECT": "#dc2626", "TEXT": "#fef2f2",
    "MUTED": "#fca5a5", "ACCENT": "#ef4444", "ACCENT_HOVER": "#dc2626", "ERROR": "#fbbf24",
}
WHITE = {
    "BG_TOP": "#ffffff", "BG_BOTTOM": "#e5e7eb", "BG": "#f9fafb",
    "SIDEBAR": "#f9fafb", "PANEL": "#ffffff", "BORDER": "#d1d5db",
    "HOVER": "#f3f4f6", "SELECT": "#e0e7ff", "TEXT": "#111827",
    "MUTED": "#6b7280", "ACCENT": "#4f46e5", "ACCENT_HOVER": "#4338ca", "ERROR": "#ef4444",
}
YELLOW = {
    "BG_TOP": "#fefce8", "BG_BOTTOM": "#fef08a", "BG": "#fef9c3",
    "SIDEBAR": "#fefce8", "PANEL": "#ffffff", "BORDER": "#fde047",
    "HOVER": "#fef9c3", "SELECT": "#fde047", "TEXT": "#422006",
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
    "SIDEBAR": "#000000", "PANEL": "#0a0a0a", "BORDER": "#1a5c1a",
    "HOVER": "#151515", "SELECT": "#2a2a2a", "TEXT": "#39ff14",
    "MUTED": "#cc44cc", "ACCENT": "#ff00ff", "ACCENT_HOVER": "#cc00cc", "ERROR": "#ff0000",
}
BLACK = {
    "BG_TOP": "#000000", "BG_BOTTOM": "#0a0a0a", "BG": "#050505",
    "SIDEBAR": "#000000", "PANEL": "#18181b", "BORDER": "#27272a",
    "HOVER": "#27272a", "SELECT": "#3f3f46", "TEXT": "#ffffff",
    "MUTED": "#a1a1aa", "ACCENT": "#6366f1", "ACCENT_HOVER": "#4f46e5", "ERROR": "#ff3333",
}
MINT = {
    "BG_TOP": "#f0fdf4", "BG_BOTTOM": "#bbf7d0", "BG": "#dcfce7",
    "SIDEBAR": "#f0fdf4", "PANEL": "#ffffff", "BORDER": "#86efac",
    "HOVER": "#dcfce7", "SELECT": "#6ee7b7", "TEXT": "#064e3b",
    "MUTED": "#047857", "ACCENT": "#10b981", "ACCENT_HOVER": "#059669", "ERROR": "#ef4444",
}
LAVENDER = {
    "BG_TOP": "#faf5ff", "BG_BOTTOM": "#e9d8fd", "BG": "#f3e8ff",
    "SIDEBAR": "#faf5ff", "PANEL": "#ffffff", "BORDER": "#d6bcfa",
    "HOVER": "#f3e8ff", "SELECT": "#c4b5fd", "TEXT": "#44337a",
    "MUTED": "#805ad5", "ACCENT": "#9f7aea", "ACCENT_HOVER": "#805ad5", "ERROR": "#e53e3e",
}
MIDNIGHT = {
    "BG_TOP": "#0f172a", "BG_BOTTOM": "#020617", "BG": "#0b1120",
    "SIDEBAR": "#020617", "PANEL": "#1e293b", "BORDER": "#334155",
    "HOVER": "#334155", "SELECT": "#475569", "TEXT": "#f8fafc",
    "MUTED": "#94a3b8", "ACCENT": "#fbbf24", "ACCENT_HOVER": "#f59e0b", "ERROR": "#ef4444",
}
ROSE_GOLD = {
    "BG_TOP": "#fff5f5", "BG_BOTTOM": "#fed7d7", "BG": "#fed7e2",
    "SIDEBAR": "#fff5f5", "PANEL": "#ffffff", "BORDER": "#fbb6ce",
    "HOVER": "#fed7e2", "SELECT": "#f9a8d4", "TEXT": "#521b41",
    "MUTED": "#97266d", "ACCENT": "#b83280", "ACCENT_HOVER": "#97266d", "ERROR": "#c53030",
}
MATRIX = {
    "BG_TOP": "#000000", "BG_BOTTOM": "#000000", "BG": "#050505",
    "SIDEBAR": "#000000", "PANEL": "#0a0a0a", "BORDER": "#003300",
    "HOVER": "#002200", "SELECT": "#005500", "TEXT": "#00ff00",
    "MUTED": "#008800", "ACCENT": "#00ff00", "ACCENT_HOVER": "#00cc00", "ERROR": "#ff0000",
}

PALETTES = {
    "dark": DARK, "light": LIGHT, "aero": AERO,
    "pink": PINK, "aqua": AQUA, "blue": BLUE, "cyberpunk": CYBERPUNK, 
    "golden": GOLDEN, "green": GREEN, "inferno": INFERNO, "orange": ORANGE, "purple": PURPLE,
    "purppink": PURPPINK, "red": RED, "white": WHITE, "yellow": YELLOW,
    "rainbow": RAINBOW, "neon": NEON, "black": BLACK,
    "mint": MINT, "lavender": LAVENDER, "midnight": MIDNIGHT, "rosegold": ROSE_GOLD, "matrix": MATRIX,
}

LIGHT_THEMES = {
    "light", "aero", "pink", "aqua", "golden", "orange", "white", "yellow", "rainbow",
    "mint", "lavender", "rosegold"
}

# GLOBAL DESIGN VARIABLES
_mode = "dark"
RADIUS = 0
BORDER_WIDTH = 1

for _k, _v in DARK.items():
    globals()[_k] = _v


def use(mode):
    global _mode, RADIUS, BORDER_WIDTH
    mode = str(mode).lower()
    if mode not in PALETTES:
        mode = "dark"
    _mode = mode
    
    # Reverted to squared corners for all themes (since sleek is removed)
    RADIUS = 0
    BORDER_WIDTH = 1

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