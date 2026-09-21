"""Generate subtitles that show who's speaking.

`output_type="srt"` gives you ready-made subtitle bytes, but without speaker
names baked in. This builds an SRT file from the JSON transcript instead, so
each cue can be prefixed with "Speaker X:" — useful for interview or panel
footage where knowing who's talking matters as much as what was said.

    python speaker_labelled_srt.py panel.mp3 --out panel.srt
"""


from __future__ import annotations

import argparse

from speechrevolutions import SpeechRevolutions
from speechrevolutions.transcript import Utterance

MAX_CUE_CHARS = 84  # roughly two lines of readable subtitle text


def srt_timestamp(seconds: float | None) -> str:
    seconds = seconds or 0.0
    total_ms = round(seconds * 1000)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def split_long_utterance(u: Utterance) -> list[Utterance]:
    """Break an utterance into shorter cues if it would overflow MAX_CUE_CHARS."""
    if len(u.text) <= MAX_CUE_CHARS or not u.words:
        return [u]

    chunks: list[Utterance] = []
    current_words = []
    current_len = 0
    for w in u.words:
        added = len(w.word) + 1
        if current_words and current_len + added > MAX_CUE_CHARS:
            chunks.append(_utterance_from_words(u.speaker, current_words))
            current_words, current_len = [], 0
        current_words.append(w)
        current_len += added
    if current_words:
        chunks.append(_utterance_from_words(u.speaker, current_words))
    return chunks


def _utterance_from_words(speaker, words) -> Utterance:
    return Utterance(
        text=" ".join(w.word for w in words),
        speaker=speaker,
        start=words[0].start,
        end=words[-1].end,
        words=words,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio")
    parser.add_argument("--out", default="output.srt")
    args = parser.parse_args()

    client = SpeechRevolutions()
    result = client.transcribe(args.audio, speaker_labels=True, word_timestamps=True)

    cues = [c for u in result.utterances for c in split_long_utterance(u)]

    lines = []
    for i, cue in enumerate(cues, start=1):
        speaker = f"{cue.speaker}: " if cue.speaker else ""
        lines.append(str(i))
        lines.append(f"{srt_timestamp(cue.start)} --> {srt_timestamp(cue.end)}")
        lines.append(f"{speaker}{cue.text}")
        lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"wrote {len(cues)} cue(s) to {args.out}")


if __name__ == "__main__":
    main()
