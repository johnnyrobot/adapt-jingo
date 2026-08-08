# Archived TTS engine configs — **not deployable**

Nothing here is live. The deployable template is `../docker-compose.example.yml`.

These are the two **open-source** engine configurations that ran on the box before the 2026-07-10
switch to Amazon Polly. They are preserved because Polly is a **proprietary dependency taken as a
deliberate, owner-approved exception** to LibreTexts' open-source-only rule — so the working
open-source configurations are the documented way back, and they existed nowhere but the VPS.

| file | engine | why it was replaced |
|---|---|---|
| `docker-compose.yml.kokoro` | Kokoro ONNX (`KOKORO_MODEL_PATH`, `KOKORO_VOICES_PATH`) | quality/coverage for es-MX and fr-FR |
| `docker-compose.yml.piper` | Piper | same |

Polly was chosen because Gemini's `*-preview-tts` model carries a fixed low rate cap that account
tier does not lift, which made bulk pre-warming impractical. Polly has real production quotas.
That reasoning is about *throughput*, not about preferring proprietary software — if a self-hosted
engine later clears the quality bar, these are the starting points.

**Neither contains a credential.** Their only long tokens are model file paths. `TTS_ENGINE` is
pluggable (`kokoro` / `piper` / `gemini` / `polly`), so switching back is a config change plus a
rebuild, not a code change. Note the engine is part of the audio cache key, so a switch regenerates
every clip.

Recovered from `/opt/libretexts/tts/*.bak-*` on 2026-08-08 during a backup inventory that confirmed
they matched no commit in any repo.
