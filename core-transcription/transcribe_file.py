"""Transcribe a file from the command line.

    python transcribe_file.py meeting.mp3
    python transcribe_file.py meeting.mp3 --output-type srt --out meeting.srt
    python transcribe_file.py meeting.mp3 --no-speaker-labels --no-word-timestamps

Reads the API key from SPEECHREVOLUTIONS_API_KEY (or STT_API_KEY).
"""

import argparse
import sys

from speechrevolutions import SpeechRevolutions
from speechrevolutions.exceptions import STTError


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", help="local file path or http(s) URL")
    parser.add_argument("--output-type", default="json", choices=["txt", "json", "srt", "vtt", "docx", "pdf"])
    parser.add_argument("--out", help="path to save the result (defaults to stdout for txt/json)")
    parser.add_argument("--no-speaker-labels", action="store_true")
    parser.add_argument("--no-word-timestamps", action="store_true")
    args = parser.parse_args()

    client = SpeechRevolutions()

    try:
        result = client.transcribe(
            args.audio,
            output_type=args.output_type,
            speaker_labels=not args.no_speaker_labels,
            word_timestamps=not args.no_word_timestamps,
            progress=True,
        )
    except STTError as e:
        print(f"transcription failed: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    if args.out:
        path = result.save(args.out)
        print(f"saved to {path}")
    elif args.output_type == "json":
        for u in result.utterances:
            speaker = f"[{u.speaker}] " if u.speaker else ""
            print(f"{speaker}{u.text}")
    else:
        print(result.text)


if __name__ == "__main__":
    main()
