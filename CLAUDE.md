# Support Ticket Classifier

An LLM-powered agent that triages support tickets (category, priority, intent),
paired with an evaluation harness that measures its own accuracy against a
labeled test set and tracks regressions across prompt iterations.

## Setup

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

Set the Claude API key in a `.env` file (see `.env.example`).

## Conventions

- Pin dependencies to exact versions in `requirements.txt`.

## Architecture

_To be defined during planning._