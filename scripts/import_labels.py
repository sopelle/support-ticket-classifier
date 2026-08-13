"""Validate labels.csv and freeze the labeled rows into labels.jsonl (issue #5).

labels.csv is the working file a human edits by hand; labels.jsonl is a derivative,
fully overwritten on every run - never edit it directly. A row counts as labeled once
both `priority` and `intent` are filled in ("label by dimension, not by ticket" means
long stretches where priority is done and intent isn't - that's normal, not an error),
so a partially-labeled sheet just produces a smaller labels.jsonl rather than failing.

Refuses to shrink the labeled-row count from whatever labels.jsonl already has: a
truncated or mis-edited CSV would otherwise silently drop tickets that were previously
labeled. Pass --force when a shrink is actually intended (a label correctly retracted).

Run as a module from the repo root:
    python -m scripts.import_labels dev
    python -m scripts.import_labels test
"""

import argparse
import csv
import json

from scripts.generate_tickets import DATA_DIR
from triage.taxonomy import Category, Intent, Priority


def _require_valid(row: dict[str, str], field: str, enum_cls: type, line_no: int) -> None:
    value = row[field]
    try:
        enum_cls(value)
    except ValueError:
        raise SystemExit(
            f"labels.csv row {line_no} ({row['id']}): {field}={value!r} is not a valid "
            f"{enum_cls.__name__}"
        ) from None


def _validate_if_present(row: dict[str, str], field: str, enum_cls: type, line_no: int) -> None:
    if row[field]:
        _require_valid(row, field, enum_cls, line_no)


def import_labels(split: str, force: bool) -> None:
    labels_csv = DATA_DIR / split / "labels.csv"
    labels_jsonl = DATA_DIR / split / "labels.jsonl"

    with labels_csv.open(newline="") as f:
        rows = list(csv.DictReader(f))

    labeled = []
    for line_no, row in enumerate(rows, start=2):  # header is line 1
        _require_valid(row, "category", Category, line_no)
        _validate_if_present(row, "priority", Priority, line_no)
        _validate_if_present(row, "intent", Intent, line_no)
        if row["priority"] and row["intent"]:
            labeled.append(
                {
                    "id": row["id"],
                    "category": row["category"],
                    "priority": row["priority"],
                    "intent": row["intent"],
                    "notes": row["notes"],
                }
            )

    if labels_jsonl.exists():
        with labels_jsonl.open() as f:
            existing_count = sum(1 for line in f if line.strip())
        if len(labeled) < existing_count and not force:
            raise SystemExit(
                f"{labels_jsonl} currently has {existing_count} labeled tickets; this run "
                f"would write {len(labeled)}. Refusing to shrink it - pass --force if that's "
                "intended."
            )

    with labels_jsonl.open("w") as f:
        for row in labeled:
            f.write(json.dumps(row) + "\n")

    print(f"{labels_jsonl}: {len(labeled)}/{len(rows)} tickets labeled.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("split", choices=["dev", "test"])
    parser.add_argument(
        "--force", action="store_true", help="Allow the labeled-row count to shrink."
    )
    args = parser.parse_args()
    import_labels(args.split, args.force)


if __name__ == "__main__":
    main()
