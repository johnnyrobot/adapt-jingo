# CLAUDE.md

**jingo** is the pronunciation-assessment engine behind LibreTexts [ADAPT](https://adapt.libretexts.org)'s `pronunciation` question type. It scores a learner's recorded audio at the phoneme level (Goodness of Pronunciation over a CTranslate2 wav2vec2 phone-CTC model) and returns a signed answer JWT to ADAPT's gradebook. This is a single MIT repo of four independent parts plus an optional TTS service.

## Architecture

Five top-level parts, each with its own README — read the relevant one before working in it:

- `engine/` — `jingo_engine` (PyPI name `johnnylingo-jingo`, v0.2.1). The scoring library: forced alignment + GOP over a CT2 wav2vec2 model. **Torch-free at runtime** (only `numpy` + `ctranslate2`). Entry: `jingo_engine.Engine(EngineConfig(...)).score(wav, record)`. Source in `engine/src/jingo_engine/` (`engine.py`, `gop.py`, `calibration.py`, `contract.py`, `model_assets.py`).
- `service/` — thin FastAPI adapter around the engine. Entry `service/app/main.py` (`uvicorn app.main:app`). Exposes `POST /score` and `GET /health`; verifies/signs WeBWorK JWTs (`app/jwt_util.py`), fetches student audio (`app/audio.py`).
- `tts/` — `jingo-tts`, a small FastAPI text-to-speech service for the "🔊 Hear it" button. Entry `tts/app/main.py`. Pluggable engine via `TTS_ENGINE` (`app/provider.py`). `GET /say?text=&lang=`, `GET /health`.
- `authoring/` — build-time, **Mac-only** grapheme-to-phoneme tools that construct language packs (`build_pack.py`, `gen_word_records.py`, `augment_spanish_pack.py`). Uses the GPL espeak toolchain — never shipped or run on a server.
- `adapt-integration/` — the ADAPT-side wiring as a 15-patch series (`patches/*.patch`) plus clean copy-in `files/`. See `adapt-integration/INTEGRATION.md`.
- `model/` — README only (no weights committed). `docs/` — `ARCHITECTURE.md`, `DEPLOYMENT.md`, `ROADMAP.md`.

**Data flow:** learner records in ADAPT → audio uploaded to object storage (MinIO) → ADAPT calls `service` `/score` → `engine` scores the audio's phonemes against the exercise's reference record → service returns a score + per-phoneme breakdown as a signed `answerJWT` → ADAPT posts it to its gradebook.

## Commands

```bash
# Engine (library)
pip install ./engine                 # runtime: numpy + ctranslate2
pip install 'jingo_engine[g2p]'      # + phonemizer/espeakng-loader for authoring

# Scoring service — build from the REPO ROOT (image installs sibling engine/)
docker build -f service/Dockerfile -t jingo:local .
cp service/docker-compose.example.yml service/docker-compose.yml   # add .env w/ WEBWORK_JWT_SECRET
cd service && docker compose up -d                                 # -> 127.0.0.1:8000
uvicorn app.main:app --host 0.0.0.0 --port 8000                    # local run (from service/)

# TTS service
cd tts && ./scripts/fetch_kokoro.sh                                # fetch model + voices (not committed)
docker compose -f docker-compose.example.yml up -d --build         # -> :8010

# Tests (pytest; per subproject)
cd service && pytest        # score endpoint, audio, jwt, provider, practice-score
cd tts && pytest            # requires tts/requirements-dev.txt (pytest, httpx)

# Authoring (Mac only) -> import into ADAPT
python authoring/build_pack.py --language es --out pack.json
php artisan libretexts:import-language-pack pack.json              # run inside ADAPT
```

`engine/` has no test directory — it is exercised through the `service/` suite. No repo-wide lint config found.

## Conventions

- Python 3.10+. Keep `engine/` **torch-free at runtime** (numpy + ctranslate2 only); Torch belongs only in offline model export.
- Scoring is tuned through a **swappable JSON asset**, not code: `engine/src/jingo_engine/assets/calibration-v1.json` holds the logistic `curve {midpoint, slope}`, `weak_tag_threshold`, `unreliable_phones`, `equivalence_classes`, `uncertainty`.
- Each part is independently licensed/MIT and self-hostable; the optional Amazon Polly TTS voice is the one opt-in proprietary path.
- Commit prefixes follow `feat:`/`fix:` (see `adapt-integration/patches/`). ADAPT-side edits ship as an ordered patch series, not a fork.

## Gotchas & Constraints

- **Build the service image from the repo root** (`context: ..`). It installs `engine/` from the sibling directory; building from inside `service/` fails.
- **The service compose must stay attached to the external `adapt_adapt` network** so it can resolve ADAPT's `minio` container to fetch audio. Detached → `audio_unreachable` → silent fallback to *completion credit* (looks fine, never actually scores). Never recreate the container without that network.
- **Changing the calibration curve requires rebuilding the jingo image** (`docker compose build`) + restart — the JSON is baked into the package at install time; a plain restart does not pick it up.
- **No model weights are committed** (`model/*/` is gitignored). The engine fetches/exports `facebook/wav2vec2-xlsr-53-espeak-cv-ft` → CTranslate2 at deploy time.
- **G2P (phonemizer/espeak-ng, GPL) is build-time only** — it lives in `authoring/`, never in the shipped engine and never on a production box.
- `WEBWORK_JWT_SECRET` must match ADAPT's; `GEMINI_API_KEY`, `POLLY_*` are opt-in. Provide all via `.env`, never commit. Without TTS creds the TTS service is cache-only.
- Scores are **provisional** (`provisional: true`) — a practice/feedback aid, not a validated, clinical, or high-stakes assessment. Do not present them as verified.
