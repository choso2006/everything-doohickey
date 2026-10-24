from core.mpv import (
    MPVError, close_all as _close_mpv, mpv_available, mpv_version, spawn_standalone,
)


def open_player(parent, path, start=None, end=None):
    if not mpv_available():
        raise MPVError(
            "mpv not available. Run `py fetch_mpv.py` to download it."
        )
    spawn_standalone(path, start, end)


def close_all():
    _close_mpv()