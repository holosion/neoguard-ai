"""Shared causal feature extraction, used identically in training and serving.

Only readings at or before the scoring time may enter a window. No future
interpolation, carried-forward stale values, or patient identifiers are features.
"""
from datetime import datetime, timedelta
from math import isfinite, sqrt
from statistics import mean

FEATURE_VERSION = "v1"
WINDOW_SECONDS = 120
MIN_WINDOW_SECONDS = 60
MAX_GAP_SECONDS = 15
VITALS = ("temperature_c", "spo2_percent", "heart_rate_bpm")
FEATURE_NAMES = [f"{v}_{s}" for v in VITALS for s in ("last", "mean", "slope_per_minute", "std")]


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value


def extract_features(readings, end=None):
    if not readings:
        return None
    end = timestamp(end) if end is not None else max(timestamp(r["measured_at"]) for r in readings)
    rows = sorted((r for r in readings if end - timedelta(seconds=WINDOW_SECONDS) <= timestamp(r["measured_at"]) <= end), key=lambda r: timestamp(r["measured_at"]))
    if not rows or timestamp(rows[-1]["measured_at"]) != end or rows[-1].get("quality", "ok") != "ok":
        return None
    # Deduplicate observation times; reject ambiguous simultaneous observations.
    times = [timestamp(r["measured_at"]) for r in rows]
    if len(set(times)) != len(times):
        return None
    result = {}
    for vital in VITALS:
        valid = [r for r in rows if r.get("quality", "ok") == "ok" and r.get(vital) is not None and isfinite(float(r[vital]))]
        if len(valid) < 12 or valid[-1] is not rows[-1]:
            return None
        t = [(timestamp(r["measured_at"]) - end).total_seconds() / 60 for r in valid]
        if (t[-1] - t[0]) * 60 < MIN_WINDOW_SECONDS or any((b - a) * 60 > MAX_GAP_SECONDS + 1e-8 for a, b in zip(t, t[1:])):
            return None
        vals = [float(r[vital]) for r in valid]
        limits = {"temperature_c": (30, 42), "spo2_percent": (50, 100), "heart_rate_bpm": (40, 220)}
        if any(not limits[vital][0] <= value <= limits[vital][1] for value in vals):
            return None
        tx, vy = mean(t), mean(vals)
        variance_t = sum((x - tx) ** 2 for x in t)
        result.update({f"{vital}_last": vals[-1], f"{vital}_mean": vy,
                       f"{vital}_slope_per_minute": sum((x - tx) * (y - vy) for x, y in zip(t, vals)) / variance_t,
                       f"{vital}_std": sqrt(mean([(y - vy) ** 2 for y in vals]))})
    return result


def trend_flags(features):
    """Experimental directional flags, not a diagnosis or calibrated forecast."""
    flags = []
    for vital, bound in (("temperature_c", -0.08), ("spo2_percent", -1.0)):
        slope = features[f"{vital}_slope_per_minute"]
        if slope < bound:
            flags.append({"parameter": vital, "direction": "declining", "slope_per_minute": slope})
    return flags
