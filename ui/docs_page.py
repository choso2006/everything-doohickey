import customtkinter as ctk

from core.docs import ALL_TARGETS, DOC_ALLOWED, TARGETS, convert_document, kind_of
from core.tools import HINTS, find_tool
from ui.toolpage import ToolPage
from ui.widgets import note, option_menu, setting_row

ACTIONS = ["Convert"]


class DocsPage(ToolPage):
    ACTIONS = ACTIONS

    def __init__(self, parent, state=None):
        super().__init__(
            parent, "Documents",
            "Word, Excel, PowerPoint and text files to PDF and back.", state,
        )
        self.target_var = self.remember("target", ctk.StringVar(value="PDF"))
        self.build()

    def current_extensions(self):
        return DOC_ALLOWED

    def build_settings(self):
        for child in self.settings.winfo_children():
            child.destroy()

        row = setting_row(self.settings, "Convert to")
        option_menu(row, [t.upper() for t in ALL_TARGETS], self.target_var, width=120).pack(side="left")
        note(self.settings,
             "Works for Word, text, spreadsheet and presentation files. "
             "A text document can become PDF, DOCX, ODT, TXT, RTF or HTML. "
             "A spreadsheet can become PDF, XLSX, ODS, CSV or HTML. A "
             "presentation can become PDF, PPTX or ODP. "
             "This uses LibreOffice running quietly in the background on "
             "your PC, so nothing is uploaded anywhere. The first conversion "
             "after opening the app is slower while LibreOffice starts up. "
             "Fonts missing from your PC can change how a document looks.")

    def make_job(self, files, output):
        if find_tool("soffice") is None:
            raise ValueError(HINTS["soffice"])

        target = self.target_var.get().lower()
        for file in files:
            kind = kind_of(file)
            if target not in TARGETS[kind]:
                allowed = ", ".join(t.upper() for t in TARGETS[kind])
                raise ValueError(
                    f"{file.name} can only be turned into: {allowed}. "
                    "Change the format or remove that file."
                )
        return self.batch_job(
            files, output, convert_document, hooks=True, target=target
        )
