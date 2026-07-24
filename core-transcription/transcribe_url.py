"""Transcribe audio straight from a URL — no download step of your own.

Useful for podcast RSS enclosures, publicly hosted recordings, or anything
already sitting behind a URL you don't want to pull through your own server
first. The API fetches the audio itself.

    python transcribe_url.py https://example.com/episode-42.mp3
"""

import argparse

from speechrevolutions import SpeechRevolutions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="http(s) URL to an audio file")
    parser.add_argument("--out", default="transcript.txt")
    args = parser.parse_args()

    client = SpeechRevolutions()

    # transcribe() auto-detects a URL; transcribe_url() makes the intent explicit.
    result = client.transcribe_url(args.url)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(result.text)
    print(f"{len(result.text)} chars written to {args.out}")


if __name__ == "__main__":
    main()
