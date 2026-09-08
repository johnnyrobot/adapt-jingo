from dataclasses import replace

from jingo_engine.calibration import load_calibration


def test_rolled_r_override_preserves_no_frames_and_quarantine():
    cal = load_calibration()
    for frames, reliable, reason in [(0, True, "too_few_frames"),
                                     (1, False, "quarantined_phone")]:
        result = cal.phone_uncertainty("r", 100, frames, reliable=reliable)
        assert result["abstain"] is True
        assert result["reason"] == reason


def test_other_wide_band_phones_still_abstain():
    cal = load_calibration()
    for phone in ["β", "ɣ", "ʁ"]:
        result = cal.phone_uncertainty(phone, 100, 1, reliable=True)
        assert result["abstain"] is True
        assert result["reason"] == "wide_native_band"


def test_wide_band_override_is_reversible_without_altering_evidence():
    cal = load_calibration()
    disabled = replace(cal, uncertainty=replace(cal.uncertainty, wide_band_score_phones=frozenset()))
    result = disabled.phone_uncertainty("r", 100, 1, reliable=True)
    assert result["abstain"] is True
    assert result["band"] == 78
