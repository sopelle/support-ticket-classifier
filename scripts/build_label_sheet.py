"""Build labels.csv for a generated ticket split: a human-editable sheet pre-filled with
a derived category and a draft priority, ready for hand-labeling (issue #5).

`intent` is deliberately never pre-filled - deriving it from `presented_as` is wrong
often enough, in a way that looks plausible, that a pre-filled value would get
rubber-stamped and the gold labels would inherit the generator's bias. `priority` is
pre-filled as a draft specifically so it can be confirmed or corrected, not accepted
blind - see derive_priority's docstring for where the draft is known to be wrong.

Re-running merges rather than overwriting: a row with anything human recorded on it -
`priority`, `intent`, `notes`, or a `category` corrected away from what's freshly
derived - is preserved exactly. An edit to `priority_derived` alone is not on that list
and is overwritten on the next run. A row with none of that yet is untouched and gets
rewritten from scratch, so a fix to derive_priority reaches every ticket nobody has
gotten to yet instead of only new ones. A fix to primary_category does not: a row whose
derived category has moved looks, to _is_untouched, exactly like a human correction, so
it's preserved with its old category instead of refreshed. See _is_untouched.

Run as a module from the repo root:
    python -m scripts.build_label_sheet dev
    python -m scripts.build_label_sheet test
"""

import argparse
import csv
import json
from pathlib import Path

from scripts.generate_tickets import (
    DATA_DIR,
    DEV_PATH,
    TEST_PATH,
    DeadlinePressure,
    Scenario,
    Tone,
    build_scenarios,
)
from triage.models import Ticket
from triage.taxonomy import Priority

LABEL_FIELDS = ["id", "subject", "body", "category", "priority_derived", "priority", "intent", "notes"]

# Priority.LOW < Priority.MEDIUM < Priority.HIGH, in the order the stated-urgency
# adjustment below raises through.
_LEVELS = [Priority.LOW, Priority.MEDIUM, Priority.HIGH]


def _raise_one_level(level: Priority) -> Priority:
    return _LEVELS[min(_LEVELS.index(level) + 1, len(_LEVELS) - 1)]


def derive_priority(scenario: Scenario) -> Priority:
    """Draft priority from deadline_pressure, workaround and tone only - the three
    situational fields the rubric's Medium/Low mechanics and stated-urgency adjustment
    turn on (domains/compliance/priority_rubric.md). Three known blind spots, all for
    manual review to catch, not this function:

    - Under-calls High: confirmed/suspected security exposure, a platform-wide outage,
      and irrecoverable data loss are properties of the *cause*, not of these three
      fields, so a severe-blocker ticket drafts as Medium or Low here.
    - Can over-call Medium/High on tickets whose rubric-correct level is Low for reasons
      unrelated to blocking - a feature request or a working-as-designed report can still
      carry workaround=False and an urgent tone, and this function has no field that
      tells that apart from an actual blocker.
    - Under-calls Medium: with workaround=True, no imminent deadline and a neutral
      tone, this drafts Low - but the rubric puts a broken control or integration
      with a workaround at Medium, as it does a bug that blocks one user or team
      with no self-service fix. A Low draft on a ticket reporting something broken
      is the case to reread, not to rubber-stamp.
    """
    if scenario.deadline_pressure == DeadlinePressure.IMMINENT:
        base = Priority.HIGH
    elif not scenario.workaround:
        base = Priority.MEDIUM
    else:
        base = Priority.LOW

    if scenario.tone == Tone.RELATIONSHIP_AT_RISK:
        return Priority.HIGH  # sets High on its own, whatever the base level
    if scenario.tone in (Tone.FRUSTRATED, Tone.URGENT_STATED):
        return _raise_one_level(base)  # never lowers
    return base


def _load_tickets(path: Path) -> dict[str, Ticket]:
    tickets = {}
    with path.open() as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            tickets[d["id"]] = Ticket(id=d["id"], subject=d["subject"], body=d["body"])
    return tickets


def _load_existing_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="") as f:
        return {row["id"]: row for row in csv.DictReader(f)}


def _fresh_row(ticket: Ticket, scenario: Scenario) -> dict[str, str]:
    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "body": ticket.body,
        "category": scenario.primary_category.value,
        "priority_derived": derive_priority(scenario).value,
        "priority": "",
        "intent": "",
        "notes": "",
    }


def _is_untouched(existing_row: dict[str, str], fresh_row: dict[str, str]) -> bool:
    """True if nothing human is recorded on this row yet: priority/intent/notes are
    still blank, and category still matches what's freshly derived (a mismatch there
    means a human corrected it, even before touching priority or intent - see the
    Manual section of issue #5, which checks derived category before priority/intent
    are necessarily filled in). Only an untouched row is safe to overwrite with a fresh
    prefill; anything else must be preserved exactly."""
    if existing_row["priority"] or existing_row["intent"] or existing_row["notes"]:
        return False
    return existing_row["category"] == fresh_row["category"]


def build_label_sheet(split: str) -> None:
    ticket_path = DEV_PATH if split == "dev" else TEST_PATH
    labels_path = DATA_DIR / split / "labels.csv"

    tickets = _load_tickets(ticket_path)
    scenarios_by_id = {s.id: s for s in build_scenarios() if s.split == split}
    existing = _load_existing_rows(labels_path)

    rows = []
    new_count = 0
    refreshed_count = 0
    for ticket_id, ticket in tickets.items():
        scenario = scenarios_by_id[ticket_id]
        fresh = _fresh_row(ticket, scenario)

        old = existing.get(ticket_id)
        if old is None:
            rows.append(fresh)
            new_count += 1
        elif _is_untouched(old, fresh):
            # No priority/intent/notes yet, and category still matches what's freshly
            # computed - nothing human is recorded here, so it's safe to pick up any
            # change to primary_category or derive_priority since this row was last
            # written.
            rows.append(fresh)
            refreshed_count += 1
        else:
            rows.append(old)

    labels_path.parent.mkdir(parents=True, exist_ok=True)
    with labels_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LABEL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    preserved_count = len(rows) - new_count - refreshed_count
    print(
        f"{labels_path}: {len(rows)} rows ({new_count} new, {refreshed_count} refreshed, "
        f"{preserved_count} preserved)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("split", choices=["dev", "test"])
    args = parser.parse_args()
    build_label_sheet(args.split)


if __name__ == "__main__":
    main()
