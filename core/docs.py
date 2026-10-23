import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from core.appdata import data_dir
from core.common import Cancelled, format_size, unique_path
from core.media import NO_WINDOW
from core.tools import require_tool

WRITER = (".doc", ".docx", ".odt", ".rtf", ".txt", ".html", ".htm", ".wpd", ".wps")
CALC = (".xls", ".xlsx", ".ods", ".csv")
IMPRESS = (".ppt", ".pptx", ".odp", ".pps", ".ppsx")
DOC_ALLOWED = WRITER + CALC + IMPRESS

# what each kind of document can be turned into
TARGETS = {
    "writer": ["pdf", "docx", "odt", "txt", "rtf", "html"],
    "calc": ["pdf", "xlsx", "ods", "csv", "html"],
    "impress": ["pdf", "pptx", "odp"],
}
ALL_TARGETS = ["pdf", "docx", "odt", "txt", "rtf", "html", "xlsx", "ods", "csv", "pptx", "odp"]

# LibreOffice wants a filter name for some formats to get the encoding right
FILTERS = {
    "txt": "txt:Text (encoded):UTF8",
    "csv": "csv:Text - txt - csv (StarCalc):44,34,76,1",
}


def kind_of(path):
    ext = Path(path).suffix.lower()
    if ext in WRITER:
        return "writer"
    if ext in CALC:
        return "calc"
    if ext in IMPRESS:
        return "impress"
    return None


def _profile_url():
    profile = data_dir() / "lo_profile"
    profile.mkdir(parents=True, exist_ok=True)
    return profile.as_uri()


def convert_document(input_path, output_folder, target, progress=None,
                     cancel=None, timeout=300):
    target = target.lstrip(".").lower()
    input_path = Path(input_path)
    kind = kind_of(input_path)
    if kind is None:
        raise ValueError(f"{input_path.suffix} isn't a document type I know.")
    if target not in TARGETS[kind]:
        allowed = ", ".join(t.upper() for t in TARGETS[kind])
        raise ValueError(
            f"A {input_path.suffix} file can only be turned into: {allowed}."
        )

    soffice = require_tool("soffice")
    folder = Path(output_folder)
    folder.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="convertor_"))

    command = [
        soffice, "--headless", "--norestore", "--nolockcheck", "--nologo",
        f"-env:UserInstallation={_profile_url()}",
        "--convert-to", FILTERS.get(target, target),
        "--outdir", str(work), str(input_path),
    ]

    try:
        with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as log:
            process = subprocess.Popen(
                command, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
            )
            started = time.monotonic()
            while process.poll() is None:
                if cancel and cancel():
                    process.kill()
                    process.wait()
                    raise Cancelled()
                if time.monotonic() - started > timeout:
                    process.kill()
                    process.wait()
                    raise RuntimeError("LibreOffice took too long and was stopped.")
                if progress:
                    elapsed = time.monotonic() - started
                    progress(min(0.9, elapsed / 30))
                time.sleep(0.2)
            log.seek(0)
            message = log.read().strip()

        made = sorted(work.glob(f"{input_path.stem}.*"))
        if not made:
            raise RuntimeError(message or "LibreOffice didn't produce a file.")

        new_path = unique_path(folder / made[0].name)
        shutil.move(str(made[0]), new_path)
        if progress:
            progress(1.0)
        return new_path
    finally:
        shutil.rmtree(work, ignore_errors=True)


def describe_document(path):
    path = Path(path)
    kinds = {"writer": "Text document", "calc": "Spreadsheet", "impress": "Presentation"}
    kind = kinds.get(kind_of(path), "Document")
    return f"{kind} \u00b7 {path.suffix[1:].upper()} \u00b7 {format_size(path.stat().st_size)}"
