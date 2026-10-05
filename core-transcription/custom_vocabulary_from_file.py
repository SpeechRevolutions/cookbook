"""Bias transcription toward a domain glossary, and see what it changed.

`custom_vocabulary` nudges the model toward specific proper nouns, product
names, or jargon it would otherwise mis-hear. This loads a glossary from a
text file (one term per line, '#' comments and blank lines ignored),
transcribes the same audio with and without it, and prints the words that
differ.

Two passes over the same audio can differ slightly even with identical
settings (punctuation, casing, the odd word), so not every difference is the
glossary's doing. The recipe separates the changes that introduce a glossary
term from everything else, and only claims the former.

    python custom_vocabulary_from_file.py meeting.mp3 glossary.txt
"""

import argparse
import difflib
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

    changes = word_changes(baseline.text, biased.text)
    if not changes:
        print("\nno difference — the glossary changed nothing on this file")
        return

    from_glossary = [c for c in changes if introduces_term(*c, vocabulary)]
    other = [c for c in changes if c not in from_glossary]

    print(f"\n{len(from_glossary)} change(s) that bring in a glossary term:")
    for before, after in from_glossary:
        print(f"  {before or '(nothing)'!r} -> {after!r}")
    if not from_glossary:
        print("  (none — the glossary had no visible effect on this file)")

    if other:
        # Not attributed to the glossary: a second pass can differ on its own.
        print(f"\n{len(other)} other difference(s), not attributed to the glossary:")
        for before, after in other:
            print(f"  {before or '(nothing)'!r} -> {after or '(nothing)'!r}")


def word_changes(a: str, b: str) -> list[tuple[str, str]]:
    """The spans of words that differ between two transcripts, as (before, after)."""
    aw, bw = a.split(), b.split()
    matcher = difflib.SequenceMatcher(a=aw, b=bw, autojunk=False)
    return [
        (" ".join(aw[i1:i2]), " ".join(bw[j1:j2]))
        for op, i1, i2, j1, j2 in matcher.get_opcodes()
        if op != "equal"
    ]


def introduces_term(before: str, after: str, terms: list[str]) -> bool:
    """True if `after` contains a glossary term that `before` did not."""
    b, a = before.lower(), after.lower()
    return any(t.lower() in a and t.lower() not in b for t in terms)


if __name__ == "__main__":
    main()
