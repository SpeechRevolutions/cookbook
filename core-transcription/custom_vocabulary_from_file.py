"""Bias transcription toward a domain glossary, and see the effect.

`custom_vocabulary` nudges the model toward specific proper nouns, product
names, or jargon it would otherwise mis-hear. This loads a glossary from a
text file (one term per line, '#' comments and blank lines ignored) and
transcribes the same audio with and without it, so you can see exactly which
words changed.

    python custom_vocabulary_from_file.py meeting.mp3 glossary.txt
"""

import argparse
from pathlib import Path

from speechrevolutions import SpeechRevolutions


def load_glossary(path: str) -> list[str]:
    terms = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            terms.append(line)
    return terms


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio")
    parser.add_argument("glossary", help="text file, one term per line")
    args = parser.parse_args()

    vocabulary = load_glossary(args.glossary)
    print(f"loaded {len(vocabulary)} term(s): {', '.join(vocabulary[:10])}{' ...' if len(vocabulary) > 10 else ''}")

    client = SpeechRevolutions()

    baseline = client.transcribe(args.audio, word_timestamps=False, speaker_labels=False)
    biased = client.transcribe(
        args.audio, word_timestamps=False, speaker_labels=False, custom_vocabulary=vocabulary
    )

    if baseline.text == biased.text:
        print("\nno difference — none of the glossary terms were affected on this file")
        return

    print("\n--- without custom_vocabulary ---")
    print(baseline.text)
    print("\n--- with custom_vocabulary ---")
    print(biased.text)


if __name__ == "__main__":
    main()
