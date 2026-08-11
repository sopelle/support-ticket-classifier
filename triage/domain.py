"""Domain configuration loading.

This is the boundary between the classifier core and the product it's applied to.
Categories, the priority rubric, root causes, and the knowledge base are all
domain-specific; retargeting the classifier to a different product means adding a
domains/<name>/ directory, not editing Python. Intent and priority are universal
(see triage/taxonomy.py) and have no domain config.

Everything here deals in plain strings, not Category - triage.taxonomy imports
load_categories() to build Category, so this module can't import taxonomy back
without a cycle. Callers that need Category instances (e.g. scripts/generate_tickets.py)
convert with Category(value) themselves.
"""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

DOMAINS_DIR = Path(__file__).resolve().parent.parent / "domains"
ACTIVE_DOMAIN = os.environ.get("DOMAIN", "compliance")
DOMAIN_DIR = DOMAINS_DIR / ACTIVE_DOMAIN

DOMAIN_METADATA_PATH = DOMAIN_DIR / "domain.yaml"
TAXONOMY_PATH = DOMAIN_DIR / "taxonomy.yaml"
PRIORITY_RUBRIC_PATH = DOMAIN_DIR / "priority_rubric.md"
CAUSES_PATH = DOMAIN_DIR / "causes.yaml"
KNOWLEDGE_BASE_DIR = DOMAIN_DIR / "knowledge_base"


def load_categories() -> dict[str, str]:
    """Return {category_id: description}, in taxonomy.yaml's order."""
    data = yaml.safe_load(TAXONOMY_PATH.read_text())
    return {c["id"]: c["description"] for c in data["categories"]}


def load_product_description() -> str:
    """How the ticket-generation prompt introduces the product - see domain.yaml."""
    data = yaml.safe_load(DOMAIN_METADATA_PATH.read_text())
    return data["product_description"]


@dataclass(frozen=True)
class Symptom:
    text: str
    category: str
    kb_file: str | None  # set only when text is drawn verbatim from the knowledge base


@dataclass(frozen=True)
class Cause:
    id: str
    true_category: str
    description: str
    symptoms: tuple[Symptom, ...]  # symptoms[0] always matches true_category


def load_causes() -> list[Cause]:
    data = yaml.safe_load(CAUSES_PATH.read_text())
    return [
        Cause(
            id=c["id"],
            true_category=c["true_category"],
            description=c["description"],
            symptoms=tuple(
                Symptom(text=s["text"], category=s["category"], kb_file=s["kb_file"])
                for s in c["symptoms"]
            ),
        )
        for c in data["causes"]
    ]


def load_deadline_pressure_messaging() -> dict[str, str]:
    """Domain-flavored instruction text per deadline-pressure level (see
    scripts/generate_tickets.py's DeadlinePressure) - what 'imminent' etc. means is
    domain vocabulary ('an audit'), the levels themselves are universal."""
    data = yaml.safe_load(DOMAIN_METADATA_PATH.read_text())
    return data["deadline_pressure_messaging"]
