# Archive data inventory and storage plan

Inspected the two project archives as read-only ZIP files. Their CSVs are research/training inputs, not live device telemetry. Neither should be inserted into the clinical `readings` table or shown on the nurse dashboard as a current patient.

## `archive.zip` — newborn daily observations

Contains `newborn_health_monitoring_with_risk.csv`, with 3,000 rows for 100 `baby_id` values: 30 date-level rows per subject, ages 1–30 days. It has birth measurements, daily anthropometrics, temperature, HR, respiratory rate, oxygen saturation, feeding/output/jaundice fields, sparse APGAR, and a `risk_level` value (`Healthy` or `At Risk`).

Store its cleanable fields as:

- One `dataset_imports` row for archive/member, file SHA-256, source/license citation, schema version, import counts and review status.
- One pseudonymous `dataset_subjects` row per `(dataset_import_id, baby_id)`. Put sex, gestational age, birth weight/length/head circumference, and APGAR here. These birth fields are repeated consistently across the 30 rows; APGAR is present only on age day 1 (100/3,000 rows).
- One `dataset_observations` row per source row, preserving the source date as `DATE` and `age_days` as an integer. Do not manufacture a midnight UTC timestamp for a daily observation. Store daily measurements, feeding, output, jaundice, and the original `risk_level` as `imported_risk_label`.
- A matching `dataset_import_rows` record for source row number, sanitized raw payload, validation status, and quality flags. This supports lineage and review without making the original file format the live application schema.

The CSV contains a `name` column. Do not copy names into `dataset_subjects`, raw JSON, model features, or dashboard data. The archives appear synthetic, but keep the original archive in restricted raw-data storage and treat it as sensitive unless its provenance is confirmed. `baby_id` is unique only within this import; always scope subject identity by `dataset_import_id`.

Seven observations have oxygen saturation above 100 (maximum 101). Preserve those source values in the research table and attach a quality flag; do not clamp them to 100 or load them into live vitals. The `risk_level` label has no supplied definition, so it must remain a source label until its derivation and intended prediction target are documented. Do not convert it directly into clinical hypothermia/sepsis labels.

## `archive_1.zip` — hypothermia temperature sequence

Contains `Hypothermia.csv`, 200 case rows, with `case`, sometimes blank `code` (3 rows), `date`, `time`, weight, `t.nur`, `t.or`, and `t.1` through `t.6`. Temperatures become increasingly sparse across columns: `t.3` is blank in 83 rows, `t.4` in 179, `t.5` in 196, and `t.6` in 199. One `t.3` value is zero. The date column includes values such as `81.01` and `98`; it cannot be treated as a valid date as-is. The meaning of the time format and the intervals/order represented by the temperature columns are not documented in the archive.

For now, store these rows only in `dataset_import_rows` with their original column names and strings, plus review flags. Do not assign absolute timestamps, interpret zero as a measured temperature, or map `t.nur`/`t.or`/`t.1`… as a specific clinical sequence until the dataset codebook confirms the meaning, units, clock convention, and missing-value convention. After confirmation, add a versioned parser and normalized temperature observations while retaining source row lineage. Weight ranges from 650 to 4,600; confirm its unit before conversion (it may be grams, but the archive alone does not prove that).

## Storage boundaries and import policy

The ORM models intentionally separate these four research tables from clinical records:

- `dataset_imports`: immutable file identity/provenance and import status/counts.
- `dataset_import_rows`: row-level staging, source row number, sanitized JSON payload and validation/review flags.
- `dataset_subjects`: source-scoped pseudonymous cohort subjects; never linked to clinical `patients`.
- `dataset_observations`: normalized day-level observations for sources whose date/field meanings are known.

Keep raw archives outside PostgreSQL in an access-controlled, backed-up data area; record their hash and location/provenance in the import manifest. Before an importer marks rows `accepted`, validate expected headers, duplicate source rows, subject-level consistency, dates, units, missingness, and numeric ranges. Preserve unusual values with quality flags in research storage rather than silently correcting them. Only accepted, documented training records should feed the future AI pipeline. Do not use these two archives to populate live demo patients by default.
