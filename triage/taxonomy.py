"""Label taxonomy for the support-ticket classifier.

These are the single source of truth for the classification labels. Both the
classifier (to constrain the model's output) and the evaluation harness (to score
predictions against gold labels) import them from here.

Category is domain-dependent - it's built at import time from the active domain's
taxonomy.yaml (see triage/domain.py), so retargeting the classifier to a different
product doesn't touch this file. Priority and Intent are universal: every domain
triages by the same urgency levels and the same five requester intents.
"""

from enum import StrEnum

from triage.domain import load_categories

Category = StrEnum("Category", {cat_id.upper(): cat_id for cat_id in load_categories()})
Category.__doc__ = "What the ticket is about. Used for routing and FAQ lookup."


class Priority(StrEnum):
    """How prio the ticket is."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Intent(StrEnum):
    """What the requester wants. Independent of the ticket's topic."""

    QUESTION = "question"                # how-to / clarification
    BUG = "bug"                          # something is broken
    FEATURE_REQUEST = "feature_request"  # asking for new functionality
    BILLING_REQUEST = "billing_request"  # account or billing action
    COMPLAINT = "complaint"              # dissatisfaction
