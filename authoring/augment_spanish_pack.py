"""Augment spanish-1.json with a dozen more pronunciation drills (words + short
phrases) and reference them in the Unit 1 exam ("Examen Unidad 1"). Phonetics
records are G2P-generated via jingo_engine (same path build_pack.py uses).

Run with any Python 3.10+ venv that has jingo_engine's G2P extras available:
  python augment_spanish_pack.py <in_pack.json> <out_pack.json>

jingo_engine is resolved from this repo's vendored engine/src. Set
JINGO_ENGINE_SRC to use a different checkout.
"""
import json
import os
import sys
from pathlib import Path

ENGINE_SRC = os.environ.get(
    "JINGO_ENGINE_SRC",
    str(Path(__file__).resolve().parent.parent / "engine" / "src"),
)
sys.path.insert(0, ENGINE_SRC)
from jingo_engine import DEFAULT_VOCAB_PATH
from jingo_engine.contract import get_g2p, phonetics_for

# 12 new drills — mix of single words and short phrases. All graded 'score' so
# the exam demonstrates real pronunciation scoring end-to-end.
NEW_DRILLS = [
    ("gato", "Escucha y repite: «gato» — cat"),
    ("casa", "Escucha y repite: «casa» — house"),
    ("libro", "Escucha y repite: «libro» — book"),
    ("mesa", "Escucha y repite: «mesa» — table"),
    ("agua", "Escucha y repite: «agua» — water"),
    ("sol", "Escucha y repite: «sol» — sun"),
    ("buenos días", "Escucha y repite: «buenos días» — good morning"),
    ("muchas gracias", "Escucha y repite: «muchas gracias» — thank you very much"),
    ("me llamo Ana", "Escucha y repite: «me llamo Ana» — my name is Ana"),
    ("¿cómo estás?", "Escucha y repite: «¿cómo estás?» — how are you?"),
    ("hasta luego", "Escucha y repite: «hasta luego» — see you later"),
    ("mucho gusto", "Escucha y repite: «mucho gusto» — nice to meet you"),
]
LESSON_ID = "es-u1-l3"
EXAM_POINTS = 5


def build_record(text, g2p):
    rec = phonetics_for(text, "es", g2p, str(DEFAULT_VOCAB_PATH))
    if rec.get("coverage", 0) < 1.0:
        raise SystemExit(f"coverage < 1.0 for {text!r}: {rec.get('unknown')}")
    return {
        "lang": rec.get("lang", "es"),
        "phones": rec["phones"],
        "ids": rec["ids"],
        "words": rec.get("words", []),
        "coverage": rec.get("coverage", 1.0),
        "unknown": rec.get("unknown", []),
        "espeak_voice": rec.get("espeak_voice"),
    }


def main(in_path, out_path):
    pack = json.loads(open(in_path, encoding="utf-8").read())
    g2p = get_g2p()
    unit = pack["units"][0]

    # Skip if the lesson already exists (idempotent re-runs).
    if any(l["id"] == LESSON_ID for l in unit["lessons"]):
        print(f"lesson {LESSON_ID} already present — nothing to do")
        return

    drills, exam_refs = [], []
    for i, (text, prompt) in enumerate(NEW_DRILLS, start=1):
        ex_id = f"{LESSON_ID}-e{i}"
        drills.append({
            "id": ex_id, "type": "pronunciation", "prompt": prompt,
            "target_text": text, "grading": "score",
            "phonetics_record": build_record(text, g2p),
        })
        exam_refs.append({"exercise_id": ex_id, "points": EXAM_POINTS})
        print(f"  {ex_id:14s} {text!r:24s} -> {''.join(drills[-1]['phonetics_record']['phones'])}")

    unit["lessons"].append({
        "id": LESSON_ID, "title": "Práctica: palabras y frases",
        "order": max(l["order"] for l in unit["lessons"]) + 1, "drills": drills,
    })
    unit["exam"]["questions"].extend(exam_refs)

    open(out_path, "w", encoding="utf-8").write(json.dumps(pack, ensure_ascii=False, indent=2))
    print(f"wrote {out_path}: +{len(drills)} drills, exam now has {len(unit['exam']['questions'])} questions")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
