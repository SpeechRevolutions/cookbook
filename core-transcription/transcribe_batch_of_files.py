"""Transcribe every audio file in a directory, in parallel.

Submits every file first (each `submit()` call returns as soon as the audio is
enqueued — no held connection), then polls the pending set until all jobs are
done. This is the pattern for throughput: hundreds of files bound by the
platform's capacity, not by how many sockets your script can hold open.

    python transcribe_batch_of_files.py ./audio --pattern "*.mp3" --out ./transcripts
"""

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from speechrevolutions import SpeechRevolutions
from speechrevolutions.exceptions import STTError


def submit_all(client: SpeechRevolutions, paths: list[Path], *, workers: int) -> dict[str, Path]:
    jobs: dict[str, Path] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(client.submit, str(p)): p for p in paths}
        for fut in as_completed(futures):
            path = futures[fut]
            try:
                jobs[fut.result()] = path
            except STTError as e:
                print(f"  FAILED submit  {path.name}: {e}")
    return jobs


def gather(client: SpeechRevolutions, jobs: dict[str, Path], out_dir: Path, *, interval: float) -> None:
    pending = set(jobs)
    while pending:
        for job_id in list(pending):
            status = client.get_job_status(job_id)
            if status.is_completed:
                result = client.get_transcript(job_id)
                out_path = out_dir / f"{jobs[job_id].stem}.txt"
                out_path.write_text(result.text, encoding="utf-8")
                print(f"  done  {jobs[job_id].name} -> {out_path}")
                pending.discard(job_id)
            elif status.is_failed:
                print(f"  FAILED  {jobs[job_id].name}: {status.failed_stage} {status.reason}")
                pending.discard(job_id)
        if pending:
            time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    parser.add_argument("--pattern", default="*.mp3")
    parser.add_argument("--out", default="./transcripts")
    parser.add_argument("--workers", type=int, default=8, help="parallel submissions")
    parser.add_argument("--poll-interval", type=float, default=3.0)
    args = parser.parse_args()

    paths = sorted(Path(args.directory).glob(args.pattern))
    if not paths:
        raise SystemExit(f"no files matching {args.pattern} in {args.directory}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    client = SpeechRevolutions()
    jobs = submit_all(client, paths, workers=args.workers)
    print(f"submitted {len(jobs)}/{len(paths)} job(s)")
    gather(client, jobs, out_dir, interval=args.poll_interval)


if __name__ == "__main__":
    main()
