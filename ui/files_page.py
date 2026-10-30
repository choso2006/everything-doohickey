import customtkinter as ctk
from pathlib import Path

from core.files import split_file, join_files
from core.common import clean_name
from ui import theme
from ui.toolpage import ToolPage
from ui.widgets import entry, note, setting_row, read_float

ACTIONS = ["Split File", "Join Files"]

class FilesPage(ToolPage):
    ACTIONS = ACTIONS

    ACTION_DESCRIPTIONS = {
        "Split File": {
            "desc": "Split large files into smaller chunks for easier sharing.",
            "ex": "5 GB video ➔ 5 × 1 GB parts",
            "icon": "✂️",
        },
        "Join Files": {
            "desc": "Join split parts back into the original file.",
            "ex": "part001 + part002 ➔ original file",
            "icon": "🔗",
        },
    }

    def __init__(self, parent, state=None):
        super().__init__(
            parent, "Files", 
            "Split massive files into chunks, or join them back together.", state
        )
        R = self.remember
        self.chunk_size_var = R("chunk_size", ctk.StringVar(value="10"))
        self.join_name_var = R("join_name", ctk.StringVar(value=""))
        self.build()

    def current_extensions(self):
        return () # Accepts ALL files

    def build_settings(self):
        for child in self.settings.winfo_children():
            child.destroy()

        action = self.action_var.get()
        box = self.settings

        if action == "Split File":
            row = setting_row(box, "Chunk size")
            entry(row, self.chunk_size_var, width=80).pack(side="left")
            ctk.CTkLabel(row, text="MB", text_color=theme.MUTED,
                         font=theme.font(13)).pack(side="left", padx=6)
            
            note(box, "Splits each selected file into smaller chunks (e.g., 10 MB each). "
                      "This is perfect for sending large videos or ZIP files through "
                      "Discord, WhatsApp, or email. The chunks will be saved in a "
                      "subfolder named after the original file.")

        else:
            row = setting_row(box, "Output name")
            entry(row, self.join_name_var).pack(side="left", fill="x", expand=True)
            
            note(box, "Select all the parts (part001, part002, etc.) in the list on the "
                      "left. Leave the name blank to automatically restore the original "
                      "filename. They will be joined back into one perfect file.")

    def make_job(self, files, output):
        action = self.action_var.get()

        if action == "Split File":
            mb = read_float(self.chunk_size_var.get(), "Chunk size", 0.1, 50000)
            return self.batch_job(files, output, split_file, hooks=True, chunk_size_mb=mb)

        name = self.join_name_var.get().strip()
        if name:
            name = clean_name(name, "joined_file")
            
        return self.single_job(
            f"Joining {len(files)} parts into one file...",
            lambda: join_files(files, output, output_name=name)
        )