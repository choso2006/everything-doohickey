import queue
import threading

from core.appdata import log_exception


class JobRunner:
    """Runs a job on a second thread so the window never freezes.

    The worker never touches widgets. It drops messages in a queue, and the
    main thread reads that queue every 100 ms and updates the screen.
    """

    def __init__(self, widget, on_file, on_progress, on_finished):
        self.widget = widget
        self.on_file = on_file
        self.on_progress = on_progress
        self.on_finished = on_finished
        self.messages = queue.Queue()
        self.stop = threading.Event()
        self.running = False

    def start(self, job):
        if self.running:
            return
        self.running = True
        self.stop.clear()
        self.messages = queue.Queue()

        thread = threading.Thread(
            target=self._work, args=(job, self.messages), daemon=True
        )
        thread.start()
        self.widget.after(100, self._poll)

    def cancel(self):
        self.stop.set()

    def _work(self, job, messages):
        try:
            result = job(
                on_file=lambda n, t, name: messages.put(("file", n, t, name)),
                on_progress=lambda f: messages.put(("progress", f)),
                should_cancel=self.stop.is_set,
            )
            messages.put(("done", result, None))
        except Exception as e:
            log_exception("job crashed")
            messages.put(("done", None, str(e) or e.__class__.__name__))

    def _poll(self):
        try:
            while True:
                message = self.messages.get_nowait()
                kind = message[0]
                if kind == "file":
                    self.on_file(*message[1:])
                elif kind == "progress":
                    self.on_progress(message[1])
                elif kind == "done":
                    self.running = False
                    self.on_finished(message[1], message[2])
                    return
        except queue.Empty:
            pass
        self.widget.after(100, self._poll)
