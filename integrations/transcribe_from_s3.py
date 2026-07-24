"""Transcribe audio stored in a private S3 bucket.

Two ways to hand S3 audio to the API, depending on how the bucket is reachable:

  --presign   Generate a short-lived presigned URL and let the API fetch it
              directly (transcribe_url). No bytes pass through this script —
              cheaper and faster for large files. Requires the bucket to be
              reachable from the API over the public internet.

  (default)   Download the object here and upload the bytes (transcribe).
              Works even for buckets that aren't publicly reachable (e.g.
              VPC-restricted), at the cost of routing the audio through
              wherever this script runs.

    pip install boto3
    python transcribe_from_s3.py my-bucket recordings/meeting.mp3
    python transcribe_from_s3.py my-bucket recordings/meeting.mp3 --presign
"""

import argparse

import boto3
from speechrevolutions import SpeechRevolutions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bucket")
    parser.add_argument("key")
    parser.add_argument("--presign", action="store_true")
    parser.add_argument("--presign-expires", type=int, default=3600, help="seconds")
    args = parser.parse_args()

    s3 = boto3.client("s3")
    client = SpeechRevolutions()

    if args.presign:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": args.bucket, "Key": args.key},
            ExpiresIn=args.presign_expires,
        )
        result = client.transcribe_url(url)
    else:
        obj = s3.get_object(Bucket=args.bucket, Key=args.key)
        audio_bytes = obj["Body"].read()
        result = client.transcribe(audio_bytes)

    print(result.text)


if __name__ == "__main__":
    main()
