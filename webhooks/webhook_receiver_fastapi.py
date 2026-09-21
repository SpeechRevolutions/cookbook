"""A runnable FastAPI server that submits jobs and receives their webhooks.

    pip install fastapi uvicorn
    export SR_WEBHOOK_SECRET=...        # the signing secret from your dashboard
    uvicorn webhook_receiver_fastapi:app --reload

    curl -X POST "http://localhost:8000/transcribe?audio=https://example.com/audio.mp3"

Point `callback_url` at a URL this server is reachable at (e.g. an ngrok
tunnel during local development). The job runs entirely server-side; nothing
here holds a connection open waiting for it.
"""

import hashlib
import hmac
import json
import os

from fastapi import FastAPI, HTTPException, Request
from speechrevolutions import SpeechRevolutions

app = FastAPI()
client = SpeechRevolutions()  # reads SPEECHREVOLUTIONS_API_KEY
SECRET = os.environ["SR_WEBHOOK_SECRET"]

# In-memory for this recipe; use a real datastore in production.
JOBS: dict[str, dict] = {}


def verify_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """Compare against the raw bytes received, not a re-serialized dict."""
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")


@app.post("/transcribe")
def start_transcription(audio: str, callback_base_url: str = "http://localhost:8000"):
    job_id = client.submit(audio, callback_url=f"{callback_base_url}/webhooks/speechrevolutions")
    # setdefault, not assignment: the webhook can arrive before this line runs.
    # The platform fires it the moment the job finishes, and a short clip can
    # finish before submit() has even returned here. Assigning "processing"
    # unconditionally would overwrite a terminal state that already landed, and
    # the job would look stuck forever while the result sat in the response you
    # just threw away.
    JOBS.setdefault(job_id, {"status": "processing"})
    return {"job_id": job_id}


@app.get("/transcribe/{job_id}")
def get_transcription(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="unknown job_id")
    return JOBS[job_id]


@app.post("/webhooks/speechrevolutions")
async def receive_webhook(request: Request):
    raw = await request.body()
    if not verify_signature(raw, request.headers.get("X-SR-Signature", ""), SECRET):
        raise HTTPException(status_code=401, detail="bad signature")

    event = json.loads(raw)
    job_id = event["job_id"]

    if event["status"] == "completed":
        result = client.get_transcript(job_id)
        JOBS[job_id] = {"status": "completed", "text": result.text}
    else:
        JOBS[job_id] = {"status": "failed", "step": event.get("step"), "reason": event.get("reason")}

    return {"ok": True}  # a 2xx acks delivery; the platform retries on 5xx
