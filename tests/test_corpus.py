"""Regression test for axis independence in scripts.generate_tickets.build_scenarios.

tone, deadline_pressure, presented_as, difficulty and workaround are each supposed to
vary independently of one another, so pairwise coverage should approach the full cross
product. MIN_AXIS_COVERAGE is calibrated on the corpus's actual output: the two pairs
carrying a deliberate override (MISSING_DECIDING_FACT forcing deadline_pressure,
WORKING_AS_DESIGNED forcing presented_as) land at 71% and 83%; every other pair hits
100%. The bug this guards against - axes derived from the same loop counter, whose
cardinalities shared factors - held pairs between 25% and 58%.
"""

from itertools import combinations

from scripts.generate_tickets import DeadlinePressure, Difficulty, Intent, Tone, build_scenarios

MIN_AXIS_COVERAGE = 0.65

AXES = {
    "tone": (lambda s: s.tone, list(Tone)),
    "deadline_pressure": (lambda s: s.deadline_pressure, list(DeadlinePressure)),
    "presented_as": (lambda s: s.presented_as, list(Intent)),
    "difficulty": (lambda s: s.difficulty, list(Difficulty)),
    "workaround": (lambda s: s.workaround, [False, True]),
}


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
