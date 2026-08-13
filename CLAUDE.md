# Support Ticket Classifier

An LLM-powered classifier that triages support tickets (category, priority, intent),
paired with an evaluation harness that measures its own accuracy against a
labeled test set and tracks regressions across prompt iterations.

## Setup

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

Set the Claude API key in a `.env` file (see `.env.example`).

## Conventions

- Pin dependencies to exact versions in `requirements.txt`.
- The README is the project's showcase. Update it in the same commit whenever results, commands, or project structure change.
- Numbers claimed in the README must come from an actual evaluation run, never from an estimate. If a run has not happened yet, say so instead of guessing.
- Nothing outside `domains/` may depend on a specific domain pack. Tests especially: naming a category (`Category.EVIDENCE`) breaks on every other pack : take one positionally with `next(iter(Category))`.
- When a docstring, comment or README line cites something that comes from a domain pack — a category name, a path under `domains/<name>/`, a count of causes, an observed dev/test gap : say it is an example measured on the default pack, not a property of the system. The reasoning stays; the reader needs to know what would change under a different pack.

## Architecture

Ports and adapters: the core knows only its own types and never depends on a ticketing platform.

- `triage/` : core. `taxonomy.py` (label enums, single source of truth — `Category` is built at import time from the active domain pack; `Priority`/`Intent` are universal and static), `domain.py` (loads the active domain pack: categories, causes, priority rubric, knowledge base — swap domains via the `DOMAIN` env var, not code edits), `models.py` (`Ticket`, `Classification`), `classifier.py` (`classify(ticket)`)
- `triage/adapters/` : I/O boundaries. Swapping in a real ticketing system means writing a new adapter, not touching the core
- `domains/<name>/` : one product's vocabulary — `domain.yaml` (product description, deadline-pressure messaging), `taxonomy.yaml` (category list), `causes.yaml` (root-cause catalog), `priority_rubric.md`, `knowledge_base/*.md`. Each file holds exactly what its name says, nothing else. `domains/compliance/` is the only one today
- `eval/` : evaluation harness, deliberately outside the core package. Parameterized by dimension (`category`, `priority`, `intent`), not hardcoded to one
- `scripts/` : entry points. `generate_tickets.py` (corpus generation), `build_label_sheet.py` / `import_labels.py` (hand-labeling workflow, issue #5)

Decisions worth not re-litigating:

- Stdlib `dataclasses`, not pydantic. The taxonomy enums already reject invalid labels, and the tool-use JSON schema is written by hand on purpose
- Prefer the standard library. Add a dependency only when it does something the stdlib genuinely cannot (PyYAML for the domain packs is the one exception so far)
- Domain content (categories, priority rubric, causes, knowledge base, product description) lives in `domains/<name>/`, not Python. Retargeting the classifier to a different product means adding a directory, not editing code
- Batch-first. Real-time triggering is an adapter concern, not a core concern
- Structured output via tool use is not MCP; the core calls the API directly
- `Classification` carries a `reasoning` field, generated before the labels. It is never scored: it exists to make the model reason before deciding, and to make error analysis possible
- Work is tracked in GitHub issues