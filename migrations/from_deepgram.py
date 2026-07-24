"""Migrate from Deepgram without touching your downstream code.

If you have existing code that walks a Deepgram-shaped response (a common
pattern once transcript-processing logic is written and tested), you don't
have to rewrite it — `result.to_deepgram()` returns that same shape.

    python from_deepgram.py meeting.mp3
"""

import argparse

from speechrevolutions import SpeechRevolutions


# --- Downstream code, written against Deepgram's response shape -------------
# This function doesn't change at all when you switch providers.
def print_transcript(deepgram_response: dict) -> None:
    alt = deepgram_response["results"]["channels"][0]["alternatives"][0]
    print(alt["transcript"])
    for utt in deepgram_response["results"].get("utterances", []):
        print(f"  speaker {utt['speaker']}: {utt['transcript']}")


# --- Before (Deepgram SDK) ---------------------------------------------------
#     from deepgram import DeepgramClient, PrerecordedOptions
#     dg = DeepgramClient(DEEPGRAM_API_KEY)
#     response = dg.listen.rest.v("1").transcribe_file(
#         {"buffer": audio_bytes}, PrerecordedOptions(model="nova-3", diarize=True)
#     )
#     print_transcript(response.to_dict())

# --- After (Speech Revolutions) ---------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio")
    args = parser.parse_args()

    client = SpeechRevolutions()  # reads SPEECHREVOLUTIONS_API_KEY
    result = client.transcribe(args.audio, speaker_labels=True)

    print_transcript(result.to_deepgram())  # same shape, same downstream code


if __name__ == "__main__":
    main()
