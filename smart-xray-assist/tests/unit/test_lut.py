"""UT-LUT-001 — LUT boundary values: correct clamping at min/max thickness
(verification-validation.md). Covers exact row boundaries, out-of-range
thickness (manual review), the pending-clinical-review modes, and guardrail
min/max clamping of out-of-range kVp/mAs."""

from __future__ import annotations

import pytest

from xray_assist.exposure.recommender import ExposureRecommender

DEV, SESS = "edge-001", "sess_test"


@pytest.fixture
def rec():
    root = __import__("pathlib").Path(__file__).resolve().parents[2]
    return ExposureRecommender.from_file(root / "configs" / "exposure_lut.yaml", DEV, SESS)


@pytest.mark.parametrize("thickness,kvp,mas", [
    (180, 70, 8.0),    # upper edge of row 1
    (181, 82, 15.0),   # lower edge of row 2
    (230, 82, 15.0),   # mid row 2 — the canonical adult chest_pa case
    (240, 82, 15.0),   # upper edge of row 2
    (241, 90, 22.0),   # lower edge of row 3
    (320, 90, 22.0),   # upper edge of row 3
])
def test_adult_chest_pa_boundaries(rec, thickness, kvp, mas):
    out = rec.recommend(thickness, "chest_pa", "adult").to_message()
    assert out["recommendation"]["kvp"] == kvp
    assert out["recommendation"]["mas"] == mas
    assert out["recommendation"]["operator_approval_required"] is True
    assert out["guardrails"]["manual_review_required"] is False


def test_out_of_range_thickness_is_manual_review(rec):
    # 500mm adult has no LUT row -> no numbers, manual review
    out = rec.recommend(500, "chest_pa", "adult").to_message()
    assert out["recommendation"]["kvp"] is None
    assert out["recommendation"]["mas"] is None
    assert out["guardrails"]["manual_review_required"] is True


def test_pending_clinical_review_modes_return_no_numbers(rec):
    # pediatric + bariatric rows are flagged "pending clinical review"
    ped = rec.recommend(100, "chest_pa", "pediatric").to_message()
    assert ped["recommendation"]["kvp"] is None
    assert ped["guardrails"]["manual_review_required"] is True
    bar = rec.recommend(400, "chest_pa", "bariatric").to_message()
    assert bar["recommendation"]["kvp"] is None
    assert bar["guardrails"]["manual_review_required"] is True


def test_guardrail_clamp_at_min_and_max():
    # a (hypothetical) LUT whose values exceed the guardrails must be clamped
    lut = {
        "metadata": {"version": "test"},
        "guardrails": {"kvp_min": 60, "kvp_max": 120, "mas_min": 1.0, "mas_max": 80.0},
        "chest_pa": {"adult": [
            {"thickness_mm_min": 0, "thickness_mm_max": 100, "kvp": 200, "mas": 200},
            {"thickness_mm_min": 101, "thickness_mm_max": 200, "kvp": 10, "mas": 0.1},
        ]},
    }
    rec = ExposureRecommender(lut, DEV, SESS)

    hi = rec.recommend(50, "chest_pa", "adult").to_message()
    assert hi["recommendation"]["kvp"] == 120   # clamped to kvp_max
    assert hi["recommendation"]["mas"] == 80.0   # clamped to mas_max
    assert hi["guardrails"]["within_min_max"] is False

    lo = rec.recommend(150, "chest_pa", "adult").to_message()
    assert lo["recommendation"]["kvp"] == 60     # clamped to kvp_min
    assert lo["recommendation"]["mas"] == 1.0    # clamped to mas_min
    assert lo["guardrails"]["within_min_max"] is False
