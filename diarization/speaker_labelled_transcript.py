"""Print a transcript as a labelled, timestamped conversation log.

    python speaker_labelled_transcript.py meeting.mp3

    [00:00:03] SPEAKER_1: Thanks everyone for joining today.
    [00:00:07] SPEAKER_2: Happy to be here, let's get started.
"""


from __future__ import annotations

import argparse

from speechrevolutions import SpeechRevolutions


def format_timestamp(seconds: float | None) -> str:
    if seconds is None:
        return "??:??:??"
    total = int(seconds)
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio")
    args = parser.parse_args()

    client = SpeechRevolutions()
    result = client.transcribe(args.audio, speaker_labels=True, word_timestamps=True)

    for u in result.utterances:
        speaker = u.speaker or "SPEAKER_?"
        print(f"[{format_timestamp(u.start)}] {speaker}: {u.text}")


if __name__ == "__main__":
    main()
