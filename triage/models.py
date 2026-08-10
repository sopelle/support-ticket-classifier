"""Core data types for the support-ticket classifier.

Plain dataclasses per CLAUDE.md's stdlib-over-pydantic decision. Classification
revalidates its fields in __post_init__ so an out-of-taxonomy label is rejected
even when a caller bypasses the enum constructor (e.g. passes a raw string).
"""

from dataclasses import dataclass

from triage.taxonomy import Category, Intent, Priority


@dataclass(frozen=True)
class Ticket:
    id: str
    subject: str
    body: str


@dataclass(frozen=True)
class Classification:
    reasoning: str  # generated before the labels, never scored; for CoT and error analysis
    category: Category
    priority: Priority
    intent: Intent

    def __post_init__(self) -> None:
        _reject_unless_valid(self.category, Category, "category")
        _reject_unless_valid(self.priority, Priority, "priority")
        _reject_unless_valid(self.intent, Intent, "intent")


def _reject_unless_valid(value: object, enum_cls: type, field_name: str) -> None:
    try:
        enum_cls(value)
    except ValueError:
        raise ValueError(
            f"{field_name!r} value {value!r} is not a valid {enum_cls.__name__}"
        ) from None
