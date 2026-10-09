from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import pytest

from app.services.risk_features import FEATURE_NAMES, extract_features
from app.services.risk_model import load_model, predict
from ai.audit_archives import audit

ROOT = Path(__file__).resolve().parents[2]


def readings():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [{"measured_at": start + timedelta(seconds=i * 5), "temperature_c": 37 - i * 0.01,
             "spo2_percent": 98, "heart_rate_bpm": 140, "quality": "ok"} for i in range(25)]


def test_slopes_use_elapsed_time_and_future_readings_are_excluded():
    rows = readings()
    before = extract_features(rows)
    assert before["temperature_c_slope_per_minute"] == pytest.approx(-0.12)
    future = {**rows[-1], "measured_at": rows[-1]["measured_at"] + timedelta(seconds=5), "temperature_c": 30}
    assert extract_features(rows + [future], end=rows[-1]["measured_at"]) == before


@pytest.mark.parametrize("fault", ["poor_latest", "missing_latest", "gap", "duplicate_time", "invalid_range", "too_short"])
def test_abstain_on_unreliable_windows(fault):
    rows = readings()
    if fault == "poor_latest":
        rows[-1]["quality"] = "motion_artifact"
    elif fault == "missing_latest":
        rows[-1]["spo2_percent"] = None
    elif fault == "gap":
        rows = rows[:5] + rows[12:]
    elif fault == "duplicate_time":
        rows.append(dict(rows[-1]))
    elif fault == "invalid_range":
        rows[-1]["spo2_percent"] = 101
    else:
        rows = rows[:5]
    assert extract_features(rows) is None


def test_saved_model_matches_logistic_equation_and_explains_score():
    import math
    model = load_model(ROOT / "ai/artifacts/risk_model.json")
    features = extract_features(readings())
    result = predict(model, features)
    logit = model["intercept"] + sum(c["log_odds_contribution"] for c in result["explanation"]["contributions"])
    assert result["score"] == pytest.approx(1 / (1 + math.exp(-logit)))
    assert result["validation_scope"] == "synthetic_only"
    assert len(result["explanation"]["contributions"]) == len(FEATURE_NAMES)


def test_model_rejects_changed_feature_contract(tmp_path):
    model = json.loads((ROOT / "ai/artifacts/risk_model.json").read_text())
    model["feature_names"].reverse()
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(model))
    with pytest.raises(ValueError):
        load_model(path)


def test_subject_splits_never_overlap():
    manifest = json.loads((ROOT / "ai/reports/split_manifest.json").read_text())
    tr, val, test = (set(manifest[n]) for n in ("train", "validation", "test"))
    assert tr and val and test
    assert not (tr & val or tr & test or val & test)


def test_archive_staging_excludes_identifiers_and_preserves_review_flags(tmp_path):
    audit(ROOT, tmp_path)
    newborn = [json.loads(s) for s in (tmp_path / "newborn_staging.jsonl").read_text().splitlines()]
    hypo = [json.loads(s) for s in (tmp_path / "hypothermia_staging.jsonl").read_text().splitlines()]
    assert len(newborn) == 3000 and len(hypo) == 200
    assert all("name" not in r["payload"] for r in newborn)
    assert all("code" not in r["payload"] for r in hypo)
    assert sum("invalid_oxygen_saturation" in r["quality_flags"] for r in newborn) == 7
    assert all(r["validation_status"] == "review" for r in newborn + hypo)
