"""A runnable web app showing a live progress bar while a file transcribes.

    pip install fastapi uvicorn
    uvicorn live_progress_webapp:app --reload

Open http://localhost:8000, paste an audio URL, and watch the upload +
transcription bars move in real time. The transcription runs in a background
task; the browser just polls GET /progress/{job_id} every 500ms.
"""


from __future__ import annotations

import threading
from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import HTMLResponse
from speechrevolutions import ProgressEvent, SpeechRevolutions

app = FastAPI()
client = SpeechRevolutions()  # reads SPEECHREVOLUTIONS_API_KEY

# Weight the two phases into one bar: upload is usually quick, transcription
# takes the rest. Tune to taste.
_UPLOAD_WEIGHT = 0.15
_TRANSCRIBE_WEIGHT = 0.85


@dataclass
class JobProgress:
    phase: str = "starting"  # starting | upload | transcribe | done | error
    percent: float = 0.0
    text: str | None = None
    error: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set(self, phase: str, overall: float) -> None:
        with self._lock:
            self.phase = phase
            self.percent = max(self.percent, round(overall, 1))  # never go backwards

    def snapshot(self) -> dict:
        with self._lock:
            return {"phase": self.phase, "percent": self.percent, "text": self.text, "error": self.error}


JOBS: dict[str, JobProgress] = {}


def run_transcription(job_id: str, audio: str) -> None:
    progress = JOBS[job_id]

    def on_upload(event: ProgressEvent) -> None:
        progress.set("upload", (event.percent or 0.0) * _UPLOAD_WEIGHT)

    def on_transcribe(event: ProgressEvent) -> None:
        progress.set("transcribe", _UPLOAD_WEIGHT * 100 + (event.percent or 0.0) * _TRANSCRIBE_WEIGHT)

    try:
        result = client.transcribe(audio, on_upload_progress=on_upload, on_progress=on_transcribe)
        progress.text = result.text
        progress.set("done", 100.0)
    except Exception as e:  # noqa: BLE001 — surface any failure to the browser
        progress.error = str(e)
        progress.set("error", progress.percent)


@app.post("/transcribe")
def start(audio: str, background: BackgroundTasks):
    job_id = str(uuid4())
    JOBS[job_id] = JobProgress()
    background.add_task(run_transcription, job_id, audio)
    return {"job_id": job_id}


@app.get("/progress/{job_id}")
def progress(job_id: str):
    return JOBS[job_id].snapshot()


@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!doctype html>
<title>Live transcription progress</title>
<body style="font-family: system-ui; max-width: 32rem; margin: 3rem auto">
  <h1>Transcribe with live progress</h1>
  <input id="audio" placeholder="https://example.com/audio.mp3" style="width: 100%" />
  <button onclick="start()">Transcribe</button>
  <p id="phase"></p>
  <progress id="bar" value="0" max="100" style="width: 100%"></progress>
  <pre id="text" style="white-space: pre-wrap"></pre>
  <script>
    async function start() {
      const audio = document.getElementById('audio').value;
      const res = await fetch(`/transcribe?audio=${encodeURIComponent(audio)}`, { method: 'POST' });
      const { job_id } = await res.json();
      poll(job_id);
    }
    async function poll(jobId) {
      const res = await fetch(`/progress/${jobId}`);
      const snap = await res.json();
      document.getElementById('phase').textContent = snap.error ? `error: ${snap.error}` : snap.phase;
      document.getElementById('bar').value = snap.percent;
      if (snap.phase === 'done') {
        document.getElementById('text').textContent = snap.text;
        return;
      }
      if (snap.phase !== 'error') setTimeout(() => poll(jobId), 500);
    }
  </script>
</body>
"""
