# Architecture

This document walks the full path a pronunciation submission takes: from a
student pressing record in ADAPT's browser SPA to a graded row in ADAPT's
gradebook. It also covers the guardrails that make (or silently break) real
scoring.

## Components

| Component | Repo location | Role |
|---|---|---|
| `PronunciationQuestion.vue` | ADAPT (patched in via [`adapt-integration/`](../adapt-integration/)) | Browser-side recorder + question UI |
| ADAPT backend | ADAPT (patched in via `adapt-integration/`) | Owns the assignment, the gradebook, and the JWT contract |
| Object storage (e.g. MinIO) | ADAPT's own deployment | Holds the uploaded audio |
| `service/` (jingo) | this repo | FastAPI `/score` endpoint (and the login-free `/practice-score`) — the network-facing scoring component |
| `engine/` (`jingo_engine`) | this repo | GOP scoring library used by `service/`; no network I/O of its own |
| `tts/` (`jingo-tts`) | this repo | Optional FastAPI `/say` endpoint (pluggable engine, default Kokoro-82M) for the "Hear it" exemplar button; independent of the scoring path |

## "Hear it" exemplar audio (optional, independent path)

Separate from scoring, ADAPT can offer a **🔊 Hear it** button that plays a model
pronunciation of the prompt. When `PronunciationQuestion.vue` is given a `ttsUrl`
(from ADAPT's `PRONUNCIATION_TTS_URL` → `window.config.pronunciationTtsUrl`), it
calls the [`tts/`](../tts/) service directly with the question's target word:

```
 PronunciationQuestion.vue ──GET /say?text=<word>&lang=<code>──▶ jingo-tts (Kokoro)
        ▲                                                            │
        └───  audio/mpeg, cached (see tts/README.md)  ──────────────◀┘
```

This path never touches the gradebook, object storage, or the JWT contract — it is a
read-only "listen before you record" aid. The component prefetches on render so the first
click is instant, and the service caches every clip to disk. See [`../tts/README.md`](../tts/README.md).

## End-to-end data flow

```
 ┌───────────────────────────┐
 │        Student            │
 │   (browser, ADAPT SPA)    │
 └─────────────┬─────────────┘
               │ 1. records audio in PronunciationQuestion.vue
               │    - energy-based VAD auto-stops the recording
               │    - client-side lamejs encodes PCM -> audio/mpeg (mp3)
               │      (ADAPT's upload endpoint only accepts audio/mpeg)
               │    - student presses explicit Submit
               ▼
 ┌───────────────────────────┐
 │   ADAPT backend           │ 2. mp3 bytes uploaded, stored in object
 │  POST /api/submission-    │    storage; ADAPT gets back a fetchable
 │  audios                   │    audio_url (e.g. a MinIO object URL)
 └─────────────┬─────────────┘
               │
               │ 3. the page already carries a problemJWT (standard
               │    ADAPT claims), the exercise_id and language from
               │    pronunciation_data, and the scorer's URL
               │    (window.config.pronunciationServiceUrl); the
               │    student's browser calls the scorer directly
               ▼
 ┌───────────────────────────┐
 │   jingo service           │ 4. fetches the mp3 from object storage
 │  POST /score              │    (server-side, over ADAPT's own docker
 │  (service/app/main.py)    │    network — see Guardrails below)
 └─────────────┬─────────────┘
               │
               │ 5. ffmpeg normalizes the audio to 16 kHz mono WAV
               ▼
 ┌───────────────────────────┐
 │   jingo_engine            │ 6. transcribes phonemes (GOP over a
 │  (engine/, CT2 wav2vec2)  │    CTranslate2-exported wav2vec2 phoneme
 └─────────────┬─────────────┘    model) and compares against the
               │                  exercise's reference phoneme record
               │
               │ 7. returns to the browser:
               │      - answerJWT: minimal, signed (WEBWORK_JWT_SECRET)
               │      - feedback.phoneme_scores: richer, unsigned,
               │        display-only per-phoneme breakdown
               ▼
 ┌───────────────────────────┐
 │   Student's browser       │ 8. renders per-phoneme chips from
 │  (PronunciationQuestion)  │    feedback.phoneme_scores, then posts
 └─────────────┬─────────────┘    the answerJWT, unchanged, to ADAPT
               ▼
 ┌───────────────────────────┐
 │   ADAPT backend           │ 9. verifies the answerJWT signature and
 │  POST /api/jwt/process-   │    records the grade in the gradebook
 │  answer-jwt               │
 └───────────────────────────┘
```

Because the browser calls `/score`, the scorer needs a URL the student's
browser can reach and a CORS origin that matches ADAPT's
(`JINGO_ALLOWED_ORIGIN`); see [`docs/DEPLOYMENT.md`](DEPLOYMENT.md) step 7.

**Practice mode:** an ungraded practice attempt skips object storage and the
gradebook entirely. The browser posts the mp3 straight to the login-free
`POST /practice-score`, which returns the feedback object only (no
`answerJWT`). It is bounded by `JINGO_MAX_UPLOAD_BYTES` and a per-IP rate
limit.

**Instructor preview:** the same `<pronunciation-question>` widget also renders
for instructors (`user.role === 2`) in the question preview, but with a
`preview` prop that disables the Record button and short-circuits
`startRecording()`/`submitForScoring()`. Instructors thus see exactly the
student widget without any mic capture, upload, or gradeback occurring. Without
this, a pronunciation question renders as a blank body in the instructor
"View Assessments" page (the recorder was previously gated to students only).

## Why two payloads come back from `/score`

`/score` returns two things with different trust levels and different
purposes:

- **`answerJWT`** — small, signed with the shared `WEBWORK_JWT_SECRET`. This
  is the only part ADAPT's backend trusts for grading. It follows the same
  problem/answer JWT contract ADAPT already uses for its WeBWorK and IMathAS
  engines, so `pronunciation` slots into the existing
  `POST /api/jwt/process-answer-jwt` path (see
  [`adapt-integration/INTEGRATION.md`](../adapt-integration/INTEGRATION.md))
  instead of requiring a new gradeback mechanism.
- **`feedback.phoneme_scores`** — a richer, unsigned object with per-phoneme
  scores and labels. This never touches the gradebook; it's passed straight
  through to `PronunciationQuestion.vue` so the student sees per-phoneme score
  chips immediately after submitting. Because it's display-only, it can be as
  verbose as is useful for learner feedback without expanding what the signed
  grading contract has to carry.

## Guardrails

- **Network placement is load-bearing, not optional.** The jingo service must
  be attached to the same docker network as ADAPT's object storage (in this
  repo's deployment docs, that's `adapt_adapt`, ADAPT's default network name;
  substitute your own if you deploy differently). If it isn't, step 4 above
  fails, but **not loudly**: `/health` still reports `engine_available: true`
  because the model loaded fine, and `/score` returns `feedback.status:
  "audio_unreachable"`. The service then falls back to completion credit — the
  gradebook looks populated and correct at a glance, but no phoneme scoring
  actually ran. See [`docs/DEPLOYMENT.md`](DEPLOYMENT.md) for how to verify
  network attachment.
- **Upload format is constrained by ADAPT, not by jingo.** ADAPT's
  `POST /api/submission-audios` endpoint only accepts `audio/mpeg`. That's why
  the recorder encodes to mp3 client-side with `lamejs` before uploading,
  rather than uploading raw PCM or a browser-native `audio/webm` recording.
  jingo's `ffmpeg` normalization step (16 kHz mono WAV) happens after fetch,
  independent of this constraint.
- **The `answerJWT` is the only trust boundary.** `problemJWT` (opaque to
  jingo, echoed back inside the `answerJWT`) and `feedback.phoneme_scores` are
  never independently verified by ADAPT — only the `answerJWT` signature is.
  Both sides must share the exact same `WEBWORK_JWT_SECRET` value; see
  [`docs/DEPLOYMENT.md`](DEPLOYMENT.md#security-considerations) for handling
  it as a secret.
- **Grading defaults to `completion`, not `score`.** Each drill in a
  language pack declares its grading (`completion` unless the drill says
  `score`), stored on the question's `pronunciation_data`. ADAPT applies it
  when it records the grade (`Submission.php`): score-based credit only when
  the drill says `score` and the scorer returned `scored` with an `overall`;
  for any other signed answer that matches the question, completion credit. An exam section can't override a drill's grading yet. The
  out-of-the-box behavior is credit for a valid, reachable submission. This
  keeps the (explicitly provisional — see the repo
  [README](../README.md#accuracy-disclaimer)) GOP score from being used as a
  high-stakes grade by default.

## Not covered here

- Deploying and configuring the service (env vars, model/records placement,
  reverse proxy): [`docs/DEPLOYMENT.md`](DEPLOYMENT.md).
- The exact ADAPT-side files and patches that wire up the `pronunciation`
  question type: [`adapt-integration/INTEGRATION.md`](../adapt-integration/INTEGRATION.md).
- Building/importing language packs (word lists + reference phoneme
  sequences): [`authoring/README.md`](../authoring/README.md).
