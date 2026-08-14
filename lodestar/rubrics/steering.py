"""The canonical steering rubric suite."""

from lodestar.models import BinaryScale, CategoricalScale, OrdinalScale, Rubric

PREAMBLE = """You are a rigorous evaluator for a mechanistic-interpretability experiment on
LLM activation steering. You will score ONE piece of model-generated text on a
SINGLE dimension. Judge only what is asked. Be strict and calibrated.
"""

COHERENCE = Rubric(
    name="coherence",
    version="1.0",
    description="Grammatical fluency and readability, independent of topic.",
    scale=OrdinalScale(minimum=1, maximum=10),
    prompt_template=PREAMBLE
    + """
DIMENSION: Coherence (grammatical fluency and readability)
- 10: flawless, fluent, natural prose.
- 7-9: minor awkwardness; fully readable.
- 4-6: degraded grammar or mild repetition; meaning still recoverable.
- 2-3: heavy repetition, broken syntax, or fragmentary.
- 1: gibberish / repeated tokens / no recoverable meaning.
IMPORTANT: Judge coherence ONLY. A perfectly fluent off-topic text scores high.
Do NOT reward or penalize topic.

TEXT TO EVALUATE:
\"\"\"{{ generation.text }}\"\"\"

Respond with JSON only, no preamble:
{\"score\": <int 1-10>, \"rationale\": \"<=20 words\"}
""",
    output_schema={
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 1, "maximum": 10},
            "rationale": {"type": "string"},
        },
        "required": ["score", "rationale"],
        "additionalProperties": False,
    },
)

CONCEPT_RELEVANCE = Rubric(
    name="concept_relevance",
    version="1.0",
    description="How centrally and specifically the output expresses the target concept.",
    scale=OrdinalScale(minimum=1, maximum=10),
    prompt_template=PREAMBLE
    + """
DIMENSION: Concept relevance to \"{{ target_concept }}\"
- 10: centrally about {{ target_concept }} with accurate specifics.
- 7-9: clearly about {{ target_concept }} or its defining attributes.
- 4-6: related domain but not {{ target_concept }} specifically.
- 2-3: only tangential association.
- 1: unrelated.
Score relevance ONLY; ignore grammar/fluency.
TEXT: \"\"\"{{ generation.text }}\"\"\"
Respond with JSON only:
{\"score\": <int 1-10>, \"rationale\": \"<=20 words\"}
""",
    output_schema={
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 1, "maximum": 10},
            "rationale": {"type": "string"},
        },
        "required": ["score", "rationale"],
        "additionalProperties": False,
    },
)

LITERAL_MENTION = Rubric(
    name="literal_mention",
    version="1.0",
    description="Literal occurrence of the target concept or an explicitly supplied alias.",
    scale=BinaryScale(),
    aliases=(),
    deterministic=True,
    prompt_template=PREAMBLE
    + """
DIMENSION: Literal mention
TARGET: \"{{ target_concept }}\"
ALIASES: {{ aliases }}
Determine whether the target or an alias occurs literally, case-insensitively.
TEXT: \"\"\"{{ generation.text }}\"\"\"
Respond with JSON only:
{\"score\": <true or false>, \"count\": <non-negative integer>, \"rationale\": \"<=20 words\"}
""",
    output_schema={
        "type": "object",
        "properties": {
            "score": {"type": "boolean"},
            "count": {"type": "integer", "minimum": 0},
            "rationale": {"type": "string"},
        },
        "required": ["score", "count", "rationale"],
        "additionalProperties": False,
    },
)

PROMPT_ADHERENCE = Rubric(
    name="prompt_adherence",
    version="1.0",
    description="How fully the output continues to answer the original prompt.",
    scale=OrdinalScale(minimum=1, maximum=10),
    prompt_template=PREAMBLE
    + """
DIMENSION: Adherence to the original prompt
- 10: directly and completely answers the prompt.
- 7-9: mostly answers it with minor drift.
- 4-6: partially answers it; substantial drift.
- 2-3: weak connection to the prompt.
- 1: entirely abandons or contradicts the prompt.
Judge prompt adherence only; concept relevance is a separate dimension.
ORIGINAL PROMPT: \"\"\"{{ generation.prompt }}\"\"\"
OUTPUT: \"\"\"{{ generation.text }}\"\"\"
Respond with JSON only:
{\"score\": <int 1-10>, \"rationale\": \"<=20 words\"}
""",
    output_schema={
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 1, "maximum": 10},
            "rationale": {"type": "string"},
        },
        "required": ["score", "rationale"],
        "additionalProperties": False,
    },
)

INTEGRATION_NATURALNESS = Rubric(
    name="integration_naturalness",
    version="1.0",
    description="Whether the target concept is integrated naturally rather than bolted on.",
    scale=OrdinalScale(minimum=1, maximum=10),
    prompt_template=PREAMBLE
    + """
DIMENSION: Natural integration of \"{{ target_concept }}\"
- 10: concept is woven in seamlessly and contextually.
- 7-9: natural with only slight forcing.
- 4-6: noticeable insertion or awkward transition.
- 2-3: bolted on, list-like, or strongly forced.
- 1: incoherent insertion or word salad.
If the concept is absent, score 1. Judge integration, not raw relevance.
ORIGINAL PROMPT: \"\"\"{{ generation.prompt }}\"\"\"
OUTPUT: \"\"\"{{ generation.text }}\"\"\"
Respond with JSON only:
{\"score\": <int 1-10>, \"rationale\": \"<=20 words\"}
""",
    output_schema={
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 1, "maximum": 10},
            "rationale": {"type": "string"},
        },
        "required": ["score", "rationale"],
        "additionalProperties": False,
    },
)

DEGENERATION_FLAGS = Rubric(
    name="degeneration_flags",
    version="1.0",
    description="Observable steering failure modes; multiple flags may apply.",
    scale=CategoricalScale(
        categories=("repetition_loop", "topic_salad", "language_drift", "gibberish", "none"),
        multiple=True,
    ),
    prompt_template=PREAMBLE
    + """
DIMENSION: Degeneration failure modes
Select every observable flag:
- repetition_loop: phrase/token cycling or excessive repetition
- topic_salad: rapid, incoherent jumps among loosely associated topics
- language_drift: output switches away from language {{ generation.language }}
- gibberish: no recoverable meaning or severely corrupted syntax
- none: no listed failure mode (must appear alone)
TEXT: \"\"\"{{ generation.text }}\"\"\"
Respond with JSON only:
{\"score\": [<flags>], \"rationale\": \"<=20 words\"}
""",
    output_schema={
        "type": "object",
        "properties": {
            "score": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "repetition_loop",
                        "topic_salad",
                        "language_drift",
                        "gibberish",
                        "none",
                    ],
                },
                "minItems": 1,
                "uniqueItems": True,
            },
            "rationale": {"type": "string"},
        },
        "required": ["score", "rationale"],
        "additionalProperties": False,
    },
)

STEERING_RUBRICS = (
    COHERENCE,
    CONCEPT_RELEVANCE,
    LITERAL_MENTION,
    PROMPT_ADHERENCE,
    INTEGRATION_NATURALNESS,
    DEGENERATION_FLAGS,
)

