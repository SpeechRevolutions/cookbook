"""The webhook receiver recipes, end to end over real sockets.

This is the path the user flagged as never having been tested anywhere. It is
also the one most likely to be wrong in a way nobody notices: a receiver that
verifies the signature against a re-serialised body rejects every delivery, and
you only find out when a customer says their callbacks stopped working.

The shape here is the real one:

    uvicorn webhook_receiver_fastapi:app   (a real server, on a real port)
        -> POST /transcribe                (recipe submits a job to the mock API)
        -> mock API completes the job      (and POSTs the signed webhook back)
        -> receiver verifies + stores it
        -> GET /transcribe/{job_id}        (the transcript is there)

Nothing is stubbed on the receiver side, so the signature really is computed
over the bytes that really arrived.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

COOKBOOK = Path(__file__).resolve().parents[1]
SECRET = "whsec_cookbook_test"

pytest.importorskip("fastapi", reason="the FastAPI receiver recipe needs fastapi")
pytest.importorskip("uvicorn", reason="the FastAPI receiver recipe needs uvicorn")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str, timeout: float = 5.0) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _post(url: str, timeout: float = 20.0) -> tuple[int, str]:
    req = urllib.request.Request(url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


class Receiver:
    """Runs the published recipe under uvicorn, exactly as its docstring says."""

    def __init__(self, api, *, secret: str = SECRET) -> None:
        self.api = api
        self.secret = secret
        self.port = _free_port()
        self.proc: subprocess.Popen | None = None

    def __enter__(self) -> Receiver:
        env = {
            **os.environ,
            "SPEECHREVOLUTIONS_API_KEY": self.api.api_key,
            "SPEECHREVOLUTIONS_BASE_URL": self.api.base_url,
            "SR_WEBHOOK_SECRET": self.secret,
            "PYTHONPATH": os.environ.get("SR_SDK_SRC", ""),
            "PYTHONUNBUFFERED": "1",
        }
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "webhook_receiver_fastapi:app",
             "--port", str(self.port), "--log-level", "warning"],
            cwd=str(COOKBOOK / "webhooks"), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise AssertionError(
                    f"receiver exited {self.proc.returncode}:\n{self.proc.stdout.read()}"
                )
            try:
                _get(f"{self.base}/docs", timeout=1.0)
                return self
            except Exception:
                time.sleep(0.2)
        raise AssertionError("receiver never came up")

    def __exit__(self, *exc: object) -> None:
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def submit(self, audio: str = "https://example.com/a.mp3") -> str:
        import json
        status, body = _post(
            f"{self.base}/transcribe?audio={audio}&callback_base_url={self.base}"
        )
        assert status == 200, f"submit failed {status}: {body}"
        return json.loads(body)["job_id"]

    def poll(self, job_id: str, want: str, timeout: float = 20.0) -> dict:
        import json
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            status, body = _get(f"{self.base}/transcribe/{job_id}")
            if status == 200:
                last = json.loads(body)
                if last.get("status") == want:
                    return last
            time.sleep(0.15)
        raise AssertionError(f"job never reached {want!r}; last state: {last}")


@pytest.fixture
def signed_api(request):
    """A mock API that signs its webhooks with the secret the recipe expects."""
    from mock_api import MockAPI

    with MockAPI(progress_steps=1, webhook_secret=SECRET) as a:
        yield a


# ---------------------------------------------------------------------------

def test_completed_webhook_is_verified_and_stored(signed_api):
    with Receiver(signed_api) as rcv:
        job_id = rcv.submit()
        state = rcv.poll(job_id, "completed")
    assert state["text"] == "Good morning everyone. Thanks for joining."


def test_failed_webhook_records_step_and_reason(signed_api):
    signed_api.fail_job_at = "gpu_timestamps"
    with Receiver(signed_api) as rcv:
        job_id = rcv.submit()
        state = rcv.poll(job_id, "failed")
    assert state["step"] == "gpu_timestamps"
    assert "simulated failure" in state["reason"]


def test_the_recipe_really_verifies_the_signature(signed_api):
    """A delivery signed with the WRONG secret must be rejected with 401.

    Without this, a receiver that accepts anything would pass every other test
    in this file.
    """
    with Receiver(signed_api, secret="whsec_a_different_secret") as rcv:
        job_id = rcv.submit()
        # The signature will not match, so the receiver 401s and never stores
        # a result: the job stays exactly as /transcribe left it.
        time.sleep(2.0)
        status, body = _get(f"{rcv.base}/transcribe/{job_id}")
    assert status == 200
    import json
    assert json.loads(body)["status"] == "processing", (
        "receiver accepted a delivery signed with the wrong secret"
    )


def test_unknown_job_id_is_a_404(signed_api):
    with Receiver(signed_api) as rcv:
        status, _ = _get(f"{rcv.base}/transcribe/job_does_not_exist")
    assert status == 404


def test_the_webhook_actually_reached_the_receiver(signed_api):
    with Receiver(signed_api) as rcv:
        job_id = rcv.submit()
        rcv.poll(job_id, "completed")
    sent = signed_api.wait_webhooks(1)
    assert sent[0]["job_id"] == job_id
    assert sent[0].get("response_status") == 200, (
        f"receiver did not ack the delivery: {sent[0]}"
    )
