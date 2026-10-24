import io
import plistlib
import shutil
import sqlite3
import tarfile
import tempfile
import zipfile
from pathlib import Path

from PIL import Image

from core.common import Cancelled, unique_path

BRUSH_ALLOWED = (".brush", ".brushset")
SUT_ALLOWED = (".sut",)

SQLITE_MAGIC = b"SQLite format 3\x00"

DYNAMICS_FIELDS = [
    ("dynamicsPressureSize", "Size (pressure)"),
    ("dynamicsPressureOpacity", "Opacity (pressure)"),
    ("dynamicsPressureShapeRoundness", "Shape roundness (pressure)"),
    ("dynamicsPressureHue", "Hue (pressure)"),
    ("dynamicsPressureSaturation", "Saturation (pressure)"),
    ("dynamicsPressureBrightness", "Brightness (pressure)"),
    ("dynamicsTiltSize", "Size (tilt)"),
    ("dynamicsTiltOpacity", "Opacity (tilt)"),
    ("dynamicsTiltAngle", "Angle (tilt)"),
    ("dynamicsTiltShapeRoundness", "Shape roundness (tilt)"),
    ("dynamicsSpeedSize", "Size (speed)"),
    ("dynamicsSpeedOpacity", "Opacity (speed)"),
    ("dynamicsRollSize", "Size (roll)"),
    ("dynamicsRollOpacity", "Opacity (roll)"),
    ("dynamicsJitterSize", "Size (jitter)"),
    ("dynamicsJitterOpacity", "Opacity (jitter)"),
]


def _resolve(objs, node, depth=0):
    if depth > 50:
        return None
    if isinstance(node, plistlib.UID):
        i = node.data
        return _resolve(objs, objs[i], depth + 1) if 0 <= i < len(objs) else None
    if isinstance(node, dict):
        if "NS.keys" in node and "NS.objects" in node:
            keys = [_resolve(objs, k, depth + 1) for k in node["NS.keys"]]
            vals = [_resolve(objs, v, depth + 1) for v in node["NS.objects"]]
            return dict(zip(keys, vals))
        return {k: _resolve(objs, v, depth + 1)
                for k, v in node.items() if not k.startswith("$")}
    if isinstance(node, list):
        return [_resolve(objs, v, depth + 1) for v in node]
    return node


def _decode_archive(data):
    try:
        plist = plistlib.loads(data)
    except Exception:
        return {}
    objects = plist.get("$objects", [])
    root = plist.get("$top", {}).get("root")
    if isinstance(root, plistlib.UID):
        root = root.data
    if not isinstance(root, int) or root >= len(objects):
        return {}
    return _resolve(objects, objects[root])


def _brush_bundle(path):
    path = Path(path)
    files = {}
    if path.is_dir():
        for f in path.rglob("*"):
            if f.is_file():
                files[str(f.relative_to(path)).replace("\\", "/")] = f.read_bytes()
        return files
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if not name.endswith("/"):
                    files[name] = zf.read(name)
        return files
    raise ValueError(f"{path.name} isn't a .brush or .brushset file.")


def _read_archive(files, prefix):
    for name, data in files.items():
        if name.startswith(prefix) and name.endswith("Brush.archive") and "/Reset/" not in name:
            return _decode_archive(data)
    return {}


def _iter_brush_entries(files):
    if "Brush.archive" in files:
        archive = _decode_archive(files["Brush.archive"])
        return [("", archive)] if archive else []
    uuids = []
    for rel in files:
        parts = rel.split("/")
        if len(parts) >= 2 and parts[1] == "Brush.archive" and "Reset" not in parts:
            if parts[0] not in uuids:
                uuids.append(parts[0])
    out = []
    for uuid in uuids:
        archive = _read_archive(files, f"{uuid}/")
        if archive:
            out.append((f"{uuid}/", archive))
    return out


def _tip_bytes(files, prefix):
    candidates = []
    for rel, data in files.items():
        if not rel.startswith(prefix):
            continue
        short = rel[len(prefix):].lstrip("/").lower()
        if not short.endswith((".png", ".jpg", ".jpeg")):
            continue
        if short.startswith(("reset/", "signature/", "authorpicture/", "quicklook/")):
            continue
        candidates.append((short, data))
    if not candidates:
        return None
    for short, data in candidates:
        if "shape" in short:
            return data
    return candidates[0][1]


def _curve_points(curve):
    if not isinstance(curve, dict):
        return None
    pts = curve.get("points")
    if not isinstance(pts, dict):
        return None
    raw = pts.get("NS.objects")
    return raw if isinstance(raw, list) else None


def _format_curve(points):
    if not points:
        return "linear (0,0 -> 1,1)"
    return " -> ".join(str(p) for p in points)


def make_settings_text(archive):
    name = str(archive.get("name") or "Brush")
    lines = [f"Brush: {name}", ""]

    author = archive.get("authorName")
    if author and author != "$null":
        lines += [f"Author: {author}", ""]

    lines.append("-- Main Settings --")
    for key, label, fmt in (
        ("maxSize", "Max size (px)", "{:.2f}"),
        ("minSize", "Min size (px)", "{:.6f}"),
    ):
        v = archive.get(key)
        if isinstance(v, (int, float)):
            lines.append(f"{label}: " + fmt.format(v))

    v = archive.get("paintOpacity")
    if isinstance(v, (int, float)):
        lines.append(f"Opacity: {round(v * 100)}%")

    v = archive.get("plotSpacing")
    if isinstance(v, (int, float)):
        lines.append(f"Spacing: {v * 100:.2f}%")

    v = archive.get("blendMode")
    if v is not None:
        lines.append(f"Blend mode: {v} (0 = normal)")

    lines += ["", "-- Dynamics (0% = off, 100% = full) --"]
    any_dyn = False
    for key, label in DYNAMICS_FIELDS:
        v = archive.get(key)
        if isinstance(v, (int, float)) and abs(v) > 0.001:
            any_dyn = True
            curve = _format_curve(_curve_points(archive.get(f"{key}Curve")))
            lines.append(f"{label}: {round(v * 100)}%   curve: {curve}")
    if not any_dyn:
        lines.append("(no pressure or tilt dynamics - flat brush)")

    lines += ["", "-- Files in this folder --"]
    grain = archive.get("bundledGrainPath")
    if grain and grain != "$null":
        lines.append(f"Grain (Texture): {grain}")
    shape = archive.get("bundledShapePath")
    if shape and shape != "$null":
        lines.append(f"Shape (Tip): {shape}")
    else:
        lines.append("Shape (Tip): Shape.png")

    lines += [
        "",
        "----------------------------------------------------",
        "How to use in Clip Studio Paint:",
        "----------------------------------------------------",
        "1. Drag Shape.png into the Sub Tool palette (creates a new brush).",
        "2. Right-click the new subtool -> Tool Settings.",
        "3. Copy the numbers above.",
        "4. Procreate -> CSP Translation Guide:",
        "   - Procreate 'Spacing' = CSP 'Interval'",
        "   - Procreate 'Grain' = CSP 'Texture'",
        "   - Procreate 'Opacity' = CSP 'Opacity'",
        "   - Procreate 'Size (pressure)' = CSP 'Pen Pressure' (Size)",
        "5. If you have a Grain/Texture image in this folder, import it",
        "   into CSP's 'Texture' tab and set it to 'Multiply'.",
    ]
    return "\n".join(lines) + "\n"


def _extract_one(files, prefix, archive, output_folder):
    name = str(archive.get("name") or "brush")
    safe = "".join(c for c in name if c not in '<>:"/\\|?*').strip() or "brush"
    target = unique_path(Path(output_folder) / safe)
    target.mkdir(parents=True, exist_ok=True)

    for rel, data in files.items():
        if not rel.startswith(prefix):
            continue
        short = rel[len(prefix):].lstrip("/")
        if not short or not short.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        low = short.lower()
        if low.startswith(("reset/", "signature/", "authorpicture/")):
            continue
        if low.startswith("quicklook/"):
            short = short.split("/", 1)[1]
        (target / short.replace("/", "_")).write_bytes(data)

    (target / "settings.txt").write_text(make_settings_text(archive), encoding="utf-8")
    return target


def extract_brush(path, output_folder, progress=None, cancel=None):
    files = _brush_bundle(path)
    entries = _iter_brush_entries(files)
    if not entries:
        raise ValueError("Couldn't read Brush.archive inside this file.")
    prefix, archive = entries[0]
    return _extract_one(files, prefix, archive, output_folder)


def extract_brushset(path, output_folder, progress=None, cancel=None):
    files = _brush_bundle(path)
    entries = _iter_brush_entries(files)
    if not entries:
        raise ValueError("No brushes found inside this .brushset.")
        
    made = []
    summary_lines = [f"Master Summary for: {Path(path).name}", "=" * 40, ""]
    
    for i, (prefix, archive) in enumerate(entries):
        if cancel and cancel():
            raise Cancelled()
        try:
            folder = _extract_one(files, prefix, archive, output_folder)
            made.append(folder)
            summary_lines.append(make_settings_text(archive))
            summary_lines.append("-" * 40)
            summary_lines.append("")
        except Exception:
            pass
        if progress:
            progress((i + 1) / len(entries))
            
    if made:
        root_summary = unique_path(Path(output_folder) / "_ALL_BRUSHES_SUMMARY.txt")
        root_summary.write_text("\n".join(summary_lines), encoding="utf-8")
        
    return made


def describe_brush(path):
    try:
        files = _brush_bundle(path)
        entries = _iter_brush_entries(files)
        if not entries:
            return Path(path).stem
        if len(entries) == 1:
            return str(entries[0][1].get("name") or Path(path).stem)
        return f"{Path(path).stem} - {len(entries)} brushes"
    except Exception:
        return path.name


def preview_brush(path, box=(520, 140)):
    """(PIL thumbnail of the brush tip, one-line info). None on failure."""
    try:
        files = _brush_bundle(path)
        entries = _iter_brush_entries(files)
    except Exception:
        return None
    if not entries:
        return None

    prefix, archive = entries[0]
    tip_data = _tip_bytes(files, prefix)
    if not tip_data:
        return None
    try:
        im = Image.open(io.BytesIO(tip_data)).convert("RGBA")
    except Exception:
        return None
    im.thumbnail(box, Image.Resampling.LANCZOS)

    name = str(archive.get("name") or Path(path).stem)
    if Path(path).suffix.lower() == ".brushset":
        n = len(entries)
        info = f"{name} - {n} brush{'es' if n != 1 else ''}"
    else:
        parts = [name]
        max_size = archive.get("maxSize")
        if isinstance(max_size, (int, float)):
            parts.append(f"max {max_size:.0f}px")
        try:
            parts.append(f"{Path(path).stat().st_size // 1024} KB")
        except OSError:
            pass
        info = " - ".join(parts)
    return im, info


# ---------------------------------------------------------------- SUT READ/WRITE

def _tip_for_csp(data):
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    if max(im.size) > 1024:
        im.thumbnail((1024, 1024), Image.Resampling.LANCZOS)

    alpha = im.getchannel("A")
    if alpha.getextrema() == (255, 255):
        alpha = im.convert("L")

    white = Image.new("RGBA", im.size, (255, 255, 255, 0))
    white.putalpha(alpha)
    buf = io.BytesIO()
    white.save(buf, format="PNG")
    return buf.getvalue()


def _replace_tip_in_tar(blob, new_png):
    try:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:") as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            payload = {m.name: tf.extractfile(m).read() for m in members}
    except (tarfile.TarError, OSError):
        return None

    pngs = [n for n in payload if n.lower().endswith(".png")]
    if not pngs:
        return None

    def score(name):
        low = name.lower()
        hint = 2 if any(k in low for k in ("tip", "shape", "stamp")) else 0
        return (hint, len(payload[name]))

    target = max(pngs, key=score)
    payload[target] = new_png

    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as tf:
        for m in members:
            data = payload[m.name]
            info = tarfile.TarInfo(m.name)
            info.size = len(data)
            info.mtime = m.mtime
            info.mode = m.mode
            info.uid = m.uid
            info.gid = m.gid
            info.uname = m.uname
            info.gname = m.gname
            tf.addfile(info, io.BytesIO(data))
    return out.getvalue()


def _build_sut(template_bytes, tip_png, brush_name):
    offset = template_bytes.find(SQLITE_MAGIC)
    if offset < 0:
        raise ValueError(
            "That template isn't a .sut file. Export a brush from Clip Studio Paint "
            "and pick that file as the template."
        )
    prefix, db = template_bytes[:offset], template_bytes[offset:]

    work = Path(tempfile.mkdtemp(prefix="convertor_sut_"))
    db_path = work / "template.sut"
    db_path.write_bytes(db)
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("PRAGMA journal_mode=DELETE")

            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            missing = {"Node", "Variant", "MaterialFile"} - tables
            if missing:
                raise ValueError(
                    "The template is missing tables: " + ", ".join(sorted(missing)) +
                    ". Export a brush from Clip Studio Paint and use that."
                )

            node_cols = [r[1] for r in conn.execute("PRAGMA table_info(Node)")]
            if "NodeName" in node_cols:
                try:
                    conn.execute(
                        "UPDATE Node SET NodeName=? WHERE rowid=(SELECT MIN(rowid) FROM Node)",
                        (brush_name,),
                    )
                except sqlite3.Error:
                    conn.execute("UPDATE Node SET NodeName=?", (brush_name,))

            mat_cols = [r[1] for r in conn.execute("PRAGMA table_info(MaterialFile)")]
            blob_col = next(
                (c for c in mat_cols if c.lower() in ("thefiledata", "filedata")), None
            )
            if blob_col is None:
                blob_col = next((c for c in mat_cols if "data" in c.lower()), None)
            if blob_col is None:
                raise ValueError("The template has no material data column.")

            id_col = "_PW_ID" if "_PW_ID" in mat_cols else "rowid"
            rows = conn.execute(
                f"SELECT {id_col}, {blob_col} FROM MaterialFile"
            ).fetchall()

            replaced = 0
            for row_id, blob in rows:
                if not isinstance(blob, (bytes, bytearray)):
                    continue
                new_blob = _replace_tip_in_tar(bytes(blob), tip_png)
                if new_blob:
                    conn.execute(
                        f"UPDATE MaterialFile SET {blob_col}=? WHERE {id_col}=?",
                        (sqlite3.Binary(new_blob), row_id),
                    )
                    replaced += 1

            if not replaced:
                raise ValueError(
                    "Couldn't find a tip image inside the template's material archive."
                )

            conn.commit()
            conn.execute("VACUUM")
        finally:
            conn.close()

        return prefix + db_path.read_bytes()
    finally:
        shutil.rmtree(work, ignore_errors=True)


def write_sut(template_path, brush_path, output_folder, progress=None, cancel=None):
    template_bytes = Path(template_path).read_bytes()
    files = _brush_bundle(brush_path)
    entries = _iter_brush_entries(files)
    if not entries:
        raise ValueError("No brushes found inside this file.")

    made = []
    for i, (prefix, archive) in enumerate(entries):
        if cancel and cancel():
            raise Cancelled()

        name = str(archive.get("name") or "Brush")
        tip = _tip_bytes(files, prefix)
        if tip is None:
            raise ValueError(f"{name}: no brush tip image found.")
        tip = _tip_for_csp(tip)

        data = _build_sut(template_bytes, tip, name)
        safe = "".join(c for c in name if c not in '<>:"/\\|?*').strip() or "brush"
        path = unique_path(Path(output_folder) / f"{safe}.sut")
        path.write_bytes(data)
        made.append(path)

        if progress:
            progress((i + 1) / len(entries))
    return made


def read_sut_data(sut_path):
    """Reads a CSP .sut file and returns (name, tip_png_bytes, settings_dict)."""
    sut_path = Path(sut_path)
    data = sut_path.read_bytes()
    offset = data.find(SQLITE_MAGIC)
    if offset < 0:
        raise ValueError("Not a valid .sut file (missing SQLite header).")
    
    db_bytes = data[offset:]
    work = Path(tempfile.mkdtemp(prefix="convertor_sut_read_"))
    db_path = work / "temp.sut"
    db_path.write_bytes(db_bytes)
    
    name = sut_path.stem
    tip_png = None
    settings = {"spacing": 0.05, "opacity": 1.0, "max_size": 100.0}
    
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("SELECT NodeName FROM Node LIMIT 1").fetchone()
            if row and row[0]:
                name = row[0]
                
            var_cols = [r[1].lower() for r in conn.execute("PRAGMA table_info(Variant)")]
            var_row = conn.execute("SELECT * FROM Variant LIMIT 1").fetchone()
            if var_row:
                var_dict = dict(zip(var_cols, var_row))
                if "interval" in var_dict and var_dict["interval"]:
                    settings["spacing"] = float(var_dict["interval"])
                if "opacity" in var_dict and var_dict["opacity"]:
                    settings["opacity"] = float(var_dict["opacity"])
                if "brushsize" in var_dict and var_dict["brushsize"]:
                    settings["max_size"] = float(var_dict["brushsize"])

            mat_cols = [r[1] for r in conn.execute("PRAGMA table_info(MaterialFile)")]
            blob_col = next((c for c in mat_cols if c.lower() in ("thefiledata", "filedata")), None)
            if not blob_col:
                blob_col = next((c for c in mat_cols if "data" in c.lower()), None)
                
            if blob_col:
                rows = conn.execute(f"SELECT {blob_col} FROM MaterialFile").fetchall()
                for (blob,) in rows:
                    if not isinstance(blob, (bytes, bytearray)):
                        continue
                    try:
                        with tarfile.open(fileobj=io.BytesIO(bytes(blob)), mode="r:") as tf:
                            for member in tf.getmembers():
                                if member.name.lower().endswith((".png", ".jpg", ".jpeg")):
                                    tip_png = tf.extractfile(member).read()
                                    break
                    except Exception:
                        pass
                    if tip_png:
                        break
        finally:
            conn.close()
    finally:
        shutil.rmtree(work, ignore_errors=True)
        
    if not tip_png:
        raise ValueError("Couldn't find a brush tip image inside the .sut file.")
        
    return name, tip_png, settings


def extract_sut_textures(sut_path, output_folder, progress=None, cancel=None):
    """Extracts textures and settings from a CSP .sut file."""
    name, tip_png, settings = read_sut_data(sut_path)
    safe = "".join(c for c in name if c not in '<>:"/\\|?*').strip() or "brush"
    target = unique_path(Path(output_folder) / safe)
    target.mkdir(parents=True, exist_ok=True)
    
    (target / "Shape.png").write_bytes(tip_png)
    
    lines = [
        f"Brush: {name} (Extracted from CSP)",
        "",
        "-- Main Settings --",
        f"Max size: {settings['max_size']}",
        f"Opacity: {round(settings['opacity'] * 100)}%",
        f"Spacing (Interval): {settings['spacing'] * 100:.2f}%",
        "",
        "How to use in Procreate:",
        "1. Create a new brush in Procreate.",
        "2. Go to Shape -> Shape Source, and import Shape.png.",
        "3. Go to Stroke -> Spacing, and match the Spacing value above.",
    ]
    (target / "settings.txt").write_text("\n".join(lines), encoding="utf-8")
    return target


def write_procreate_brush(name, tip_png_bytes, spacing, opacity, max_size, output_folder):
    """Builds a Procreate .brush file from extracted settings."""
    archive_data = {
        "$version": 100000,
        "$archiver": "NSKeyedArchiver",
        "$top": {"root": plistlib.UID(1)},
        "$objects": [
            "$null",
            {
                "NS.keys": [plistlib.UID(2), plistlib.UID(3), plistlib.UID(4), plistlib.UID(5)],
                "NS.objects": [plistlib.UID(6), plistlib.UID(7), plistlib.UID(8), plistlib.UID(9)],
            },
            "name", "maxSize", "plotSpacing", "paintOpacity",
            name, max_size, spacing, opacity,
        ],
    }
    plist_bytes = plistlib.dumps(archive_data, fmt=plistlib.FMT_BINARY)
    
    safe = "".join(c for c in name if c not in '<>:"/\\|?*').strip() or "brush"
    out_path = unique_path(Path(output_folder) / f"{safe}.brush")
    
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Brush.archive", plist_bytes)
        zf.writestr("Shape.png", tip_png_bytes)
        zf.writestr("QuickLook/Thumbnail.png", tip_png_bytes)
        
    return out_path