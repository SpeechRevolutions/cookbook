"""Handle every failure mode the client can raise.

    python retry_and_error_handling.py meeting.mp3

The built-in retry (`max_retries` / `retry_backoff`) already covers transient
429/5xx/network errors. This recipe shows the errors worth catching yourself:
a missing file, a bad key, a job that fails server-side, and a manual backoff
loop for RateLimitError that respects `retry_after` on top of the client's own
retries.
"""

import argparse
import sys
import time

from speechrevolutions import SpeechRevolutions
from speechrevolutions.exceptions import (
    AuthenticationError,
    JobFailedError,
    RateLimitError,
    STTError,
    TimeoutError as SRTimeoutError,
    UploadError,
)


def transcribe_with_manual_backoff(client: SpeechRevolutions, audio: str, *, max_attempts: int = 5):
    """Retry on RateLimitError beyond the client's own budget, honoring retry_after."""
    for attempt in range(1, max_attempts + 1):
        try:
            return client.transcribe(audio)
        except RateLimitError as e:
            if attempt == max_attempts:
                raise
            wait = e.retry_after or min(2 ** attempt, 30)
            print(f"rate limited (attempt {attempt}/{max_attempts}); waiting {wait}s")
            time.sleep(wait)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", nargs="?", default="meeting.mp3",
                        help="local file path or http(s) URL (default: meeting.mp3)")
    args = parser.parse_args()

    # max_retries/retry_backoff handle transient 429/5xx/network failures already;
    # this client keeps that budget small so the manual loop above is exercised.
    client = SpeechRevolutions(max_retries=1, retry_backoff=0.5)

    try:
        result = transcribe_with_manual_backoff(client, args.audio)
        print(result.text[:200])
    except FileNotFoundError:
        # The most common failure of all, and not an SDK exception: the path is
        # resolved locally before any request is made.
        print(f"no such file: {args.audio}", file=sys.stderr)
        raise SystemExit(1) from None
    except AuthenticationError:
        print("bad or missing API key — check SPEECHREVOLUTIONS_API_KEY")
    except UploadError as e:
        print(f"upload didn't go through: {e}")
    except JobFailedError as e:
        # e.step is where it failed (e.g. "transcribe"), e.reason is the server's explanation
        print(f"job failed at step={e.step}: {e.reason}")
    except SRTimeoutError:
        print("job didn't finish within the client's timeout — safe to retry with submit()/poll")
    except STTError as e:
        # Catch-all: every SDK exception carries status_code and request_id when available.
        print(f"request failed (HTTP {e.status_code}, request_id={e.request_id}): {e}")


if __name__ == "__main__":
    main()
