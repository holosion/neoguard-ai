"""Train a synthetic warning prototype and an isolated source-label benchmark.

Run from the repository root: python -m ai.train
"""
import argparse
from collections import Counter
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, confusion_matrix, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.risk_features import FEATURE_NAMES, FEATURE_VERSION, extract_features
from app.services.risk_model import predict
from ai.audit_archives import audit

SEED = 20261009
HORIZON = 120
STEP = 5
SCENARIOS = ("normal", "cooling", "desaturation", "combined", "recovery", "artifact", "near_threshold", "dropout")


def generate_sessions(count, seed):
    rng = np.random.default_rng(seed)
    sessions = []
    for number in range(count):
        scenario = SCENARIOS[number % len(SCENARIOS)]
        start = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=number)
        base_temp, base_spo2, base_hr = rng.uniform(36.7, 37.3), rng.uniform(95.5, 99), rng.uniform(115, 150)
        onset = int(rng.uniform(200, 500))
        cooling = rng.uniform(0.07, 0.24) / 60
        oxygen_decline = rng.uniform(1.1, 3.2) / 60
        recovery_start = onset + int(rng.uniform(160, 300))
        cooling_extent = rng.uniform(1.2, 1.8)
        rows, events = [], []
        for seconds in range(0, 1201, STEP):
            dt = max(0, seconds - onset)
            temp, spo2, hr = base_temp, base_spo2, base_hr
            if scenario in ("cooling", "combined", "recovery"):
                temp -= min(dt * cooling, cooling_extent)
            if scenario in ("desaturation", "combined", "recovery"):
                spo2 -= min(dt * oxygen_decline, 10)
                hr += min(dt / 60 * rng.uniform(0.5, 1.5), 12)
            if scenario == "recovery" and seconds > recovery_start:
                temp = min(base_temp, temp + (seconds - recovery_start) * cooling * 1.7)
                spo2 = min(base_spo2, spo2 + (seconds - recovery_start) * oxygen_decline * 1.7)
            if scenario == "near_threshold":
                temp = 36.58 + 0.035 * np.sin(seconds / rng.uniform(30, 90))
                spo2 = 91.2 + 0.4 * np.sin(seconds / 60)
            # Ground truth is latent physiology, not a bad sensor observation.
            events.append(bool(temp < 36.5 or spo2 < 90))
            quality = "ok"
            observed_temp, observed_spo2 = temp + rng.normal(0, 0.025), np.clip(spo2 + rng.normal(0, 0.25), 50, 100)
            if scenario == "artifact" and onset <= seconds < onset + 30:
                quality = "motion_artifact"
                observed_spo2 -= 15
            if scenario == "dropout" and onset <= seconds < onset + 60:
                quality = "sensor_error"
            rows.append({"measured_at": start + timedelta(seconds=seconds), "temperature_c": round(float(observed_temp), 2),
                         "spo2_percent": int(round(observed_spo2)) if quality != "sensor_error" else None,
                         "heart_rate_bpm": int(round(hr + rng.normal(0, 1.0))), "quality": quality})
        sessions.append({"session_id": f"S{number:04d}", "scenario": scenario, "rows": rows, "events": events})
    return sessions


def split_groups(groups, seed):
    indices = np.arange(len(groups))
    train_val, test = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed).split(indices, groups=groups))
    tr, val = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed + 1).split(train_val, groups=np.array(groups)[train_val]))
    return train_val[tr], train_val[val], test


def metrics(y, p, threshold):
    pred = np.asarray(p) >= threshold
    return {"rows": len(y), "positive_rows": int(sum(y)), "precision": float(precision_score(y, pred, zero_division=0)),
            "recall": float(recall_score(y, pred, zero_division=0)), "average_precision": float(average_precision_score(y, p)),
            "roc_auc": float(roc_auc_score(y, p)), "brier_score": float(brier_score_loss(y, p)),
            "confusion_matrix_tn_fp_fn_tp": confusion_matrix(y, pred, labels=[0, 1]).ravel().tolist()}


def event_metrics(sessions, records, probs, threshold):
    grouped = {}
    for record, p in zip(records, probs):
        grouped.setdefault(record[0], {})[record[1]] = p >= threshold
    detected = total = false_episodes = warning_episodes = matched_episodes = 0
    lead_times = []
    hours = sum(len(warnings) for warnings in grouped.values()) * STEP / 3600
    for sid, warnings in grouped.items():
        session = sessions[sid]
        events = session["events"]
        onsets = [i for i, event in enumerate(events) if event and (i == 0 or not events[i - 1]) and min(warnings) <= i <= max(warnings)]
        for onset in onsets:
            total += 1
            candidates = [i for i, warn in warnings.items() if warn and max(0, onset - HORIZON // STEP) <= i <= onset]
            if candidates:
                detected += 1
                lead_times.append((onset - min(candidates)) * STEP)
        previous = False
        for i in range(len(events)):
            warn = warnings.get(i, False)
            if warn and not previous:
                warning_episodes += 1
                if any(events[i:min(len(events), i + HORIZON // STEP + 1)]):
                    matched_episodes += 1
                else:
                    false_episodes += 1
            previous = warn
    return {"events": total, "events_detected_by_onset": detected, "event_sensitivity": detected / total if total else None,
            "warning_episodes": warning_episodes, "warning_episode_precision": matched_episodes / warning_episodes if warning_episodes else None,
            "false_warning_episodes": false_episodes, "monitoring_hours": hours,
            "false_warning_episodes_per_hour": false_episodes / hours,
            "median_lead_seconds_among_detected": float(np.median(lead_times)) if lead_times else None}


def archive_benchmark():
    rows = [json.loads(line)["payload"] for line in (ROOT / "ai/data/newborn_staging.jsonl").read_text(encoding="utf-8").splitlines()
            if "invalid_oxygen_saturation" not in json.loads(line)["quality_flags"]]
    names = ["temperature_c", "heart_rate_bpm", "oxygen_saturation"]
    x = np.array([[float(r[k]) for k in names] for r in rows])
    y = np.array([int(r["risk_level"] == "At Risk") for r in rows])
    groups = [r["baby_id"] for r in rows]
    train, val, test = split_groups(groups, SEED)
    scale = StandardScaler().fit(x[train])
    clf = LogisticRegression(max_iter=1000).fit(scale.transform(x[train]), y[train])
    report = {"purpose": "Exploratory reproduction of undocumented source label; never deployed", "validation_scope": "unverified_source_labels",
              "features": names, "excluded_invalid_spo2_rows": 7,
              "split_subjects": {name: len(set(np.array(groups)[idx])) for name, idx in (("train", train), ("validation", val), ("test", test))},
              "test": metrics(y[test], clf.predict_proba(scale.transform(x[test]))[:, 1], 0.5),
              "majority_accuracy": float(1 - y[test].mean()), "limitation": "Labels are not verified clinical events; vitals alone may not explain their derivation."}
    (ROOT / "ai/reports/archive_baseline.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def train(count=480, seed=SEED):
    audit()
    archive_benchmark()
    sessions = generate_sessions(count, seed)
    data, labels, groups, records, baseline = [], [], [], [], []
    for sid, session in enumerate(sessions):
        for i, row in enumerate(session["rows"]):
            # Exclude the censored tail: a full future horizon is required for labels.
            if i + HORIZON // STEP >= len(session["rows"]):
                continue
            features = extract_features(session["rows"][max(0, i - 24):i + 1])
            if features is None:
                continue
            data.append([features[n] for n in FEATURE_NAMES])
            labels.append(int(any(session["events"][i:i + HORIZON // STEP + 1])))
            groups.append(session["session_id"])
            records.append((sid, i))
            baseline.append(int(row["quality"] == "ok" and (row["temperature_c"] < 36.5 or row["spo2_percent"] < 90)))
    x, y, records = np.array(data), np.array(labels), np.array(records)
    tr, val, test = split_groups(groups, seed)
    scaler = StandardScaler().fit(x[tr])
    model = LogisticRegression(max_iter=2000, C=0.3, random_state=seed).fit(scaler.transform(x[tr]), y[tr])
    validation_probs = model.predict_proba(scaler.transform(x[val]))[:, 1]
    # Select operating point only on validation sessions, penalizing false episodes.
    candidates = []
    for threshold in np.linspace(0.1, 0.9, 33):
        em = event_metrics(sessions, records[val], validation_probs, float(threshold))
        utility = (em["event_sensitivity"] or 0) - 0.12 * em["false_warning_episodes_per_hour"]
        candidates.append((utility, float(threshold)))
    threshold = max(candidates)[1]
    p = model.predict_proba(scaler.transform(x[test]))[:, 1]
    manifest = {name: sorted(set(np.array(groups)[idx])) for name, idx in (("train", tr), ("validation", val), ("test", test))}
    report = {"seed": seed, "sessions": count, "scenario_counts": dict(Counter(s["scenario"] for s in sessions)),
              "sampling_seconds": STEP, "feature_window_seconds": 120, "label_horizon_seconds": HORIZON,
              "label_definition": "Latent simulated temperature <36.5C or SpO2 <90%, now or within 120 seconds; not diagnosis",
              "validation_scope": "synthetic_only", "test_used_for_threshold_selection": False,
              "decision_threshold": threshold, "split_subject_counts": {k: len(v) for k, v in manifest.items()},
              "test": metrics(y[test], p, threshold), "test_event_metrics": event_metrics(sessions, records[test], p, threshold),
              "threshold_baseline": metrics(y[test], np.array(baseline)[test], 0.5),
              "threshold_baseline_event_metrics": event_metrics(sessions, records[test], np.array(baseline)[test], 0.5),
              "limitations": ["No clinical validation or clinical probability calibration", "Train and test share a synthetic generator",
                             "Threshold-derived simulated future events", "Daily archive data excluded from time-series training",
                             "False-alarm and lead-time results describe the simulated scenarios only"],
              "runtime": {"python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__}}
    artifact = {"schema_version": 1, "feature_version": FEATURE_VERSION, "feature_names": FEATURE_NAMES,
                "version": f"synthetic-v1-{seed}", "model_key": "neoguard-warning", "target": "simulated_event_current_or_within_120s",
                "validation_scope": "synthetic_only", "means": scaler.mean_.tolist(), "scales": scaler.scale_.tolist(),
                "coefficients": model.coef_[0].tolist(), "intercept": float(model.intercept_[0]),
                "decision_threshold": threshold, "sampling_seconds": STEP, "horizon_seconds": HORIZON,
                "event_thresholds": {"temp_low": 36.5, "spo2_low": 90}, "metrics": report}
    # Verify exported inference matches sklearn before saving the artifact.
    for index in test[:50]:
        got = predict(artifact, dict(zip(FEATURE_NAMES, x[index]))) ["score"]
        expected = model.predict_proba(scaler.transform(x[index:index + 1]))[0, 1]
        assert abs(got - expected) < 1e-12
    out = ROOT / "ai/artifacts"
    out.mkdir(parents=True, exist_ok=True)
    artifact_bytes = (json.dumps(artifact, indent=2, allow_nan=False) + "\n").encode()
    (out / "risk_model.json").write_bytes(artifact_bytes)
    report["artifact_sha256"] = hashlib.sha256(artifact_bytes).hexdigest()
    for name, payload in (("training_report.json", report), ("split_manifest.json", manifest)):
        (ROOT / "ai/reports" / name).write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    # Persist simulated records for reproducibility, never live patient records.
    with (ROOT / "ai/data/synthetic_sessions.jsonl").open("w", encoding="utf-8") as f:
        for session in sessions:
            for row, event in zip(session["rows"], session["events"]):
                f.write(json.dumps({**row, "measured_at": row["measured_at"].isoformat(), "session_id": session["session_id"], "scenario": session["scenario"], "latent_event": event}) + "\n")
    print(json.dumps({"artifact": str(out / "risk_model.json"), "test": report["test"], "events": report["test_event_metrics"],
                      "baseline_events": report["threshold_baseline_event_metrics"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=int, default=480)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    if args.sessions < 160:
        parser.error("Use at least 160 independent sessions")
    train(args.sessions, args.seed)
