from core.brushes import read_sut_data, write_procreate_brush, write_sut

def convert_csp_to_procreate(sut_path, output_folder, progress=None, cancel=None):
    """Extracts a CSP .sut and builds a Procreate .brush zip."""
    if cancel and cancel():
        return None
    name, tip_png, settings = read_sut_data(sut_path)
    if cancel and cancel():
        return None
    return write_procreate_brush(
        name=name,
        tip_png_bytes=tip_png,
        spacing=settings.get("spacing", 0.05),
        opacity=settings.get("opacity", 1.0),
        max_size=settings.get("max_size", 100.0),
        output_folder=output_folder
    )

def convert_procreate_to_csp_sut(brush_path, output_folder, template_sut_path, progress=None, cancel=None):
    """Our existing write_sut logic."""
    return write_sut(template_sut_path, brush_path, output_folder, progress, cancel)