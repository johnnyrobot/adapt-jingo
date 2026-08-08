# `pron` container, retired 2026-07-07 — **not deployable**

Nothing here is live. The current scorer is `../../service/`.

On 2026-07-07 the pronunciation scorer container was renamed `pron` → **`jingo`**, and the old tree
was set aside on the box as `/opt/libretexts/pron.retired-20260707/`. These three files are the
`.bak-*` copies that were sitting inside it. They matched no commit in any repo — verified
2026-08-08 by computing each git blob OID on the box and testing it for reachability across all 18
local checkouts.

| file | current equivalent |
|---|---|
| `docker-compose.yml` | `../../service/docker-compose.example.yml` |
| `src/app/main.py` | `../../service/app/main.py` |
| `src/packs/spanish-1.json` | `../../service/packs/spanish-1.json` |

Note the path shift: `src/app/…` → `service/app/…`. Directory layout is preserved here as it was on
the box, so these do not line up with the current tree by path.

## Why this rename is worth remembering

`docker inspect pron` fails, which reads alarmingly like a missing container. **There is no `pron`
container — it is `jingo`.** The container must also stay attached to the `adapt_adapt` docker
network: off it, the scorer cannot resolve `minio` to fetch student audio, logs `audio_unreachable`,
and silently falls back to completion credit. It looks fine and never actually scores.

**None of these contains a credential.** Their only long tokens are directory paths and a volume
mount.
