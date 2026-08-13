"""Corpus invariants for scripts.generate_tickets.build_scenarios.

An invariant is pass/fail and must break the build; a distribution is something a human
reads before spending money on generation. These three checks used to live partly in
--dry-run (as a SystemExit for leakage, nothing at all for pairwise axis locking) - which
is exactly how an unrelated Intent taxonomy change (5 values to 4) once relocked every
axis derived from `i % len(...)` without anyone noticing, since nothing failed and nobody
happened to read the --dry-run table that day. --dry-run still prints per-split counts,
tickets per cause, documented ratios, and the same axis-gap numbers test_axis_dev_test_gap
asserts on below.

Leakage is checked in both places: split_leakage() backs this module's test *and* a
SystemExit main() raises before --dry-run even branches, since generation can be run
without a dry-run first and that's exactly the run leakage would otherwise waste money on.
Pairwise axis locking and the split gap threshold stay test-only - they degrade the
corpus's statistics, not its validity, so failing the build is enough.
"""

from itertools import combinations

from scripts.generate_tickets import (
    MAX_SPLIT_GAP,
    DeadlinePressure,
    Difficulty,
    Intent,
    Tone,
    build_scenarios,
    split_axis_gaps,
    split_leakage,
)

# tone, deadline_pressure, presented_as, difficulty and workaround are each supposed to
# vary independently of one another, so pairwise coverage should approach the full cross
# product. Calibrated on the corpus's actual output: the two pairs carrying a deliberate
# override (MISSING_DECIDING_FACT forcing deadline_pressure, WORKING_AS_DESIGNED forcing
# presented_as) land at 71% and 83%; every other pair hits 100%. The bug this guards
# against - axes derived from the same loop counter, whose cardinalities shared factors -
# held pairs between 25% and 58%.
MIN_AXIS_COVERAGE = 0.65

AXES = {
    "tone": (lambda s: s.tone, list(Tone)),
    "deadline_pressure": (lambda s: s.deadline_pressure, list(DeadlinePressure)),
    "presented_as": (lambda s: s.presented_as, list(Intent)),
    "difficulty": (lambda s: s.difficulty, list(Difficulty)),
    "workaround": (lambda s: s.workaround, [False, True]),
}


def test_no_cause_or_symptom_leaks_across_splits():
    leaked_causes, leaked_symptoms = split_leakage(build_scenarios())
    assert not leaked_causes, f"cause(s) present in both splits: {sorted(leaked_causes)}"
    assert not leaked_symptoms, f"symptom(s) present in both splits: {sorted(leaked_symptoms)}"


def test_axis_pairs_are_not_locked_together():
    scenarios = build_scenarios()

    for (name1, (get1, values1)), (name2, (get2, values2)) in combinations(AXES.items(), 2):
        seen = {(get1(s), get2(s)) for s in scenarios}
        possible = len(values1) * len(values2)
        coverage = len(seen) / possible
        assert coverage >= MIN_AXIS_COVERAGE, (
            f"{name1} x {name2} covers only {len(seen)}/{possible} ({coverage:.0%}) of "
            "possible combinations - one axis may be derived from the other's loop "
            "counter again"
        )


def test_axis_dev_test_gap_stays_under_threshold():
    scenarios = build_scenarios()

    for label, dev_share, test_share, gap in split_axis_gaps(scenarios):
        assert gap <= MAX_SPLIT_GAP, (
            f"{label}: dev {dev_share:.0%} vs test {test_share:.0%} (gap {gap:.0%}) "
            f"exceeds MAX_SPLIT_GAP={MAX_SPLIT_GAP:.0%}"
        )
