# AGENTS.md

jingo is the phoneme-level pronunciation scorer for LibreTexts ADAPT's `pronunciation` question type. It is a single MIT Python repo containing: a scoring **library** (`engine/`, torch-free at runtime), a FastAPI **scoring service** (`service/`), an optional FastAPI **TTS service** (`tts/`), build-time **authoring** tools (`authoring/`), and the **ADAPT-side patch series** (`adapt-integration/`). Stack: Python 3.10+, FastAPI/uvicorn, `ctranslate2` + `numpy`, Docker.

## Setup

- Requires Python 3.10+. Each service has its own dependency file — install what you're working on:
  - Engine: `pip install ./engine` (runtime deps `numpy`, `ctranslate2`). For authoring/G2P add the extra: `pip install 'jingo_engine[g2p]'` (pulls `phonemizer` + `espeakng-loader`; needs system `espeak-ng`; Mac/Linux only).
  - Scoring service: `pip install -r service/requirements.txt`.
  - TTS service: `pip install -r tts/requirements.txt` (tests: `-r tts/requirements-dev.txt`).
- **Assets are not bundled.** Obtain the acoustic model (CT2 conversion of `facebook/wav2vec2-xlsr-53-espeak-cv-ft`) per `model/README.md`; fetch TTS voices with `tts/scripts/fetch_kokoro.sh`.

## Build & Run

- **Scoring service (Docker, from repo root):** `docker build -f service/Dockerfile -t jingo:local .` — the build context is the repo root because it installs the sibling `engine/` source. Then run via `service/docker-compose.example.yml` (copy to `docker-compose.yml`, add `.env` with `WEBWORK_JWT_SECRET`, keep the external `adapt_adapt` network). Local dev: `cd service && uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- **TTS service:** `cd tts && ./scripts/fetch_kokoro.sh && docker compose -f docker-compose.example.yml up -d --build` (serves on `:8010`; default engine `kokoro`, open-source, no key).
- **Authoring → pack → ADAPT:** `python authoring/build_pack.py --language es --out pack.json`, then inside ADAPT `php artisan libretexts:import-language-pack pack.json`.
- **ADAPT integration:** apply the ordered patch series onto upstream ADAPT with `git am adapt-integration/patches/*.patch` (`git am -3` if the tree diverged), then rebuild the SPA (`npm i && npm run …`) and `php artisan migrate`.

## Testing

- Tests are `pytest`, colocated per service:
  - `cd service && pytest` — `test_score_endpoint`, `test_audio`, `test_audio_upload`, `test_jwt_util`, `test_practice_score`, `test_provider`.
  - `cd tts && pytest` — `test_say`.
- `engine/` has no dedicated test suite; it is validated through the service tests.
- **Before a change is done:** the `pytest` suite for the part you touched must pass. There is no repo-wide test runner or lint step.

## Code Style

- Python 3.10+, type hints, FastAPI idioms. Keep `engine/` free of Torch at runtime.
- Tunable behavior belongs in JSON assets, not code — the scoring curve and phoneme rules live in `engine/src/jingo_engine/assets/calibration-v1.json`.
- Keep the GPL G2P toolchain confined to `authoring/`; never import it into `engine/`, `service/`, or `tts/`.

## Commit & PR Conventions

- Git repo. Use `feat:` / `fix:` commit prefixes (see existing `adapt-integration/patches/`).
- ADAPT-side changes are delivered as an ordered patch series (`patches/000N-*.patch`), not as a fork — keep new ADAPT edits in that form.
- `.gitignore` excludes `model/*/`, `.venv/`, `__pycache__/`, `*.egg-info/`. Never commit model weights or secrets.

## Security & Data

- Secrets (`WEBWORK_JWT_SECRET`, `GEMINI_API_KEY`, `POLLY_ACCESS_KEY_ID`/`POLLY_SECRET_ACCESS_KEY`) come from `.env` only — never commit them. `WEBWORK_JWT_SECRET` must equal ADAPT's.
- No acoustic-model weights in git; they are fetched/exported at deploy time.
- Student audio is fetched from object storage (MinIO) at scoring time and not persisted by the service.
- The GPL espeak/phonemizer toolchain is build-time only and must never run on a production/deployment host.
- Output is **provisional** (`provisional: true`) — a practice aid, not a clinical, certification, or high-stakes assessment tool. Don't represent it as validated.
