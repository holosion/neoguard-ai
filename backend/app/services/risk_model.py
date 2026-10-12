"""Non-executable JSON logistic model; no pickle loading or ML runtime required."""
import hashlib
import json
from math import exp, isfinite
from pathlib import Path

from app.services.risk_features import FEATURE_NAMES, FEATURE_VERSION, trend_flags


def load_model(path):
    raw = Path(path).read_bytes()
    model = json.loads(raw)
    if model.get("schema_version") != 1 or model.get("feature_version") != FEATURE_VERSION or model.get("feature_names") != FEATURE_NAMES:
        raise ValueError("Unsupported model feature contract")
    if model.get("validation_scope") != "synthetic_only" or model.get("target") != "simulated_event_current_or_within_120s":
        raise ValueError("Unsupported prototype model target or scope")
    for name in ("means", "scales", "coefficients"):
        values = model[name]
        if len(values) != len(FEATURE_NAMES) or not all(isfinite(float(v)) for v in values):
            raise ValueError("Invalid model vector")
    if any(v <= 0 for v in model["scales"]) or not isfinite(model["intercept"]) or not 0 < model["decision_threshold"] < 1:
        raise ValueError("Invalid model parameters")
    model["sha256"] = hashlib.sha256(raw).hexdigest()
    return model


def predict(model, features):
    contributions = [{"feature": name, "value": features[name], "log_odds_contribution": (features[name] - mu) / scale * coefficient}
                     for name, mu, scale, coefficient in zip(FEATURE_NAMES, model["means"], model["scales"], model["coefficients"])]
    z = model["intercept"] + sum(c["log_odds_contribution"] for c in contributions)
    score = 1 / (1 + exp(-z)) if z >= 0 else exp(z) / (1 + exp(z))
    return {"score": score, "risk_category": "high" if score >= model["decision_threshold"] else "low",
            "warning": score >= model["decision_threshold"], "target": model["target"],
            "model_version": model["version"], "validation_scope": model["validation_scope"],
            "explanation": {"intercept": model["intercept"], "contributions": sorted(contributions, key=lambda c: abs(c["log_odds_contribution"]), reverse=True),
                            "contribution_units": "log_odds_relative_to_training_mean", "trend_flags": trend_flags(features)}}
