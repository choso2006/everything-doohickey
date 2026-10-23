import sys
import traceback


def _log_crash(context):
    """Write any startup crash to log.txt so the packaged app is debuggable."""
    print(f"\n=== CRASH DURING {context} ===", file=sys.stderr)
    traceback.print_exc()
    try:
        from core.appdata import log_exception
        log_exception(context)
    except Exception:
        # If even logging fails, we've done all we can
        pass


if __name__ == "__main__":
    try:
        from ui.splash import show_splash
        show_splash()
    except Exception:
        _log_crash("splash screen")
        sys.exit(1)

    try:
        from ui.app import App
        App().mainloop()
    except Exception:
        _log_crash("main application")
        sys.exit(1)