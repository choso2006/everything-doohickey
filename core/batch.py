from dataclasses import dataclass, field
from pathlib import Path

from core.appdata import log_exception
from core.common import Cancelled


@dataclass
class BatchResult:
    done: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    failed: list = field(default_factory=list)
    cancelled: bool = False

    def summary(self):
        text = f"{len(self.done)} worked, {len(self.failed)} failed"
        if self.cancelled:
            text += ", cancelled"
        return text


def list_files(folder, extensions):
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"folder not found: {folder}")
    return sorted(
        f for f in folder.iterdir()
        if f.is_file() and (not extensions or f.suffix.lower() in extensions)
    )


def run_batch(files, output_folder, action, on_file=None, on_progress=None,
              should_cancel=None, wants_hooks=False, **options):
    """Run `action(file, output_folder, **options)` on every file.

    One bad file never stops the rest. With wants_hooks=True the action also
    gets progress= and cancel= so it can report progress and be stopped midway.
    """
    files = [Path(f) for f in files]
    total = len(files)
    result = BatchResult()

    for number, file in enumerate(files, start=1):
        if should_cancel and should_cancel():
            result.cancelled = True
            break

        if on_file:
            on_file(number, total, file.name)

        extra = {}
        if wants_hooks:
            def hook(fraction, number=number):
                if on_progress:
                    on_progress((number - 1 + fraction) / total)
            extra = {"progress": hook, "cancel": should_cancel}

        try:
            outcome = action(file, output_folder, **extra, **options)
            result.done.append(outcome)
            result.sources.append(file)
        except Cancelled:
            result.cancelled = True
            break
        except Exception as e:
            log_exception(f"{getattr(action, '__name__', 'action')} on {file}")
            result.failed.append((file.name, str(e) or e.__class__.__name__))

        if on_progress:
            on_progress(number / total)

    return result
