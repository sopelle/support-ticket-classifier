# Support Ticket Classifier

An LLM-powered classifier that triages support tickets for a compliance automation platform (classifying each by category, priority, and intent) paired with an
evaluation harness that measures its own accuracy against a labeled test set.

**Status:** work in progress.

## Setup

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

Set the Claude API key in a `.env` file (see `.env.example`).

## Architecture

Ports and adapters: the core knows only its own types and never depends on a ticketing platform.

- `triage/` : core. `taxonomy.py` (label enums, single source of truth), `models.py` (`Ticket`, `Classification`), `classifier.py` (`classify(ticket)`)
- `triage/adapters/` : I/O boundaries. Swapping in a real ticketing system means writing a new adapter, not touching the core
- `triage/prompts/` : prompt source material (rubrics, instructions) as markdown, loaded by the prompt builder rather than inlined as Python strings. Doubles as the human labeling guide for the gold dataset
- `eval/` : evaluation harness, deliberately outside the core package. Parameterized by dimension (`category`, `priority`, `intent`), not hardcoded to one
- `scripts/` : entry points (ticket generation, batch runs)
- `data/knowledge_base/` : the compliance FAQ; grounds ticket generation today, becomes the retrieval source later