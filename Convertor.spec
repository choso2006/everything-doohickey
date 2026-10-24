# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

here = Path(SPECPATH)
is_mac = sys.platform == "darwin"
is_win = sys.platform == "win32"

datas = [
    (str(here / "icon.ico"), "."),
    (str(here / "icon.png"), "."),
]
datas += collect_data_files("customtkinter")
datas += collect_data_files("tkinterdnd2")
datas += collect_data_files("pillow_heif")
datas += collect_data_files("pymupdf")

binaries = []
binaries += collect_dynamic_libs("pillow_heif")
binaries += collect_dynamic_libs("pymupdf")

hiddenimports = [
    "PIL._tkinter_finder",
    "ui.images_page",
    "ui.pdfs_page",
    "ui.video_page",
    "ui.audio_page",
    "ui.docs_page",
    "ui.files_page",
    "selftest",
]
hiddenimports += collect_submodules("pymupdf")

a = Analysis(
    [str(here / "main.py")],
    pathex=[str(here)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

icon_path = here / ("icon.ico" if is_win else "icon.png")
icon_arg = str(icon_path) if icon_path.exists() else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Convertor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_arg,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Convertor",
)

if is_mac:
    app = BUNDLE(
        coll,
        name="Convertor.app",
        icon=icon_arg,
        bundle_identifier="com.convertor.app",
        info_plist={
            "CFBundleName": "Convertor",
            "CFBundleDisplayName": "Convertor",
            "CFBundleIdentifier": "com.convertor.app",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )