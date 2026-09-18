"""Run every published recipe, for real, against a stand-in API.

These are the recipes customers copy verbatim. None of them had ever been run
in CI, so a rename in the SDK or a change in the API shape would break published
code with nothing to catch it.

Each recipe runs as a SUBPROCESS, invoked the way its own docstring says to
invoke it, with `SPEECHREVOLUTIONS_BASE_URL` pointed at the mock. That is the
point: it exercises argparse, the `if __name__ == "__main__"` entry point, file
output and exit codes — not just an importable function. A recipe that only
works when you import it is not a working recipe.

Requires the mock from the python-sdk repo, which is the reference
implementation of the API contract:

    pytest --sdk-path ../python-sdk
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

COOKBOOK = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_recipe(recipe: str, *args: str, api, cwd: Path, expect_rc: int = 0,
               extra_env: dict | None = None) -> subprocess.CompletedProcess:
    """Invoke a recipe exactly as its docstring tells a user to."""
    env = {
        **os.environ,
        "SPEECHREVOLUTIONS_API_KEY": api.api_key,
        "SPEECHREVOLUTIONS_BASE_URL": api.base_url,
        "PYTHONPATH": os.environ.get("SR_SDK_SRC", ""),
        "PYTHONUNBUFFERED": "1",
        # tqdm writes control characters that make failures unreadable.
        "TQDM_DISABLE": "1",
    }
    env.update(extra_env or {})
    proc = subprocess.run(
        [sys.executable, str(COOKBOOK / recipe), *args],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != expect_rc:
        raise AssertionError(
            f"{recipe} exited {proc.returncode}, expected {expect_rc}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
    return proc


@pytest.fixture
def audio(tmp_path: Path) -> Path:
    p = tmp_path / "meeting.mp3"
    p.write_bytes(b"not really audio, the mock does not care" * 20)
    return p


# ---------------------------------------------------------------------------
# core-transcription
# ---------------------------------------------------------------------------

def test_transcribe_file_prints_the_transcript(api, audio, tmp_path):
    out = run_recipe("core-transcription/transcribe_file.py", str(audio),
                     api=api, cwd=tmp_path)
    assert "Good morning everyone." in out.stdout
    assert "[A]" in out.stdout, "speaker labels should be shown for json output"


def test_transcribe_file_saves_srt(api, audio, tmp_path):
    dest = tmp_path / "meeting.srt"
    run_recipe("core-transcription/transcribe_file.py", str(audio),
               "--output-type", "srt", "--out", str(dest), api=api, cwd=tmp_path)
    assert dest.exists()
    assert "-->" in dest.read_text()


def test_transcribe_file_honours_the_no_flags(api, audio, tmp_path):
    run_recipe("core-transcription/transcribe_file.py", str(audio),
               "--no-speaker-labels", "--no-word-timestamps", api=api, cwd=tmp_path)
    opts = api.only_job().options
    assert opts["speaker_labels"] is False
    assert opts["word_timestamps"] is False


def test_transcribe_file_exits_nonzero_on_failure(api, audio, tmp_path):
    api.fail_job_at = "gpu_timestamps"
    out = run_recipe("core-transcription/transcribe_file.py", str(audio),
                     api=api, cwd=tmp_path, expect_rc=1)
    assert "failed" in out.stderr.lower()


def test_transcribe_url_writes_the_transcript(api, tmp_path):
    dest = tmp_path / "episode.txt"
    run_recipe("core-transcription/transcribe_url.py",
               "https://example.com/episode-42.mp3", "--out", str(dest),
               api=api, cwd=tmp_path)
    assert dest.exists() and dest.read_text().strip()
    # The whole point of this recipe: the platform fetches it, we upload nothing.
    assert not api.paths("PUT")


def test_transcribe_batch_of_files(api, tmp_path):
    src = tmp_path / "audio"
    src.mkdir()
    for i in range(3):
        (src / f"clip{i}.mp3").write_bytes(b"audio" * 50)
    out = run_recipe("core-transcription/transcribe_batch_of_files.py", str(src),
                     api=api, cwd=tmp_path)
    assert len(api.jobs) == 3, "one job per input file"
    assert out.stdout.strip()


def test_retry_and_error_handling_runs_clean(api, audio, tmp_path):
    out = run_recipe("core-transcription/retry_and_error_handling.py", str(audio),
                     api=api, cwd=tmp_path)
    assert "Good morning everyone." in out.stdout


def test_retry_and_error_handling_reports_a_missing_file_cleanly(api, tmp_path):
    """The recipe is about handling failures; the likeliest one is a bad path.

    It must not exit with a raw traceback — that is the exact experience it
    exists to teach people to avoid.
    """
    out = run_recipe("core-transcription/retry_and_error_handling.py", "nope.mp3",
                     api=api, cwd=tmp_path, expect_rc=1)
    assert "no such file" in out.stderr.lower()
    assert "Traceback" not in out.stderr


def test_retry_and_error_handling_surfaces_a_server_side_failure(api, audio, tmp_path):
    api.fail_job_at = "gpu_timestamps"
    out = run_recipe("core-transcription/retry_and_error_handling.py", str(audio),
                     api=api, cwd=tmp_path)
    assert "job failed at step=" in out.stdout
    assert "Traceback" not in out.stderr


def test_custom_vocabulary_from_file(api, audio, tmp_path):
    glossary = tmp_path / "terms.txt"
    glossary.write_text("Kubernetes\nPostgres\n# a comment\n\nZephyr\n")
    out = run_recipe("core-transcription/custom_vocabulary_from_file.py",
                     str(audio), str(glossary), api=api, cwd=tmp_path)

    # The recipe deliberately runs TWICE — a baseline and a biased pass — so the
    # reader can see what the glossary changed.
    assert len(api.jobs) == 2, "expected a baseline and a biased transcription"
    vocabs = [j.options.get("custom_vocabulary") for j in api.jobs.values()]
    assert None in vocabs or [] in vocabs, "one pass should carry no vocabulary"
    biased = [v for v in vocabs if v]
    assert biased and {"Kubernetes", "Postgres", "Zephyr"} <= set(biased[0])
    # Comments and blank lines are stripped by load_glossary.
    assert "# a comment" not in biased[0]
    assert "loaded 3 term(s)" in out.stdout


# ---------------------------------------------------------------------------
# diarization
# ---------------------------------------------------------------------------

def test_speaker_labelled_transcript(api, audio, tmp_path):
    out = run_recipe("diarization/speaker_labelled_transcript.py", str(audio),
                     api=api, cwd=tmp_path)
    assert "Good morning everyone." in out.stdout
    assert "Thanks for joining." in out.stdout


def test_speaker_labelled_srt(api, audio, tmp_path):
    dest = tmp_path / "panel.srt"
    run_recipe("diarization/speaker_labelled_srt.py", str(audio),
               "--out", str(dest), api=api, cwd=tmp_path)
    text = dest.read_text()
    assert "-->" in text
    assert "Speaker" in text or "A:" in text, "cues should carry a speaker prefix"
    # Valid SRT: the first cue is numbered 1.
    assert text.lstrip().startswith("1")


# ---------------------------------------------------------------------------
# subtitles
# ---------------------------------------------------------------------------

def test_generate_srt_and_vtt(api, audio, tmp_path):
    run_recipe("subtitles/generate_srt_and_vtt.py", str(audio),
               "--out-stem", str(tmp_path / "movie"), api=api, cwd=tmp_path)
    srt, vtt = tmp_path / "movie.srt", tmp_path / "movie.vtt"
    assert srt.exists() and vtt.exists()
    assert "-->" in srt.read_text()
    assert vtt.read_text().lstrip().startswith("WEBVTT")


def test_subtitles_by_word_count(api, audio, tmp_path):
    dest = tmp_path / "short.srt"
    run_recipe("subtitles/subtitles_by_word_count.py", str(audio),
               "--words-per-cue", "2", "--out", str(dest), api=api, cwd=tmp_path)
    text = dest.read_text()
    assert "-->" in text
    # 6 words at 2 per cue is 3 cues.
    assert text.count("-->") == 3, f"expected 3 cues, got {text.count('-->')}"


# ---------------------------------------------------------------------------
# migrations
# ---------------------------------------------------------------------------

def test_migration_from_assemblyai(api, audio, tmp_path):
    out = run_recipe("migrations/from_assemblyai.py", str(audio), api=api, cwd=tmp_path)
    assert out.stdout.strip()


def test_migration_from_deepgram(api, audio, tmp_path):
    out = run_recipe("migrations/from_deepgram.py", str(audio), api=api, cwd=tmp_path)
    assert out.stdout.strip()


# ---------------------------------------------------------------------------
# Every recipe is at least syntactically importable
# ---------------------------------------------------------------------------

RECIPES = sorted(
    str(p.relative_to(COOKBOOK))
    for p in COOKBOOK.rglob("*.py")
    if "tests" not in p.parts
)


def test_the_recipe_inventory_is_what_we_think_it_is():
    assert len(RECIPES) >= 13, f"recipes appeared or vanished: {RECIPES}"


@pytest.mark.parametrize("recipe", RECIPES)
def test_recipe_compiles(recipe):
    """Catches a syntax error in a recipe nothing else drives."""
    src = (COOKBOOK / recipe).read_text()
    compile(src, recipe, "exec")


@pytest.mark.parametrize("recipe", RECIPES)
def test_recipe_has_a_usage_docstring(recipe):
    """Every recipe is copy-paste material; it must say how to run it."""
    src = (COOKBOOK / recipe).read_text().lstrip()
    assert src.startswith('"""'), f"{recipe} has no module docstring"
    doc = src.split('"""')[1]
    assert "python " in doc or "uvicorn " in doc, (
        f"{recipe}'s docstring never shows how to run it"
    )
