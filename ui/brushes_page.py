from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.brushes import (
    BRUSH_ALLOWED, SUT_ALLOWED, describe_brush,
    extract_brush, extract_brushset, extract_sut_textures,
)
from core.brush_converter import convert_csp_to_procreate, convert_procreate_to_csp_sut
from ui import theme
from ui.toolpage import ToolPage
from ui.widgets import entry, note, secondary_button, setting_row, shorten

ACTIONS = [
    "Procreate -> Textures",
    "Procreate -> CSP (.sut)",
    "CSP -> Procreate (.brush)",
    "CSP -> Textures",
]


class BrushesPage(ToolPage):
    ACTIONS = ACTIONS

    ACTION_DESCRIPTIONS = {
        "Procreate -> Textures": {
            "desc": "Extract the exact brush tip textures and translated settings from Procreate.",
            "ex": "Get Shape.png + settings.txt from .brushset files",
            "icon": "🖌️",
        },
        "Procreate -> CSP (.sut)": {
            "desc": "Convert Procreate brushes directly into Clip Studio Paint .sut files.",
            "ex": "Turn a Procreate pen into a native CSP brush",
            "icon": "🎨",
        },
        "CSP -> Procreate (.brush)": {
            "desc": "Convert Clip Studio Paint .sut brushes directly into Procreate .brush files.",
            "ex": "Turn a CSP watercolor brush into a Procreate brush",
            "icon": "🖌️",
        },
        "CSP -> Textures": {
            "desc": "Extract raw brush tip images and settings from Clip Studio .sut files.",
            "ex": "Get raw texture images and settings from CSP files",
            "icon": "🖼️",
        },
    }

    def __init__(self, parent, state=None):
        super().__init__(
            parent, "Brushes",
            "Universal brush converter (Procreate <-> Clip Studio Paint).", state,
        )
        self.template_var = self.remember("sut_template", ctk.StringVar(value=""))
        
        if not self.template_var.get() and Path("template.sut").exists():
            self.template_var.set(str(Path("template.sut").absolute()))
            
        self.build()

    def current_extensions(self):
        action = self.action_var.get()
        if action.startswith("CSP"):
            return SUT_ALLOWED
        return BRUSH_ALLOWED

    def pick_template(self):
        path = filedialog.askopenfilename(
            title="Choose a Clip Studio brush to use as the template",
            filetypes=[("Clip Studio brush", "*.sut"), ("All files", "*.*")],
        )
        if path:
            self.template_var.set(path)
            self.set_status(f"Template: {Path(path).name}")

    def build_settings(self):
        for child in self.settings.winfo_children():
            child.destroy()

        action = self.action_var.get()
        box = self.settings

        if action == "Procreate -> Textures":
            note(box,
                 "Extracts the raw tip and texture images from Procreate .brush/.brushset files.\n\n"
                 "Each brush gets a folder containing:\n"
                 "  - Shape.png: the exact tip texture\n"
                 "  - settings.txt: Procreate values translated to CSP terms\n\n"
                 "If you drop a .brushset, you also get a master summary file.")
            return

        if action == "CSP -> Textures":
            note(box,
                 "Extracts the raw tip images from Clip Studio .sut files.\n\n"
                 "Each brush gets a folder containing:\n"
                 "  - Shape.png: the brush tip\n"
                 "  - settings.txt: CSP spacing and opacity values\n\n"
                 "Use this if you want to rebuild the brush manually in another app.")
            return

        if action == "CSP -> Procreate (.brush)":
            note(box,
                 "Converts Clip Studio Paint .sut brushes into Procreate .brush files.\n\n"
                 "This extracts the brush tip and standard settings from the CSP database "
                 "and builds a native Procreate brush. Complex dual-brush or wet-mix "
                 "settings cannot be transferred and will be simplified.\n\n"
                 "Drag the resulting .brush file into Procreate on your iPad.")
            return

        # Procreate -> CSP (.sut) requires a template
        row = setting_row(box, "Template")
        template_entry = entry(row, self.template_var)
        template_entry.pack(side="left", fill="x", expand=True)
        secondary_button(row, "Choose", self.pick_template, width=80).pack(
            side="left", padx=(6, 0)
        )

        if self.template_var.get():
            label_text = shorten(Path(self.template_var.get()).name, 40)
        else:
            label_text = "none chosen"
        ctk.CTkLabel(
            box, text=label_text, font=theme.font(12), text_color=theme.MUTED,
        ).pack(anchor="w", pady=(4, 0))

        note(box,
             "How to make the template (once):\n"
             "  1. Open Clip Studio Paint.\n"
             "  2. Right-click any pen in the Sub Tool palette.\n"
             "  3. Export as .sut and save it somewhere.\n"
             "  4. Press Choose above and pick that file.\n\n"
             "Every converted brush uses that template's pressure curves, "
             "spacing and blending, with the Procreate tip texture swapped in. "
             "That's why the result always opens in Clip Studio - every internal "
             "field comes from a real CSP file. Use settings.txt to fine-tune "
             "spacing and opacity afterwards.")

    def make_job(self, files, output):
        action = self.action_var.get()

        if action == "Procreate -> Textures":
            return self.batch_job(files, output, self._extract_procreate, hooks=True)

        if action == "CSP -> Textures":
            return self.batch_job(files, output, extract_sut_textures, hooks=True)

        if action == "CSP -> Procreate (.brush)":
            return self.batch_job(files, output, convert_csp_to_procreate, hooks=True)

        # Procreate -> CSP (.sut)
        template = self.template_var.get().strip()
        if not template or not Path(template).is_file():
            raise ValueError(
                "Choose a Clip Studio template .sut first. Export any brush "
                "from Clip Studio Paint and pick that file."
            )
        return self.batch_job(
            files, output, convert_procreate_to_csp_sut, hooks=True, template_sut_path=template
        )

    def _extract_procreate(self, path, output_folder, progress=None, cancel=None):
        if path.suffix.lower() == ".brushset":
            extract_brushset(path, output_folder, progress=progress, cancel=cancel)
        else:
            extract_brush(path, output_folder, progress=progress, cancel=cancel)
        return path

    def done_message(self, result):
        if "-> CSP" in self.job_action:
            total = sum(len(x) if isinstance(x, list) else 1 for x in result.done)
            return f"Done. Made {total} Clip Studio brush file(s)."
        if "-> Procreate" in self.job_action:
            return f"Done. Made {len(result.done)} Procreate brush file(s)."
        return super().done_message(result)