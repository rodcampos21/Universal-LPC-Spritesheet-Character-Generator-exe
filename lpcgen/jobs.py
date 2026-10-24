from __future__ import annotations

import queue
import threading
import time
import uuid


class Job:
    def __init__(self, kind):
        self.id = uuid.uuid4().hex[:12]
        self.kind, self.status, self.progress, self.message = kind, "queued", 0.0, ""
        self.result, self.error = {}, None
        self.cancel = threading.Event()

    def view(self):
        return {"id": self.id, "kind": self.kind, "status": self.status, "progress": self.progress,
                "message": self.message, "result": self.result, "error": self.error}


class JobManager:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._q: queue.Queue = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def submit(self, kind, fn, message=""):
        j = Job(kind)
        j.message = message
        self._jobs[j.id] = j
        self._q.put((j, fn))
        return j

    def _run(self):
        while True:
            job, fn = self._q.get()
            job.status = "running"

            def progress(frac, msg=None, job=job):
                job.progress = max(0.0, min(1.0, float(frac)))
                if msg:
                    job.message = msg
            try:
                job.result = fn(progress, job.cancel) or {}
                job.status, job.progress, job.message = "done", 1.0, "Pronto."
            except Exception as e:                                    # noqa: BLE001
                if job.cancel.is_set():
                    job.status, job.message = "cancelled", "Cancelado."
                else:
                    job.status, job.error, job.message = "error", str(e) or e.__class__.__name__, "Falhou."

    def get(self, jid):
        return self._jobs.get(jid)

    def active(self):
        return any(j.status in ("queued", "running") for j in self._jobs.values())
