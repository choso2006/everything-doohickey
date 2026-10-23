import shutil
from pathlib import Path
from core.common import unique_path, Cancelled

def split_file(input_path, output_folder, chunk_size_mb=10, progress=None, cancel=None):
    """Splits a file into multiple chunks of roughly chunk_size_mb."""
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path.name}")
        
    chunk_size = int(float(chunk_size_mb) * 1024 * 1024)
    if chunk_size < 1024:
        raise ValueError("Chunk size must be at least 1 KB.")

    folder = Path(output_folder) / f"{input_path.stem}_parts"
    folder.mkdir(parents=True, exist_ok=True)

    parts_made = []
    total_size = input_path.stat().st_size
    processed = 0

    with open(input_path, 'rb') as f:
        part_num = 1
        while True:
            if cancel and cancel():
                raise Cancelled()

            chunk = f.read(chunk_size)
            if not chunk:
                break

            part_name = f"{input_path.name}.part{part_num:03d}"
            part_path = unique_path(folder / part_name)
            
            with open(part_path, 'wb') as pf:
                pf.write(chunk)
            
            parts_made.append(part_path)
            processed += len(chunk)
            part_num += 1

            if progress:
                progress(processed / total_size)

    return parts_made


def join_files(file_paths, output_folder, output_name=None, progress=None, cancel=None):
    """Joins multiple .partXXX files back into a single file."""
    if not file_paths:
        raise ValueError("No files selected to join.")
    
    file_paths = sorted([Path(p) for p in file_paths])
    
    if not output_name:
        first_name = file_paths[0].name
        if ".part" in first_name:
            output_name = first_name.rsplit(".part", 1)[0]
        else:
            output_name = "joined_file" + file_paths[0].suffix
            
    output_path = unique_path(Path(output_folder) / output_name)
    
    total_size = sum(p.stat().st_size for p in file_paths)
    processed = 0

    with open(output_path, 'wb') as outfile:
        for p in file_paths:
            if cancel and cancel():
                outfile.close()
                output_path.unlink(missing_ok=True)
                raise Cancelled()

            with open(p, 'rb') as infile:
                shutil.copyfileobj(infile, outfile)
            
            processed += p.stat().st_size
            if progress:
                progress(processed / total_size)

    return output_path