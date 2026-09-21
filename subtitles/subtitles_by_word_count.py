"""Build short, caption-style subtitles capped at N words per cue.

The server's `output_type="srt"` chunks cues by its own logic (roughly one
per sentence/utterance), which can run long for fast talkers. This recipe
builds cues client-side from the word-level JSON transcript instead, capping
every cue at a fixed word count — the standard "easy to read at a glance"
caption style.

    python subtitles_by_word_count.py talk.mp4 --words-per-cue 6 --out talk.srt
"""


from __future__ import annotations

import argparse

from speechrevolutions import SpeechRevolutions


def srt_timestamp(seconds: float | None) -> str:
    seconds = seconds or 0.0
    total_ms = round(seconds * 1000)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def chunk_words(words, words_per_cue: int):
    for i in range(0, len(words), words_per_cue):
        yield words[i : i + words_per_cue]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio")
    parser.add_argument("--words-per-cue", type=int, default=6)
    parser.add_argument("--out", default="output.srt")
    args = parser.parse_args()

    client = SpeechRevolutions()
    result = client.transcribe(args.audio, word_timestamps=True)

    lines = []
    for i, group in enumerate(chunk_words(result.words, args.words_per_cue), start=1):
        timed = [w for w in group if w.start is not None and w.end is not None]
        start = timed[0].start if timed else 0.0
        end = timed[-1].end if timed else 0.0
        text = " ".join(w.word for w in group)
        lines += [str(i), f"{srt_timestamp(start)} --> {srt_timestamp(end)}", text, ""]

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"wrote {(len(lines) + 1) // 4} cue(s) to {args.out}")


if __name__ == "__main__":
    main()
