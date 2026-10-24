import sys
import traceback

def _log_crash(context):
    print(f"\n=== CRASH DURING {context} ===", file=sys.stderr)
    traceback.print_exc()
    try:
        from core.appdata import log_exception
        log_exception(context)
    except Exception:
        pass

if __name__ == "__main__":
    try:
        from ui.app import App
        app = App()
        app.mainloop()
    except Exception:
        _log_crash("main application")
        sys.exit(1)