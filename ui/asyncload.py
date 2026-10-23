import queue
import threading

from core.appdata import log_exception


class AsyncLoader:
    """Do slow work (like grabbing a video frame) off the main thread.

    Only the newest request counts: if you ask for something else before the
    last request finishes, the old answer is thrown away.
    """

    def __init__(self, widget):
        self.widget = widget
        self.results = queue.Queue()
        self.token = 0
        self._schedule()

    def submit(self, work, done):
        self.token += 1
        token = self.token

        def run():
            try:
                value, error = work(), None
            except Exception as e:
                value, error = None, e
            self.results.put((token, value, error, done))

        threading.Thread(target=run, daemon=True).start()

    def cancel_pending(self):
        self.token += 1

    def _schedule(self):
        try:
            self.widget.after(60, self._poll)
        except Exception:
            pass

    def _poll(self):
        try:
            while True:
                token, value, error, done = self.results.get_nowait()
                if token == self.token:
                    done(value, error)
        except queue.Empty:
            pass
        except Exception:
            log_exception("preview")
        self._schedule()
