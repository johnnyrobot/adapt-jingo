# Archived TTS engine configs — **not deployable**

Nothing here is live. The deployable template is `../docker-compose.example.yml`.

These are the two **open-source** engine configurations that ran on the box before the 2026-07-10
switch to Amazon Polly. They are preserved because Polly is a **proprietary dependency taken as a
deliberate, owner-approved exception** to LibreTexts' open-source-only rule — so the working
open-source configurations are the documented way back, and they existed nowhere but the VPS.

| file | engine | why it was replaced |
|---|---|---|
| `docker-compose.yml.kokoro` | Kokoro ONNX (`KOKORO_MODEL_PATH`, `KOKORO_VOICES_PATH`) | quality/coverage for es-MX and fr-FR |
| `docker-compose.yml.piper` | Piper — **but see the defect below** | same |

## ⚠️ `docker-compose.yml.piper` does not actually select Piper — do not run it as-is

**It omits `TTS_ENGINE`.** `app/config.py` reads
`TTS_ENGINE = os.environ.get("TTS_ENGINE", "kokoro")`, so this file selects **kokoro** — which then
fails, because the file also mounts no Kokoro model. It sets `PIPER_VOICE_DIR` and stops.

Found by Greptile on PR #3, and confirmed against `app/config.py` and `app/provider.py`.

**The file is left exactly as it was on the box, on purpose.** It is an archive: the point is a
byte-exact record of what sat on the VPS, verified by git blob OID at three separate steps.
"Correcting" it here would turn evidence into a guess, and would hide the fact that this
configuration was very likely never actually exercised.

To genuinely run Piper, add the missing line:

```yaml
    environment:
      TTS_ENGINE: piper                                   # <- absent from the archived file
      PIPER_VOICE_DIR: /opt/libretexts/tts/voices
```

Treat `docker-compose.yml.kokoro` as the trustworthy starting point — it does set
`TTS_ENGINE: kokoro`, along with its model paths and a `KOKORO_VOICES` map.

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
