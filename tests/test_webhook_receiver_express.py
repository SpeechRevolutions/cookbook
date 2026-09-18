"""The Express webhook receiver recipe, end to end over real sockets.

Same shape as the FastAPI receiver test, against the JavaScript recipe. Worth
having both: the signature check is the part integrations get wrong, and the two
recipes get the raw bytes by different means — FastAPI's `await request.body()`
versus Express's `express.raw({ type: "application/json" })`. A middleware that
parsed and re-serialised instead would break only the JS one.

Skipped unless the harness in tests/node_harness is installed:

    cd tests/node_harness && npm install
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

COOKBOOK = Path(__file__).resolve().parents[1]
HARNESS = Path(__file__).resolve().parent / "node_harness"
SECRET = "whsec_cookbook_test_js"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or not (HARNESS / "node_modules").is_dir(),
    reason="needs node and `npm install` in tests/node_harness",
)


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


class ExpressReceiver:
    """Runs the published .mjs recipe under node, on an ephemeral port.

    The recipe hardcodes `app.listen(8000)`, which is right for a copy-paste
    example and wrong for a test suite that must not collide with whatever is
    already on 8000. PORT is injected by copying the recipe and rewriting that
    one line, so the file under test stays the published one in every other
    respect.
    """

    def __init__(self, api, *, secret: str = SECRET) -> None:
        self.api = api
        self.secret = secret
        self.port = _free_port()
        self.proc: subprocess.Popen | None = None

    def __enter__(self) -> ExpressReceiver:
        src = (COOKBOOK / "webhooks" / "webhook_receiver_express.mjs").read_text()
        patched = src.replace(
            "app.listen(8000,",
            "app.listen(Number(process.env.PORT) || 8000,",
        )
        assert patched != src, "the recipe no longer calls app.listen(8000, ...)"
        runner = HARNESS / "_receiver_under_test.mjs"
        runner.write_text(patched)

        env = {
            **os.environ,
            "SPEECHREVOLUTIONS_API_KEY": self.api.api_key,
            "SPEECHREVOLUTIONS_BASE_URL": self.api.base_url,
            "SR_WEBHOOK_SECRET": self.secret,
            "PORT": str(self.port),
        }
        self.proc = subprocess.Popen(
            ["node", str(runner)], cwd=str(HARNESS), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise AssertionError(
                    f"receiver exited {self.proc.returncode}:\n{self.proc.stdout.read()}"
                )
            try:
                _get(f"{self.base}/transcribe/probe", timeout=1.0)
                return self
            except Exception:
                time.sleep(0.2)
        raise AssertionError("express receiver never came up")

    def __exit__(self, *exc: object) -> None:
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        runner = HARNESS / "_receiver_under_test.mjs"
        if runner.exists():
            runner.unlink()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def submit(self, audio: str = "https://example.com/a.mp3") -> str:
        status, body = _post(
            f"{self.base}/transcribe?audio={audio}&callback_base_url={self.base}"
        )
        assert status == 200, f"submit failed {status}: {body}"
        return json.loads(body)["job_id"]

    def poll(self, job_id: str, want: str, timeout: float = 20.0) -> dict:
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
def signed_api():
    from mock_api import MockAPI

    with MockAPI(progress_steps=1, webhook_secret=SECRET) as a:
        yield a


# ---------------------------------------------------------------------------

def test_completed_webhook_is_verified_and_stored(signed_api):
    with ExpressReceiver(signed_api) as rcv:
        job_id = rcv.submit()
        state = rcv.poll(job_id, "completed")
    assert state["text"] == "Good morning everyone. Thanks for joining."


def test_failed_webhook_records_step_and_reason(signed_api):
    signed_api.fail_job_at = "preprocess"
    with ExpressReceiver(signed_api) as rcv:
        job_id = rcv.submit()
        state = rcv.poll(job_id, "failed")
    assert state["step"] == "preprocess"
    assert "simulated failure" in state["reason"]


def test_the_recipe_really_verifies_the_signature(signed_api):
    """A delivery signed with the WRONG secret must be rejected with 401."""
    with ExpressReceiver(signed_api, secret="whsec_a_different_secret") as rcv:
        job_id = rcv.submit()
        time.sleep(2.0)
        status, body = _get(f"{rcv.base}/transcribe/{job_id}")
    assert status == 200
    assert json.loads(body)["status"] == "processing", (
        "receiver accepted a delivery signed with the wrong secret"
    )


def test_unknown_job_id_is_a_404(signed_api):
    with ExpressReceiver(signed_api) as rcv:
        status, _ = _get(f"{rcv.base}/transcribe/job_does_not_exist")
    assert status == 404


def test_the_receiver_acked_the_delivery(signed_api):
    with ExpressReceiver(signed_api) as rcv:
        job_id = rcv.submit()
        rcv.poll(job_id, "completed")
    sent = signed_api.wait_webhooks(1)
    assert sent[0]["job_id"] == job_id
    assert sent[0].get("response_status") == 200
