/**
 * A runnable Express server that submits jobs and receives their webhooks.
 *
 *   npm install express @speechrevolutions/stt
 *   export SR_WEBHOOK_SECRET=...        # the signing secret from your dashboard
 *   node webhook_receiver_express.mjs
 *
 *   curl -X POST "http://localhost:8000/transcribe?audio=https://example.com/audio.mp3"
 *
 * Point `callbackUrl` at a URL this server is reachable at (e.g. an ngrok
 * tunnel during local development).
 */

import { createHmac, timingSafeEqual } from "node:crypto";
import express from "express";
import { SpeechRevolutions } from "@speechrevolutions/stt";

const client = new SpeechRevolutions(); // reads SPEECHREVOLUTIONS_API_KEY
const SECRET = process.env.SR_WEBHOOK_SECRET;

// In-memory for this recipe; use a real datastore in production.
const JOBS = new Map();

function verifySignature(rawBody, signatureHeader, secret) {
  const expected = "sha256=" + createHmac("sha256", secret).update(rawBody).digest("hex");
  const a = Buffer.from(expected);
  const b = Buffer.from(signatureHeader ?? "");
  return a.length === b.length && timingSafeEqual(a, b);
}

const app = express();

app.post("/transcribe", express.json(), async (req, res) => {
  const audio = req.query.audio;
  const callbackBaseUrl = req.query.callback_base_url ?? "http://localhost:8000";
  const jobId = await client.submit(audio, {
    callbackUrl: `${callbackBaseUrl}/webhooks/speechrevolutions`,
  });
  JOBS.set(jobId, { status: "processing" });
  res.json({ job_id: jobId });
});

app.get("/transcribe/:jobId", (req, res) => {
  const job = JOBS.get(req.params.jobId);
  if (!job) return res.status(404).json({ error: "unknown job_id" });
  res.json(job);
});

// Capture the RAW body — the signature is computed over the exact bytes sent.
app.post("/webhooks/speechrevolutions", express.raw({ type: "application/json" }), async (req, res) => {
  if (!verifySignature(req.body, req.get("X-SR-Signature"), SECRET)) {
    return res.status(401).send("bad signature");
  }

  const event = JSON.parse(req.body.toString());

  if (event.status === "completed") {
    const result = await client.getTranscript(event.job_id);
    JOBS.set(event.job_id, { status: "completed", text: result.text });
  } else {
    JOBS.set(event.job_id, { status: "failed", step: event.step, reason: event.reason });
  }

  res.json({ ok: true }); // a 2xx acks delivery; the platform retries on 5xx
});

app.listen(8000, () => console.log("listening on http://localhost:8000"));
