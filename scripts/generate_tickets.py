"""Generate the synthetic support-ticket corpus (dev + test splits).

Tickets are generated from a Scenario, not from a label: a category/priority/intent
in the prompt would just get paraphrased back, producing a corpus the classifier
could ace without proving anything. Each Scenario is seeded from a `cause` - a
specific root cause, documented in the active domain's knowledge base or invented -
plus the situational variables the priority rubric depends on (deadline pressure,
workaround, tone, ...). No labels are produced here - labeling is issue #5.

The cause catalog, category list, knowledge base, and generation prompt's product
description all come from the active domain pack (triage/domain.py, defaulting to
domains/compliance/ - set the DOMAIN env var to point at a different one). Nothing
in this script is compliance-specific.

A cause is not the same as its symptom: `cause` is a stable identifier that can
surface as more than one customer-visible symptom, in more than one category (an
expired integration credential shows up both as "integration disconnected" in
integrations and "control keeps failing" in controls). `misleading_symptom`
scenarios deliberately use the symptom whose apparent category differs from the
cause's true category - the tie-break the classifier has to get right.

About a third of scenarios are invented (`documented=False`, no `kb_file`): plausible
problems no knowledge-base article covers. Without them the corpus would just be a
copy of the FAQ, and retrieval/cause-discovery work downstream would never have to
handle "not in the docs."

Scenario selection is deterministic (cause rotation + axis cycling), not random
sampling, so re-running reproduces the same scenario list. Neither a `symptom` nor
a `cause` may appear in both splits - causes are partitioned into dev/test pools
per category before any tickets are generated. Already-generated ids (present in
the split file) are skipped, so a partial or failed run can be resumed without
re-billing completed tickets. generation_log.jsonl records the full Scenario for
every id, which is what makes the corpus auditable and regenerable.

Imports from `triage`, so run as a module from the repo root:
    python -m scripts.generate_tickets --dry-run
"""

import argparse
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from triage import domain
from triage.models import Ticket
from triage.taxonomy import Category, Intent

REPO_ROOT = Path(__file__).resolve().parent.parent
# Namespaced by domain - two domain packs generating corpora shouldn't overwrite each other.
DATA_DIR = REPO_ROOT / "data" / domain.ACTIVE_DOMAIN
DEV_PATH = DATA_DIR / "dev" / "tickets.jsonl"
TEST_PATH = DATA_DIR / "test" / "tickets.jsonl"
LOG_PATH = DATA_DIR / "generation_log.jsonl"

# The classifier being evaluated must not be the model that wrote the corpus.
MODEL = "claude-sonnet-5"

# ~60 dev / ~140 test overall, per the issue - spread evenly across however many
# categories the active domain defines (5-8 dev / 15-20 test per category, for the
# compliance domain's 8 categories; the range shifts with category count).
DEV_TOTAL = 60
TEST_TOTAL = 140
DEV_SHARE = 0.3  # dev's share of each category's cause pool


def _spread(total: int, n: int) -> list[int]:
    """Split `total` as evenly as possible across `n` categories."""
    base, remainder = divmod(total, n)
    return [base + 1 if i < remainder else base for i in range(n)]


DEV_COUNTS: dict[Category, int] = dict(zip(Category, _spread(DEV_TOTAL, len(Category))))
TEST_COUNTS: dict[Category, int] = dict(zip(Category, _spread(TEST_TOTAL, len(Category))))

CATEGORY_DESCRIPTIONS: dict[Category, str] = {
    Category(cat_id): description for cat_id, description in domain.load_categories().items()
}


class DeadlinePressure(StrEnum):
    """How close the ticket is to a domain deadline (an audit, in the compliance
    domain) - the axis the priority rubric's High-vs-Medium check turns on. The
    levels are universal; what they mean in prose is domain-supplied (see
    render_prompt and domain.load_deadline_pressure_messaging)."""

    IMMINENT = "imminent"
    SCHEDULED = "scheduled"
    NONE = "none"
    NOT_MENTIONED = "not_mentioned"


DEADLINE_PRESSURE_MESSAGING: dict[str, str] = domain.load_deadline_pressure_messaging()


class Tone(StrEnum):
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    URGENT_STATED = "urgent_stated"
    RELATIONSHIP_AT_RISK = "relationship_at_risk"


class Difficulty(StrEnum):
    PLAIN = "plain"
    MULTI_TOPIC = "multi_topic"
    MISLEADING_SYMPTOM = "misleading_symptom"
    WORKING_AS_DESIGNED = "working_as_designed"
    MISSING_DECIDING_FACT = "missing_deciding_fact"
    CAUSE_UNDETERMINABLE = "cause_undeterminable"


@dataclass(frozen=True)
class Symptom:
    text: str
    category: Category  # the category this symptom sounds like it belongs to
    kb_file: str | None  # source knowledge-base file, or None if invented


@dataclass(frozen=True)
class Cause:
    id: str
    true_category: Category
    description: str  # prompt-grounding text; not part of the logged Scenario
    symptoms: tuple[Symptom, ...]  # symptoms[0] always matches true_category


def _load_causes() -> list[Cause]:
    """Convert the domain pack's plain-string Cause/Symptom records into this
    script's Category-typed ones."""
    return [
        Cause(
            id=c.id,
            true_category=Category(c.true_category),
            description=c.description,
            symptoms=tuple(
                Symptom(text=s.text, category=Category(s.category), kb_file=s.kb_file)
                for s in c.symptoms
            ),
        )
        for c in domain.load_causes()
    ]


ALL_CAUSES: list[Cause] = _load_causes()
CAUSES_BY_ID: dict[str, Cause] = {cause.id: cause for cause in ALL_CAUSES}

# The catalog-wide documented share (27/88 causes today). Both splits, and every
# category, target this same figure - a category's own documented:invented ratio
# varies too much (CONTROLS has 1 documented cause out of 11) to hit reliably by
# just preserving whatever ratio its pool happens to have after rounding.
DOCUMENTED_SHARE = sum(1 for c in ALL_CAUSES if c.symptoms[0].kb_file is not None) / len(ALL_CAUSES)


def allocate_causes(pool: list[Cause], n: int) -> list[Cause]:
    """Pick n causes from the pool, targeting DOCUMENTED_SHARE regardless of how the
    pool's own documented:invented ratio landed, rotating within each group so no
    single cause is front-loaded the way pool[i % len(pool)] would front-load
    whichever cause happens to sort first."""
    documented = [c for c in pool if c.symptoms[0].kb_file is not None]
    invented = [c for c in pool if c.symptoms[0].kb_file is None]

    n_doc = round(n * DOCUMENTED_SHARE) if documented else 0
    if not invented:
        n_doc = n
    n_inv = n - n_doc

    return (
        [documented[i % len(documented)] for i in range(n_doc)]
        + [invented[i % len(invented)] for i in range(n_inv)]
    )


@dataclass(frozen=True)
class Scenario:
    id: str
    split: str
    symptom: str
    cause: str
    primary_category: Category
    documented: bool
    kb_file: str | None
    deadline_pressure: DeadlinePressure
    workaround: bool
    tone: Tone
    presented_as: Intent
    difficulty: Difficulty
    secondary_category: Category | None = None  # only for multi_topic


def split_causes(category: Category) -> tuple[list[Cause], list[Cause]]:
    """Partition a category's causes into disjoint dev/test pools, so no cause - and
    therefore no symptom - crosses splits.

    The documented and invented groups are split separately (a stratified split):
    cutting a pre-mixed list at DEV_SHARE only gets each pool close to the category's
    ratio, and "close" on pools this small (as few as 4 causes) rounds the wrong way
    often enough to matter. Splitting within each stratum first means every prefix -
    not just the whole list - reflects the group's own size.
    """
    pool = [c for c in ALL_CAUSES if c.true_category == category]
    documented = [c for c in pool if c.symptoms[0].kb_file is not None]
    invented = [c for c in pool if c.symptoms[0].kb_file is None]

    def cut(group: list[Cause]) -> tuple[list[Cause], list[Cause]]:
        n_dev = math.ceil(len(group) * DEV_SHARE)
        return group[:n_dev], group[n_dev:]

    doc_dev, doc_test = cut(documented)
    inv_dev, inv_test = cut(invented)
    return doc_dev + inv_dev, doc_test + inv_test


def build_scenarios() -> list[Scenario]:
    categories = list(Category)
    hard_types = [
        Difficulty.MULTI_TOPIC,
        Difficulty.MISLEADING_SYMPTOM,
        Difficulty.WORKING_AS_DESIGNED,
        Difficulty.MISSING_DECIDING_FACT,
        Difficulty.CAUSE_UNDETERMINABLE,
    ]
    scenarios: list[Scenario] = []
    # Indexed by split, not reset per category: at ~17-20 tickets per category, a
    # per-category (i // 4) % len(hard_types) reset never reaches later hard_types
    # once there are more hard types than a single category has slots for. Carrying
    # the rotation across categories still gives every hard type - including the one
    # a given category runs out of room for - somewhere in the split.
    hard_counts = {"dev": 0, "test": 0}

    for category in categories:
        dev_pool, test_pool = split_causes(category)
        for split, pool, counts in (("dev", dev_pool, DEV_COUNTS), ("test", test_pool, TEST_COUNTS)):
            multi_symptom = [c for c in pool if len(c.symptoms) >= 2]
            assigned = allocate_causes(pool, counts[category])
            for i in range(counts[category]):
                cause = assigned[i]

                if i % 4 == 3:
                    difficulty = hard_types[hard_counts[split] % len(hard_types)]
                    hard_counts[split] += 1
                else:
                    difficulty = Difficulty.PLAIN
                if difficulty == Difficulty.MISLEADING_SYMPTOM:
                    if multi_symptom:
                        # Route to a cause that actually has a cross-category symptom,
                        # rather than leaving it to whatever pool[i % len(pool)] lands on.
                        cause = multi_symptom[i % len(multi_symptom)]
                    else:
                        # No cross-category symptom exists anywhere in this pool - fall
                        # back rather than fabricate a pairing that isn't grounded in anything.
                        difficulty = Difficulty.WORKING_AS_DESIGNED

                symptom = cause.symptoms[1] if difficulty == Difficulty.MISLEADING_SYMPTOM else cause.symptoms[0]

                deadline_pressure = list(DeadlinePressure)[i % len(DeadlinePressure)]
                if difficulty == Difficulty.MISSING_DECIDING_FACT:
                    deadline_pressure = DeadlinePressure.NOT_MENTIONED

                secondary_category = None
                if difficulty == Difficulty.MULTI_TOPIC:
                    idx = categories.index(category)
                    offset = 1 + (i // 4) % (len(categories) - 1)
                    secondary_category = categories[(idx + offset) % len(categories)]

                presented_as = list(Intent)[i % len(Intent)]
                if difficulty == Difficulty.WORKING_AS_DESIGNED:
                    # The prompt tells the writer the customer is reporting a bug; a
                    # rotated presented_as of question/feature_request would contradict it.
                    presented_as = Intent.BUG

                scenarios.append(
                    Scenario(
                        id=f"{split}-{category.value}-{i:03d}",
                        split=split,
                        symptom=symptom.text,
                        cause=cause.id,
                        primary_category=category,
                        documented=cause.symptoms[0].kb_file is not None,  # the cause's own status
                        kb_file=symptom.kb_file,  # still the chosen symptom's source
                        deadline_pressure=deadline_pressure,
                        workaround=bool(i % 2),
                        tone=list(Tone)[i % len(Tone)],
                        presented_as=presented_as,
                        difficulty=difficulty,
                        secondary_category=secondary_category,
                    )
                )
    return scenarios


SYSTEM_PROMPT = """You write realistic support tickets for {product_description}. You will \
be given a root cause and a set of situational details. Write the ticket a customer \
experiencing that situation would actually send in.

Write in the customer's voice, not a description of the situation:
- The customer does not know the internal root cause. Never restate it directly - describe \
only what they observed, using the symptom description you're given.
- Someone who believes something is broken writes a bug report even when the product behaved \
exactly as designed. Keep their framing and their mistaken assumptions if the situation calls \
for it - do not have them figure out or hint at the real explanation.
- Vary how much product vocabulary the customer uses and how much context they leave out, the \
way real, differently-technical people write tickets.
- Never mention or hint at internal generation concepts (category, priority, intent, \
difficulty, "scenario", "cause", deadline pressure as a labeled field, etc.) - those are not \
things a real customer would write.

Submit the ticket with the submit_ticket tool: a subject line and a body, exactly as the \
customer would type them.""".format(product_description=domain.load_product_description())


def render_prompt(scenario: Scenario) -> str:
    cause = CAUSES_BY_ID[scenario.cause]
    lines = [
        f"Root cause (internal, do not reveal): {cause.description}",
        f"How the customer would describe what they're seeing: {scenario.symptom}",
        "",
        f"How the customer is framing this request: {scenario.presented_as.value.replace('_', ' ')}",
        f"Customer's tone: {scenario.tone.value.replace('_', ' ')}",
    ]

    if scenario.tone == Tone.FRUSTRATED:
        lines.append("They're annoyed - this has cost them time or made them look bad.")
    elif scenario.tone == Tone.URGENT_STATED:
        lines.append("They explicitly say this is urgent or that they need a fast response.")
    elif scenario.tone == Tone.RELATIONSHIP_AT_RISK:
        lines.append(
            "They imply the relationship is at risk over this - evaluating alternatives, "
            "considering cancelling, or escalating to their own leadership."
        )

    if scenario.workaround:
        lines.append(
            "A manual workaround exists (e.g. doing the step by hand) and the customer could "
            "use it, though it's slower."
        )
    else:
        lines.append("No workaround exists - the customer is blocked until this is fixed.")

    lines.append(DEADLINE_PRESSURE_MESSAGING[scenario.deadline_pressure.value])

    if scenario.difficulty == Difficulty.MULTI_TOPIC and scenario.secondary_category:
        blurb = CATEGORY_DESCRIPTIONS[scenario.secondary_category]
        lines.append(
            f"This ticket should also raise a second, unrelated concern about {blurb}. Fold "
            "it into the same email as a customer would when they have two things on their "
            "mind, rather than writing two clearly separated topics."
        )
    elif scenario.difficulty == Difficulty.MISLEADING_SYMPTOM:
        lines.append(
            "Write this from the angle the symptom description above suggests - it reads like "
            "a different part of the product than what's actually going on. Do not have the "
            "customer correctly guess the real cause or area."
        )
    elif scenario.difficulty == Difficulty.WORKING_AS_DESIGNED:
        lines.append(
            "The customer believes this is a bug and is reporting it as one, even though the "
            "root cause above shows the product is behaving correctly. Write it fully from "
            "their mistaken point of view."
        )
    elif scenario.difficulty == Difficulty.CAUSE_UNDETERMINABLE:
        lines.append(
            "Describe this the way someone would when they have no diagnostic details to offer - "
            "no error message, no timestamp, no mention of what changed beforehand, no attempt to "
            "guess a cause. What they do say should still make the topic, urgency, and what they "
            "want clear; only the specific root cause should stay genuinely unrecoverable from the "
            "text."
        )

    return "\n".join(lines)


SUBMIT_TICKET_TOOL = {
    "name": "submit_ticket",
    "description": "Submit the generated support ticket text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "The ticket's subject line, as the customer would write it.",
            },
            "body": {
                "type": "string",
                "description": "The ticket's body text, as the customer would write it.",
            },
        },
        "required": ["subject", "body"],
        "additionalProperties": False,
    },
    "strict": True,
}


def generate_ticket(client: anthropic.Anthropic, scenario: Scenario) -> Ticket:
    # max_tokens caps thinking + output together on Sonnet 5 (thinking is on by default);
    # 1024 was tight enough that a long body could truncate before any tool_use block.
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        tools=[SUBMIT_TICKET_TOOL],
        tool_choice={"type": "tool", "name": "submit_ticket"},
        messages=[{"role": "user", "content": render_prompt(scenario)}],
    )
    if response.stop_reason != "tool_use":
        raise RuntimeError(f"stop_reason={response.stop_reason!r}, no tool call to read")
    block = next(b for b in response.content if b.type == "tool_use")
    return Ticket(id=scenario.id, subject=block.input["subject"], body=block.input["body"])


def load_existing_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open() as f:
        return {json.loads(line)["id"] for line in f if line.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=None, help="Generate at most N tickets (for testing)."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print scenario counts without calling the API."
    )
    args = parser.parse_args()

    scenarios = build_scenarios()
    dev_count = sum(1 for s in scenarios if s.split == "dev")
    test_count = sum(1 for s in scenarios if s.split == "test")
    print(f"Built {len(scenarios)} scenarios ({dev_count} dev, {test_count} test).")

    if args.dry_run:
        for split in ("dev", "test"):
            split_scenarios = [s for s in scenarios if s.split == split]
            per_cause = Counter(s.cause for s in split_scenarios)
            documented_n = sum(1 for s in split_scenarios if s.documented)
            reuse = sorted(per_cause.values())
            print(
                f"\n{split}: {len(split_scenarios)} tickets, {len(per_cause)} distinct causes, "
                f"{documented_n}/{len(split_scenarios)} documented "
                f"({documented_n / len(split_scenarios):.0%})"
            )
            print(
                f"  tickets per cause: min={reuse[0]}, max={reuse[-1]}, "
                f"avg={sum(reuse) / len(reuse):.1f}"
            )
        return

    DEV_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing_ids = load_existing_ids(DEV_PATH) | load_existing_ids(TEST_PATH)
    pending = [s for s in scenarios if s.id not in existing_ids]
    if args.limit is not None:
        pending = pending[: args.limit]
    print(f"{len(existing_ids)} tickets already generated; {len(pending)} to go.")

    load_dotenv()
    client = anthropic.Anthropic()

    with (
        DEV_PATH.open("a") as dev_f,
        TEST_PATH.open("a") as test_f,
        LOG_PATH.open("a") as log_f,
    ):
        for i, scenario in enumerate(pending, 1):
            try:
                ticket = generate_ticket(client, scenario)
            except Exception as exc:
                print(f"[{i}/{len(pending)}] {scenario.id}: FAILED ({exc}) - will retry on next run")
                continue
            # Log before the ticket: if a crash lands between the two writes, the
            # worst case is an orphaned log line (harmless, re-logged on retry since
            # existing_ids only checks the ticket files) rather than a ticket with no
            # provenance (permanent - resume would treat it as already done and skip it).
            log_f.write(json.dumps(asdict(scenario)) + "\n")
            log_f.flush()
            out = dev_f if scenario.split == "dev" else test_f
            out.write(json.dumps(asdict(ticket)) + "\n")
            out.flush()
            print(f"[{i}/{len(pending)}] {scenario.id}: {ticket.subject}")


if __name__ == "__main__":
    main()
