import pytest

from triage.models import Classification, Ticket
from triage.taxonomy import Category, Intent, Priority


def test_classification_accepts_valid_labels():
    classification = Classification(
        reasoning="reasoning",
        category=Category.EVIDENCE,
        priority=Priority.HIGH,
        intent=Intent.BUG,
    )

    assert classification.category == Category.EVIDENCE
    assert classification.priority == Priority.HIGH
    assert classification.intent == Intent.BUG


def test_classification_accepts_raw_strings_that_match_taxonomy():
    classification = Classification(
        reasoning="reasoning", category="evidence", priority="high", intent="bug"
    )

    assert classification.category == Category.EVIDENCE


@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("category", "not_a_category"),
        ("priority", "urgent"),
        ("intent", "rant"),
    ],
)
def test_classification_rejects_labels_outside_taxonomy(field, bad_value):
    kwargs = {
        "reasoning": "reasoning",
        "category": Category.EVIDENCE,
        "priority": Priority.HIGH,
        "intent": Intent.BUG,
    }
    kwargs[field] = bad_value

    with pytest.raises(ValueError):
        Classification(**kwargs)


def test_ticket_holds_raw_fields():
    ticket = Ticket(id="t-1", subject="Can't upload evidence", body="Upload fails with a 500.")

    assert ticket.id == "t-1"
    assert ticket.subject == "Can't upload evidence"
