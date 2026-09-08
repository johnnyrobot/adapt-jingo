"""Exercise the actual alignment/scoring path without loading model weights."""
import json

import numpy as np
import pytest

from jingo_engine.calibration import DEFAULT_VOCAB_PATH
from jingo_engine.engine import build_payload
from jingo_engine.gop import GopScorer, _variant_groups, log_softmax


def score(phones, heard, *, lang="es", words=None):
    vocab = json.loads(DEFAULT_VOCAB_PATH.read_text())
    scorer = GopScorer.__new__(GopScorer)
    scorer._vocab = vocab
    scorer._groups = _variant_groups(str(DEFAULT_VOCAB_PATH))
    # One confident acoustic frame per phone, separated by CTC blanks.
    logits = np.full((2 * len(phones) + 1, len(vocab)), -12.0)
    logits[::2, 0] = 0.0
    for i, phone in enumerate(heard):
        logits[2 * i + 1, vocab[phone]] = 0.0
    scorer._frame_logprobs = lambda _: (log_softmax(logits), 1.0)
    record = {"lang": lang, "phones": phones, "ids": [vocab[p] for p in phones],
              "words": words if words is not None else [{"start": 0, "len": len(phones)}]}
    return build_payload(scorer.score("unused.wav", record), record)


@pytest.mark.parametrize("consonant", ["s", "t"])
@pytest.mark.parametrize("heard_r", ["r", "ɾ"])
def test_spanish_preconsonantal_r_accepts_tap_and_trill(consonant, heard_r):
    result = score(["a", "ɾ", consonant, "e"], ["a", heard_r, consonant, "e"])
    assert result["phoneme_scores"][1]["score"] == 100
    assert result["overall"] == 100


@pytest.mark.parametrize("heard_r", ["l", "ɹ", "s", "<pad>"])
def test_wrong_or_missing_r_still_loses_credit(heard_r):
    result = score(["a", "ɾ", "s", "e"], ["a", heard_r, "s", "e"])
    assert result["phoneme_scores"][1]["score"] < 10
    assert result["overall"] < 80


@pytest.mark.parametrize("target,heard", [("ɾ", "r"), ("r", "ɾ")])
def test_intervocalic_tap_trill_contrast_preserved(target, heard):
    result = score(["e", target, "o"], ["e", heard, "o"])
    assert result["phoneme_scores"][1]["score"] < 10


@pytest.mark.parametrize("heard,expected", [("r", 100), ("ɾ", 0)])
def test_rolled_r_is_scored_and_counts_in_overall(heard, expected):
    result = score(["e", "r", "o"], ["e", heard, "o"])
    rr = result["phoneme_scores"][1]
    assert rr["score"] == expected
    assert rr["abstain"] is False
    assert rr["uncertainty"]["band"] == 78
    assert result["overall"] == round((200 + expected) / 3, 1)
    assert result["word_scores"][0]["score"] == result["overall"]
    assert result["provisional"] is True


@pytest.mark.parametrize("lang", ["fr", "en", None])
def test_rule_requires_spanish_record(lang):
    result = score(["a", "ɾ", "s", "e"], ["a", "r", "s", "e"], lang=lang)
    assert result["phoneme_scores"][1]["score"] < 10


def test_onset_tap_is_not_merged():
    result = score(["ɡ", "ɾ", "a"], ["ɡ", "r", "a"])
    assert result["phoneme_scores"][1]["score"] < 10


@pytest.mark.parametrize("words", [[], [{"start": 0, "len": 2}, {"start": 2, "len": 2}]])
def test_does_not_infer_coda_without_same_word_span(words):
    result = score(["a", "ɾ", "s", "e"], ["a", "r", "s", "e"], words=words)
    assert result["phoneme_scores"][1]["score"] < 10
