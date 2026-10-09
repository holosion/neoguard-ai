"""Read ZIPs without extracting arbitrary members; write de-identified research files."""
import csv
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def audit(root=ROOT, output=None):
    output = Path(output or root / "ai" / "data")
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    for archive, member in (("archive.zip", "newborn_health_monitoring_with_risk.csv"), ("archive_1.zip", "Hypothermia.csv")):
        with ZipFile(root / archive) as z:
            raw = z.read(member)
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        cleaned = []
        for i, row in enumerate(rows, 2):
            row = {k: v.strip() for k, v in row.items() if k not in ("name", "code")}
            flags = []
            if archive == "archive.zip":
                if not 0 <= float(row["oxygen_saturation"]) <= 100:
                    flags.append("invalid_oxygen_saturation")
                flags.append("source_risk_label_unverified")
            else:
                flags.append("codebook_units_and_timing_unverified")
                if row.get("t.3") == "0":
                    flags.append("zero_temperature_unverified")
            cleaned.append({"source_row_number": i, "payload": row, "quality_flags": flags, "validation_status": "review"})
        filename = "newborn_staging.jsonl" if archive == "archive.zip" else "hypothermia_staging.jsonl"
        (output / filename).write_text("\n".join(json.dumps(row) for row in cleaned) + "\n", encoding="utf-8")
        profile = {k: {"missing": sum(not r[k].strip() for r in rows), "unique": len({r[k].strip() for r in rows})}
                   for k in rows[0] if k not in ("name", "code")}
        reports.append({"archive": archive, "member": member, "member_sha256": hashlib.sha256(raw).hexdigest(),
                        "archive_sha256": hashlib.sha256((root / archive).read_bytes()).hexdigest(), "rows": len(rows),
                        "columns": profile, "staging_file": filename, "status": "review",
                        "source_url": None, "license": None,
                        "excluded_fields": [k for k in ("name", "code") if k in rows[0]],
                        "approved_for_clinical_training": False})
    (output / "manifest.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    report_dir = root / "ai" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "archive_audit.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    return reports


if __name__ == "__main__":
    for item in audit():
        print(f"{item['archive']}: {item['rows']} rows staged for review; identifiers excluded")
