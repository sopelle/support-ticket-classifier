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

    python -m scripts.generate_tickets --dry-run    # inspect corpus shape, no API calls
    python -m scripts.generate_tickets --limit 8    # smoke-test generation, a few real API calls

Read the 8 tickets it wrote before doing a full run. Generation resumes from whatever's
already on disk (already-generated ids are skipped), so if the prompt needs a fix, delete
this batch before rerunning — otherwise the corpus ends up mixing tickets written under the
old prompt with ones written under the new one:

    rm -rf data/compliance

    python -m scripts.generate_tickets              # build it (~200 API calls)

Once a split has tickets, build its label sheet and label by hand (issue #5) — dev
first, it unblocks the classifier work; test comes later, once a prompt is worth
measuring:

    python -m scripts.build_label_sheet dev    # writes data/compliance/dev/labels.csv
    python -m scripts.import_labels dev        # labels.csv -> labels.jsonl, once rows are labeled

`labels.csv` is the working file — open it, fill in `priority` and `intent` by hand (by
dimension, not by ticket: all of `priority` first, then all of `intent`), leave `notes`
on anything borderline. `category` and `priority_derived` are pre-filled and rarely need
touching; `priority_derived` is a draft, not a label — see `derive_priority`'s docstring
in `build_label_sheet.py` for where it's known to be wrong. You normally run
`build_label_sheet` once per split and never again — `import_labels` is the command you
re-run as labeling progresses. If you do re-run `build_label_sheet`, it preserves any row
where `priority`, `intent` or `notes` is filled in, or where `category` has been
corrected away from the derived value. A row with none of that yet is rewritten from
scratch. Changing `primary_category` after labeling has started is not propagated —
delete `labels.csv` and rebuild it (no API calls; the ticket text does not depend on
`primary_category`). An edit to `priority_derived` alone is not treated as in-progress
work and will be overwritten. `import_labels` refuses to shrink `labels.jsonl`'s row
count unless passed `--force`.

## Architecture

Ports and adapters: the core knows only its own types and never depends on a ticketing platform.

- `triage/` : core. `taxonomy.py` (label enums, single source of truth — `Category` is built at import time from the active domain pack; `Priority`/`Intent` are universal and static), `domain.py` (loads the active domain pack: categories, causes, priority rubric, knowledge base — swap domains via the `DOMAIN` env var, not code edits), `models.py` (`Ticket`, `Classification`), `classifier.py` (`classify(ticket)`)
- `triage/adapters/` : I/O boundaries. Swapping in a real ticketing system means writing a new adapter, not touching the core
- `domains/<name>/` : one product's vocabulary — `domain.yaml` (product description, deadline-pressure messaging), `taxonomy.yaml` (category list), `causes.yaml` (root-cause catalog), `priority_rubric.md`, `knowledge_base/*.md`. Each file holds exactly what its name says, nothing else. `domains/compliance/` is the only one today
- `eval/` : evaluation harness, deliberately outside the core package. Parameterized by dimension (`category`, `priority`, `intent`), not hardcoded to one
- `scripts/` : entry points. `generate_tickets.py` (corpus generation), `build_label_sheet.py` / `import_labels.py` (hand-labeling workflow, issue #5)