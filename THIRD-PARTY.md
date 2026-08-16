# Third-party components

No upstream source is vendored in this repository, and **no model weights are
committed** — every artifact below is pulled at build or deploy time.

**Running these services raises no licensing question.** The obligations attach
when you redistribute a **built image**, because the image combines the
MIT-licensed code here with the works below — including two GPL binaries.

This repository ships four separable things, and they do not carry the same
obligations. Check the one you are actually distributing.

---

## 1. The scorer image (`service/Dockerfile`)

| Component | Pinned | License |
|---|---|---|
| [python:3.11-slim](https://hub.docker.com/_/python) (Debian) | `3.11-slim` | PSF-2.0 + Debian base, mixed |
| **FFmpeg** (`ffmpeg` apt package) | Debian stable | **GPL-2.0-or-later, as Debian builds it** — see below |
| `jingo-engine` (this repo, `engine/`) | local | MIT |
| CTranslate2 | `>=4.0` | MIT |
| NumPy | `>=1.24` | BSD-3-Clause |
| FastAPI | `0.110.0` | MIT |
| Uvicorn (`[standard]`) | `0.29.0` | BSD-3-Clause |
| Pydantic | `2.6.0` | MIT |
| PyJWT | `2.8.0` | MIT |
| HTTPX | `0.27.0` | BSD-3-Clause |
| python-multipart | `0.0.9` | Apache-2.0 |

**espeak is deliberately absent from this image.** The grapheme-to-phoneme
toolchain (`phonemizer`, `espeakng-loader`) is GPL and is listed in
`service/requirements-build.txt` **commented out**, with a note saying to install
it on a workstation instead. That is not an oversight — it is why authoring new
pronunciation words is a workstation task rather than a server one.

## 2. The TTS image (`tts/Dockerfile`)

| Component | Pinned | License |
|---|---|---|
| [python:3.11-slim](https://hub.docker.com/_/python) (Debian) | `3.11-slim` | PSF-2.0 + Debian base, mixed |
| **FFmpeg** | Debian stable | **GPL-2.0-or-later, as Debian builds it** |
| **eSpeak NG** (`espeak-ng` apt package) | Debian stable | **GPL-3.0-or-later** |
| FastAPI | `0.111.0` | MIT |
| Uvicorn (`[standard]`) | `0.30.1` | BSD-3-Clause |
| kokoro-onnx | `>=0.4.9` | MIT |
| onnxruntime (via kokoro-onnx) | resolved | MIT |
| NumPy | `>=1.26` | BSD-3-Clause |
| boto3 | `>=1.34` | Apache-2.0 |

**Unlike the scorer, this image does contain espeak-ng**, because Kokoro needs
grapheme-to-phoneme conversion at synthesis time for Spanish, French and other
non-English voices. If you redistribute the TTS image, you are redistributing
GPL-3.0 software.

Voice models are **mounted at runtime, not baked into the image**
(`KOKORO_MODEL_PATH`, `KOKORO_VOICES_PATH`). Kokoro-82M is **Apache-2.0**.

### About FFmpeg and eSpeak NG

Both are standalone executables invoked as subprocesses. Nothing here links
against them, so this is aggregation rather than a derived work — but a
container image you hand to someone else still *distributes* those binaries, and
the GPL's source-offer obligation travels with them. Debian satisfies this
through its own source archive; if you rebuild or repackage, make sure you can
still point at corresponding source.

FFmpeg's own code is LGPL-2.1-or-later at its core. Debian's packaged build
enables GPL components, so treat the binary in these images as GPL-2.0-or-later
unless you build FFmpeg yourself with `--disable-gpl`.

## 3. Optional TTS engines

`TTS_ENGINE` selects the synthesis backend. Only Kokoro is installed by default.

| Engine | Status | License |
|---|---|---|
| **kokoro** (default) | installed | Apache-2.0 model, MIT runtime |
| **piper** | commented out in `tts/requirements.txt` | MIT |
| **polly** | `boto3` installed, credentials not | **Proprietary — Amazon Polly**, a paid AWS service |

Amazon Polly is a deliberate exception to the otherwise open-source stack: it is
a commercial cloud API, it requires your own AWS IAM credentials, and usage is
billed to you. Nothing in this repository contains or implies a credential.
Selecting `TTS_ENGINE=polly` means accepting the AWS Service Terms.

## 4. The acoustic model

Scoring uses a CTranslate2 int8 export of
[`facebook/wav2vec2-xlsr-53-espeak-cv-ft`](https://huggingface.co/facebook/wav2vec2-xlsr-53-espeak-cv-ft),
license **Apache-2.0**.

**The weights are not in this repository.** `model/` is empty on checkout and
the deployer fetches them, with filenames, sizes and checksums pinned in
`engine/src/jingo_engine/assets/model-manifest.json`. Distributing a built image
therefore does not distribute the model unless you deliberately bake it in.

## 5. The ADAPT patch set (`adapt-integration/`)

Patch files and prose only — no vendored code. They are derived works of
**ADAPT** (`github.com/kreut/libretext`), which is **MIT**. Applying them adds
two npm packages to your ADAPT build: **lamejs** (LGPL-3.0) for MP3 encoding in
the browser, and **vue-audio-recorder** (MIT).

`lamejs` is LGPL-3.0 and ships to the browser inside your compiled bundle. If
you redistribute that bundle, the LGPL's relinking obligation applies to it.

---

## Why this repository is MIT

Everything under `service/`, `tts/`, `engine/`, `authoring/` and
`adapt-integration/` is original work. Nothing here contains or modifies GPL
source; the GPL components are separate binaries installed from Debian, and the
build-time GPL toolchain is deliberately kept off the servers entirely.

`engine/` carries its own `LICENSE`, `NOTICE.md` and `THIRD_PARTY_NOTICES.md`
because it is packaged as a standalone Python distribution and must be
self-describing when installed on its own.

## Refreshing this file

Version ranges above are the declared constraints, not resolved versions. Before
any public release, regenerate from what actually resolved:

```bash
docker run --rm jingo:local pip list --format=freeze
docker run --rm jingo-tts:local pip list --format=freeze
docker run --rm jingo:local sh -c 'dpkg-query -W -f="\${Package} \${Version}\n"'
```

Then confirm each entry's license, rather than assuming the constraint above
still describes what shipped.
