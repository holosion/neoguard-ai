"""Idempotently stage de-identified archive rows; never populate clinical patients.

Run ai.audit_archives first. Source URLs/licenses remain unknown and every import
stays in review until its original codebook and provenance have been supplied.
"""
import argparse
import json
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import DatasetImport, DatasetImportRow

DEFAULT_DATA = Path(__file__).resolve().parents[2] / "ai" / "data"


def import_archives(db, data_dir=DEFAULT_DATA):
    data_dir = Path(data_dir)
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    results = []
    for entry in manifest:
        key = "newborn-daily" if entry["archive"] == "archive.zip" else "hypothermia-cases"
        existing = db.scalar(select(DatasetImport).where(DatasetImport.dataset_key == key, DatasetImport.sha256 == entry["member_sha256"]))
        if existing:
            results.append({"dataset": key, "status": "duplicate", "import_id": existing.id})
            continue
        staged = [json.loads(line) for line in (data_dir / entry["staging_file"]).read_text(encoding="utf-8").splitlines()]
        if len(staged) != entry["rows"]:
            raise ValueError("Staging row count differs from manifest; rerun archive audit")
        record = DatasetImport(dataset_key=key, archive_name=entry["archive"], member_name=entry["member"],
                               sha256=entry["member_sha256"], schema_version="archive-staging-v1", status="review",
                               rows_seen=len(staged), rows_accepted=0, rows_rejected=0,
                               source_reference=entry.get("source_url"), notes={"license": entry.get("license"),
                               "excluded_fields": entry["excluded_fields"], "review_rows": len(staged)})
        db.add(record)
        db.flush()
        for row in staged:
            payload = {k: v for k, v in row["payload"].items() if k not in ("name", "code")}
            db.add(DatasetImportRow(dataset_import_id=record.id, source_row_number=row["source_row_number"],
                                   external_subject_id=payload.get("baby_id") or payload.get("case"), raw_payload=payload,
                                   validation_status="review", quality_flags=row["quality_flags"]))
        results.append({"dataset": key, "status": "review", "rows": len(staged), "import_id": record.id})
    db.flush()
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    with SessionLocal.begin() as db:
        print(json.dumps(import_archives(db, args.data_dir), indent=2))
