# Speech Revolutions Cookbook

Code examples, guides, and recipes for using the Speech Revolutions
speech-to-text API — the fuller, runnable counterpart to the short snippets
in the [docs](https://github.com/SpeechRevolutions/docs). Most recipes are
Python; a couple that are inherently server-side (webhooks) also have a
JavaScript/Node version. The concepts apply to any of the [official
SDKs](https://github.com/SpeechRevolutions) (Python, JavaScript/TypeScript,
Go, C#).

You'll need a Speech Revolutions account and API key — see
[Getting Started](https://docs.speechrevolutions.com/getting-started).

```bash
pip install -r requirements.txt
export SPEECHREVOLUTIONS_API_KEY=stt_...
```

## Core transcription

| Recipe | Description |
|---|---|
| [transcribe_file.py](core-transcription/transcribe_file.py) | Transcribe a local file or URL from the command line |
| [transcribe_url.py](core-transcription/transcribe_url.py) | Transcribe audio straight from a URL, no download step |
| [transcribe_batch_of_files.py](core-transcription/transcribe_batch_of_files.py) | Transcribe every file in a directory, submitted in parallel |
| [custom_vocabulary_from_file.py](core-transcription/custom_vocabulary_from_file.py) | Bias transcription toward a domain glossary and diff the effect |
| [retry_and_error_handling.py](core-transcription/retry_and_error_handling.py) | Handle every SDK exception, plus a manual rate-limit backoff loop |

## Speaker diarization

| Recipe | Description |
|---|---|
| [speaker_labelled_transcript.py](diarization/speaker_labelled_transcript.py) | Print a timestamped, speaker-labelled conversation log |
| [speaker_labelled_srt.py](diarization/speaker_labelled_srt.py) | Generate subtitles with "Speaker X:" prefixes on each cue |

## Subtitles

| Recipe | Description |
|---|---|
| [generate_srt_and_vtt.py](subtitles/generate_srt_and_vtt.py) | Get ready-made SRT/WebVTT files straight from the API |
| [subtitles_by_word_count.py](subtitles/subtitles_by_word_count.py) | Build short, caption-style cues capped at N words each |

## Webhooks

| Recipe | Description |
|---|---|
| [webhook_receiver_fastapi.py](webhooks/webhook_receiver_fastapi.py) | A runnable FastAPI server that submits jobs and verifies incoming webhooks |
| [webhook_receiver_express.mjs](webhooks/webhook_receiver_express.mjs) | The same thing in Node/Express |

## Live progress

| Recipe | Description |
|---|---|
| [live_progress_webapp.py](live-progress/live_progress_webapp.py) | A small full-stack app with a live upload + transcription progress bar |

## Migrating from another provider

| Recipe | Description |
|---|---|
| [from_deepgram.py](migrations/from_deepgram.py) | Keep Deepgram-shaped downstream code working via `result.to_deepgram()` |
| [from_assemblyai.py](migrations/from_assemblyai.py) | Keep AssemblyAI-style `.text` / `.utterances` code working unchanged |

See the [migration playbook](https://docs.speechrevolutions.com/migrate/playbook)
for a broader walkthrough, including OpenAI Whisper and ElevenLabs.

## Integrations

| Recipe | Description |
|---|---|
| [transcribe_from_s3.py](integrations/transcribe_from_s3.py) | Transcribe audio stored in a private S3 bucket (presigned URL or direct upload) |

---

Every recipe reads its API key from `SPEECHREVOLUTIONS_API_KEY` (or the
legacy `STT_API_KEY`). Questions or requests for a recipe that isn't here
yet — open an issue.
