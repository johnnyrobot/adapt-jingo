# Deploying adapt-jingo

This repository is three deliverables, not one service. Deploy only the parts
you want — the second is optional and the third is required only if you want
graded pronunciation questions inside ADAPT.

| # | What | Required? |
|---|---|---|
| 1 | **`jingo`** — the pronunciation scoring service | Yes |
| 2 | **`jingo-tts`** — "Hear it" exemplar audio | Optional. Unset the URL and the button simply disappears. |
| 3 | **16 ADAPT patches** in `adapt-integration/` | Only for graded questions in ADAPT. The login-free practice embed also comes from here. |

**Deploy in that order.** The scorer is the only piece the others depend on.

The scorer has its own detailed walkthrough — model acquisition, records,
compose, reverse proxy, and two smoke tests — in
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). **Read that for step 1.** This file
covers what that walkthrough does not: the TTS service, the ADAPT side, content
authoring, and the traps that span all three.

---

## 1. The scorer, in brief

Follow [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). The short version:

```bash
# The model is not in git — ~300 MB, fetched and checksum-verified at deploy
# time against engine/src/jingo_engine/assets/model-manifest.json.
# `ensure` needs an explicit source: either --archive, or BOTH of these.
jingo-engine-model ensure \
  --model-dir /opt/libretexts/jingo/model/wav2vec2-xlsr-53-espeak-ct2 \
  --hf-repo johnnyrobotai/johnnylingo-jingo-wav2vec2-xlsr-53-espeak-ct2 \
  --hf-filename wav2vec2-xlsr-53-espeak-ct2-v0.2.1.zip

jingo-engine-model verify --model-dir /opt/libretexts/jingo/model/wav2vec2-xlsr-53-espeak-ct2

cd adapt-jingo
docker build -f service/Dockerfile -t jingo:local .    # build from the REPO ROOT
cd service && cp docker-compose.example.yml docker-compose.yml && docker compose up -d
```

Both source flags are required together — `ensure` with only `--model-dir`
fails with "ensure requires --archive or both --hf-repo and --hf-filename".
`model/README.md` documents the manual download-and-convert path as well.

Two things from that document are worth repeating here because they cause
silent wrong behaviour rather than errors:

- **The container must stay attached to ADAPT's `adapt_adapt` docker
  network.** Off it, the scorer cannot resolve object storage, returns
  `audio_unreachable`, and ADAPT falls back to completion credit. The gradebook
  fills in and looks correct; nothing was ever scored.
- **`JINGO_AUDIO_HOST_ALLOWLIST` is unset by default**, which permits fetching
  `audio_url` from any http(s) host. Pin it to your storage hostname in
  production to close the SSRF surface.

Health is at **`/health`**, not `/healthz`.

---

## 2. The TTS service (optional)

`jingo-tts` speaks the target word so a learner hears it before recording. It is
entirely independent: the scorer neither calls it nor knows it exists.

### 2.1 Choose an engine

`TTS_ENGINE` selects the backend. **Only Kokoro is installed by default**; the
others need either an uncommented dependency or your own cloud credentials.

| Engine | Cost | What you must supply |
|---|---|---|
| `kokoro` *(default)* | Free, self-hosted, Apache-2.0 | Model + voice files, ~350 MB |
| `piper` | Free, self-hosted | Uncomment `piper-tts` in `tts/requirements.txt` and rebuild; voice files |
| `polly` | **Paid AWS service** | Your own IAM key pair with `polly:SynthesizeSpeech` and `DescribeVoices` |
| `gemini` | **Paid Google service** | Your own API key |

Nothing in this repository contains a credential for any of them.

### 2.2 Fetch the Kokoro model

```bash
cd tts && ./scripts/fetch_kokoro.sh      # ~350 MB into ./kokoro
```

### 2.3 Run it

```bash
cp docker-compose.example.yml docker-compose.yml   # edit paths + origin
docker compose up -d
```

Binds `127.0.0.1:8010`. Front it with your reverse proxy the same way as the
scorer.

**Set `TTS_ALLOWED_ORIGIN` to your ADAPT origin.** It defaults to `*`, which is
convenient for a first smoke test and wrong for production.

### 2.4 Verify

```bash
curl -s https://tts.example.org/health | jq .
curl -s 'https://tts.example.org/say?text=perro&lang=es' -o /tmp/perro.mp3
```

`engine_available: false` means the engine has no usable model or credential.
That is **not fatal**: `/say` still serves anything already in the disk cache,
and only returns `503` for words it has never synthesized. A cache-only
deployment is a legitimate state — a prepared demo keeps working — but new
vocabulary will fail until the engine is usable again.

### 2.5 Pre-warming the cache

Synthesis is cached to disk, so the first play of each word is the slow one. To
warm it ahead of a demo, use `tts/scripts/cache_place.py` — and read the
[cache-key trap](#the-tts-cache-key-must-match-the-running-container) before you
do, because getting it wrong produces a cache that is silently never read.

---

## 3. The ADAPT side

Apply the patch set in [`adapt-integration/`](adapt-integration/INTEGRATION.md)
— 16 patches covering the question type, the recorder, "Hear it", word-level
feedback and the login-free practice embed.

You need **only this repository**; the patches carry everything ADAPT-side.

Afterwards:

```bash
npm i                    # picks up lamejs + vue-audio-recorder
npm run production       # the SPA is compiled — changes are invisible until you rebuild
php artisan migrate      # adds 'pronunciation' to questions.technology
```

Then set, in ADAPT's `.env`:

```dotenv
PRONUNCIATION_SERVICE_URL=https://jingo.example.org
PRONUNCIATION_TTS_URL=https://tts.example.org      # omit to hide the "Hear it" button
WEBWORK_JWT_SECRET=<the same value jingo uses>
```

`WEBWORK_JWT_SECRET` must be **byte-identical on both sides** — the scorer signs
the answer JWT and ADAPT verifies it with that shared secret. Read it out of
ADAPT's existing `.env` rather than inventing one.

**The service URL is baked into the page at load time**, so after changing it:
clear Laravel's config cache if you use one (`php artisan config:clear`), and
hard-reload any open tab. A stale tab posts to the old host, the fetch throws,
and ADAPT silently falls back to completion credit — which again looks like
success.

---

## 4. Content: records, packs, and new words

The scorer needs a **record** per exercise — the expected phoneme sequence it
compares a learner against. Records live under `JINGO_RECORDS_DIR` and are
**bind-mounted read-only**, so adding records takes effect without a rebuild.

Word lists are imported into ADAPT by CLI:

```bash
php artisan libretexts:import-language-pack
```

This is an **admin/CLI step with no instructor-facing UI**. Instructors work by
copying pronunciation questions from a pre-seeded course.

### Adding new words is a workstation task, not a server one

Generating a record requires grapheme-to-phoneme conversion, which needs the
espeak toolchain. **That toolchain is deliberately absent from the scorer
image** — it is GPL, and keeping it out is why the runtime image is not (see
`THIRD-PARTY.md`).

So the loop is: extend a pack and generate records on a workstation using
`authoring/gen_word_records.py` and `authoring/build_pack.py`, copy the results
into `JINGO_RECORDS_DIR` on the server, then re-import the pack in ADAPT. The
server never runs G2P.

---

## Traps

Five failure modes that produce no error message.

### The scorer detached from `adapt_adapt`

Covered above and in `docs/DEPLOYMENT.md` §5. Worth restating because it is the
worst of these: everything reports healthy, students receive credit, and no
pronunciation is ever scored. If you see repeated `audio_unreachable` in the
logs, check the network attachment before anything else.

### The TTS cache key must match the running container

`clip_key` derives the cache filename from the engine, voice, language, text
**and** any non-default rate, speed or padding. A clip written under a different
key is simply never found — `/say` re-synthesizes or 503s, and the cache appears
to do nothing.

This has already happened once: an earlier hand-rolled copy of the key logic in
the pre-warm script drifted from the service — it lacked the Polly engine tier
and the rate component — so on a Polly box with a non-default rate, **every clip
it placed landed at a key the service never looks up.** The script now imports
the service's own `app.clip_key`, which is why it must run with the same engine
and voice environment as the container:

```bash
TTS_ENGINE=polly python3 tts/scripts/cache_place.py /path/to/words_dir
```

Changing `TTS_ENGINE`, the voice, or `TTS_RATE` after warming invalidates the
whole cache by design — the audio genuinely differs. Old clips are not deleted,
just orphaned.

### `TTS_ALLOWED_ORIGIN` defaults to `*`

Fine for a smoke test. Set it to your ADAPT origin before anyone else can reach
the service.

### A CORS mismatch looks like a server fault and is not

`JINGO_ALLOWED_ORIGIN` must equal ADAPT's public origin exactly. A mismatch
appears only in the student's browser console; the scorer logs nothing, because
the request never arrives.

### The container port is not the host port

The scorer listens on **8000 inside the container**. The example compose
publishes it on a host port — check which one you actually bound before
pointing a reverse proxy at it. The same applies to `jingo-tts` on 8010.

---

## What this repository never contains

No credentials, no model weights, no voice files. The scorer model (~300 MB) is
fetched and checksum-verified at deploy time against
`engine/src/jingo_engine/assets/model-manifest.json`; Kokoro's model and voices
are fetched by `tts/scripts/fetch_kokoro.sh`. Licensing for all of it is in
[`THIRD-PARTY.md`](THIRD-PARTY.md).
