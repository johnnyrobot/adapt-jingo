# Spanish R scoring investigation — 2026-09-08

Status: deployed and verified on 2026-09-08. No model training performed.

The six practice widgets on [Verbos reflexivos con emociones](https://library.libretexts.dev/Books/Chevere_Introductory_Spanish_II/02%3A_Mente_sana_en_cuerpo_sano/2.07%3A_Verbos_reflexivos_con_emociones/)
penalized their own cached Hear-it exemplars at the R before `-se`.

| Word | R before -se, live | R, candidate | Overall, live | Overall, candidate |
| --- | ---: | ---: | ---: | ---: |
| calmarse | 4.9 | 100 | 81.7 | 93.5 |
| aburrirse | 2.3 | 100 | 83.7 | 100 |
| alegrarse | 2.7 | 100 | 86.2 | 98.3 |
| asustarse | 1.3 | 100 | 89.0 | 100 |
| cansarse | 0.6 | 100 | 87.0 | 99.4 |
| divertirse | 20.6 | 100 | 83.6 | 100 |

The earlier R before `t` in divertirse also improved from 31.9 to 100.
The onset tap in alegrarse remained 86.8. Other sound scores were unchanged.

## Cause and scope

The live records correctly map reference `ɾ` to vocabulary ID 15. At each
aligned R-before-s frame, the acoustic model instead strongly predicts `r`.
For example, calmarse frame 46 has log probabilities `r=-0.05`, `ɾ=-4.06`.
The strict calibration converts this mismatch into 4.9/100. This is neither a
missing vocabulary token nor a display rounding error.

Tap/trill variation in Spanish codas is documented in
[A stochastic approach to rhotic variation in Spanish codas](https://loquens.revistas.csic.es/index.php/loquens/article/view/20).
Engine 0.2.2 combines acoustic tap/trill evidence only for reference taps
followed by a recognized consonant within the same Spanish word. The record
must identify `lang: "es"` and the word span. Alignment, global equivalence
classes, calibration curve and uncertainty bands are unchanged. Intervocalic
contrasts (pero/perro), onset taps, other languages and word boundaries retain
their previous behavior. This is a bounded scoring correction, not a full
Spanish syllabifier or a model accuracy guarantee.

The separate `r` in aburrirse already has raw score 100, but the calibration
abstains because its native uncertainty band is 78, above the cutoff of 45.
The UI displays a dash and the engine excludes it from overall scoring.
Removing that abstention requires evidence that trill judgments are reliable;
it should not be disabled just to display a numeric score.

## Verification

Reproduce against the deployed service (uses public cached exemplar audio;
does not submit a grade):

```sh
curl -fsSL 'https://tts.libretexts.dev/say?text=calmarse&lang=es' -o /tmp/calmarse.mp3
curl -fsS 'https://jingo.libretexts.dev/practice-score' \
  -F 'audio=@/tmp/calmarse.mp3;type=audio/mpeg' \
  -F 'exercise_id=es-w-calmarse' -F 'language=es' -o /tmp/calmarse-score.json
python3 - <<'PY'
import json
p = json.load(open('/tmp/calmarse-score.json'))
r = p['phoneme_scores'][-3]
print(p['overall'], r)
assert r['phoneme'] == 'ɾ' and r['score'] >= 75 and not r.get('abstain')
PY
```

Before correction this fails with overall 81.7 and R 4.9. Candidate validation
ran the changed GOP module in an isolated Python process inside the existing
scorer container, using its deployed weights, records and the same cached
audio. It did not alter service files or restart the application. All six
R-before-se scores were asserted to be 100 and not abstained.

Regression tests drive the real CTC alignment, GOP scoring and payload
aggregation using deterministic frame probabilities. The tap/trill cases
failed with score zero before the fix. Wrong/missing rhotics still fail;
intervocalic and onset contrasts and non-Spanish behavior are preserved.

```sh
PYTHONPATH=engine/src:service python3 -m pytest engine/tests service/tests -q
```

Result: 55 passed. Existing service test JWT fixtures emit short-key warnings.

## Remaining validation and training

These results establish a reproducible mismatch on synthetic exemplars, not
accuracy on Cristina's team recordings, which were not available. Validate
with consenting speakers' recordings of the reported words and teacher
ratings, including acceptable dialect variants and incorrect/missing R
examples. Keep speakers separate between training and evaluation. Refit
context-sensitive calibration/uncertainty first; consider acoustic model
fine-tuning if held-out evidence still shows recognition errors. Ordinary use
does not automatically train this scorer. The existing uncertainty bands
remain provisional and have not been refit for this correction.

Deployment requires rebuilding the scorer image with the updated engine.
The reference records and ADAPT UI do not need to change for these six words.

## Deployment record

- Fix commit: `2c1342e` on `johnnylibretexts/adapt-jingo` main.
- Running engine and installed package: `0.2.2`.
- Release image: `jingo:release-2c1342e`, also tagged `jingo:local`.
- Running image ID: `sha256:274355b1e6496d19a6cf1efed930f53a4c779cda41ec029851c3a0c250bbb4e6`.
- Rollback: `jingo:rollback-20260908-pre-r-2c1342e`, image
  `sha256:ea7d53d41d58b853630be35b79ae8f83fc16244bbc87237f884277e282c43d35`.
- Source archive and release Dockerfile:
  `/opt/libretexts/jingo/releases/2c1342e/` on the deployment host.

The release installs the committed engine into the prior service image with
`pip install --no-deps --no-build-isolation`. Comparison of the two images
verified unchanged service code, dependency versions, calibration, vocabulary
and engine files other than `gop.py` and the engine version in `engine.py`.
The existing server checkout received those two files and the package version
update, preserving its other local overrides. The release archive is the
reproducible source for this deployed engine.

The initial rollout was automatically reverted after an order-sensitive
environment-list comparison failed. Before retrying, the planned environment
was verified against the running environment by variable name and value, and
the signing key was checked against ADAPT without displaying or persisting it.
The completed rollout verified environment values, mounts, ports and networks,
plus `minio` DNS resolution. It used the existing Compose configuration with
`up -d --no-build --no-deps jingo`.

Public `/health` returned `engine_available: true`. Replaying all six cached
exemplars through public `/practice-score` reproduced the candidate column
above exactly; all six R-before-se scores were asserted to be 100 and not
abstained. The separate rolled-R abstention in aburrirse remains in place.
The local engine/service test suite passed all 55 tests before deployment.

Rollback on the host:

```sh
docker tag jingo:rollback-20260908-pre-r-2c1342e jingo:local
cd /opt/libretexts/jingo
docker compose up -d --no-build --no-deps jingo
```

This restores the prior runtime image; the source checkout still contains the
fix. Do not rebuild from that checkout when intending to remain rolled back.
