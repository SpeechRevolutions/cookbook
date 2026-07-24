"""Migrate from AssemblyAI without touching your downstream code.

AssemblyAI's SDK returns a transcript object with `.text` and `.utterances`.
The Speech Revolutions SDK mirrors that shape directly, so code written
against an AssemblyAI transcript works unchanged against `result` here.

    python from_assemblyai.py meeting.mp3
"""

import argparse

from speechrevolutions import SpeechRevolutions


# --- Downstream code, written against AssemblyAI's transcript object -------
# This function doesn't change at all when you switch providers.
def print_transcript(transcript) -> None:
    print(transcript.text)
    for utt in transcript.utterances:
        print(f"  speaker {utt.speaker}: {utt.text}")


# --- Before (AssemblyAI SDK) -------------------------------------------------
#     import assemblyai as aai
#     aai.settings.api_key = ASSEMBLYAI_API_KEY
#     config = aai.TranscriptionConfig(speaker_labels=True)
#     transcript = aai.Transcriber().transcribe(audio_path, config)
#     print_transcript(transcript)

# --- After (Speech Revolutions) ---------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio")
    args = parser.parse_args()

    client = SpeechRevolutions()  # reads SPEECHREVOLUTIONS_API_KEY
    result = client.transcribe(args.audio, speaker_labels=True)

    print_transcript(result)  # same .text / .utterances shape, same downstream code


if __name__ == "__main__":
    main()
