"""Generate ready-to-use SRT and WebVTT subtitle files.

Setting `output_type` to "srt" or "vtt" returns fully formatted subtitle
bytes from the server — no client-side cue formatting needed. This is the
quickest way to get a subtitle file. The server groups consecutive words into
readable cues: at most two lines of 42 characters and 7 seconds per cue, with a
new cue at a pause of more than a second or at the end of a sentence. No cue
spans two speakers, and with speaker labels on (the default) each cue's first
line starts with "SPEAKER_N: "; pass `speaker_labels=False` to drop the prefix.

See speaker_labelled_srt.py to build speaker cues yourself (e.g. with real
names), or subtitles_by_word_count.py for shorter, fixed-length cues.

    python generate_srt_and_vtt.py movie.mp4
"""

import argparse
from pathlib import Path

from speechrevolutions import SpeechRevolutions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio")
    parser.add_argument("--out-stem", help="defaults to the input filename without extension")
    args = parser.parse_args()

    stem = args.out_stem or Path(args.audio).stem
    client = SpeechRevolutions()

    srt = client.transcribe(args.audio, output_type="srt")
    srt_path = srt.save(stem)
    print(f"wrote {srt_path}")

    vtt = client.transcribe(args.audio, output_type="vtt")
    vtt_path = vtt.save(stem)
    print(f"wrote {vtt_path}")


if __name__ == "__main__":
    main()
