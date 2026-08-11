# Support Ticket Classifier

An LLM-powered classifier that triages support tickets (category, priority, intent) for whichever
product a domain pack under `domains/` targets — `domains/compliance/` ships as the default,
targeting a fictional SOC 2 / ISO 27001 / GDPR compliance automation platform. Paired with an evaluation
harness that measures its own accuracy against a labeled test set.

**Status:** work in progress.

## Setup

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

Set the Claude API key in a `.env` file (see `.env.example`).

Scripts import from `triage`, so run them as modules from the repo root:

    python -m scripts.generate_tickets --dry-run   # inspect corpus shape, no API calls
    python -m scripts.generate_tickets             # build it (~200 API calls)

## Architecture

Ports and adapters: the core knows only its own types and never depends on a ticketing platform.

- `triage/` : core. `taxonomy.py` (label enums, single source of truth — `Category` is built at import time from the active domain pack; `Priority`/`Intent` are universal and static), `domain.py` (loads the active domain pack: categories, causes, priority rubric, knowledge base — swap domains via the `DOMAIN` env var, not code edits), `models.py` (`Ticket`, `Classification`), `classifier.py` (`classify(ticket)`)
- `triage/adapters/` : I/O boundaries. Swapping in a real ticketing system means writing a new adapter, not touching the core
- `domains/<name>/` : one product's vocabulary — `domain.yaml` (product description, deadline-pressure messaging), `taxonomy.yaml` (category list), `causes.yaml` (root-cause catalog), `priority_rubric.md`, `knowledge_base/*.md`. Each file holds exactly what its name says, nothing else. `domains/compliance/` is the only one today
- `eval/` : evaluation harness, deliberately outside the core package. Parameterized by dimension (`category`, `priority`, `intent`), not hardcoded to one
- `scripts/` : entry points (ticket generation, batch runs)