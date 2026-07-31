"""Label taxonomy for a compliance support-ticket classifier.

These enums are the single source of truth for the classification labels.
Both the classifier (to constrain the model's output) and the evaluation
harness (to score predictions against gold labels) import them from here.
"""

from enum import StrEnum


class Category(StrEnum):
    """What the ticket is about. Used for routing and FAQ lookup."""

    FRAMEWORKS = "frameworks"                # SOC 2 / ISO 27001 / GDPR scoping and setup
    CONTROLS = "controls"                    # implementing and tracking controls
    EVIDENCE = "evidence"                    # collecting and uploading evidence
    INTEGRATIONS = "integrations"            # connecting cloud/SaaS to auto-collect evidence
    POLICIES = "policies"                    # policy templates, customization, approvals
    ACCESS_MANAGEMENT = "access_management"  # users, roles, permissions, access reviews
    AUDITS = "audits"                        # audit preparation and auditor access
    ACCOUNT_BILLING = "account_billing"      # account setup, subscription, billing


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