from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from lodestar.judges.anthropic import _UNSUPPORTED_SCHEMA_KEYWORDS, AnthropicJudge, _sanitize_schema
from lodestar.models import EvalRun, RunManifest
from lodestar.report.html import _drilldown
from lodestar.rubrics import get_rubric
from lodestar.rubrics.steering import STEERING_RUBRICS
from lodestar.validation.consistency import consistency_report


class FakeMessages:
    def __init__(self, texts: list[str]) -> None:
        self.texts = iter(texts)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=next(self.texts))],
            usage=SimpleNamespace(input_tokens=10, output_tokens=4),
        )


class FakeClient:
    def __init__(self, texts: list[str]) -> None:
        self.messages = FakeMessages(texts)


@pytest.mark.asyncio
async def test_invalid_json_gets_one_repair(sample_generations) -> None:
    client = FakeClient(["not json", '{"score": 8, "rationale": "Readable."}'])
    judge = AnthropicJudge("claude-test", client=client)
    result = await judge.judge_one(sample_generations[0], get_rubric("coherence"))
    assert result.score == 8
    assert result.metadata["repair_attempted"]
    assert result.usage.input_tokens == 20
    assert len(client.messages.calls) == 2
    assert "output_config" in client.messages.calls[0]


@pytest.mark.asyncio
async def test_second_parse_failure_is_recorded(sample_generations) -> None:
    client = FakeClient(["bad", "still bad"])
    judge = AnthropicJudge("claude-test", client=client)
    result = await judge.judge_one(sample_generations[0], get_rubric("coherence"))
    assert result.score is None
    assert result.metadata["degeneration"] == "parse_failure"


@pytest.mark.asyncio
async def test_literal_score_uses_grep_and_keeps_crosscheck(sample_generations) -> None:
    client = FakeClient(['{"score": false, "count": 0, "rationale": "No mention."}'])
    judge = AnthropicJudge("claude-test", client=client)
    result = await judge.judge_one(sample_generations[1], get_rubric("literal_mention"))
    assert result.score is True
    assert result.metadata["judge_grep_disagreement"] is True


@pytest.mark.asyncio
async def test_deterministic_path_honors_flag_not_name(sample_generations) -> None:
    # INV-DETTYPE / F7: the deterministic path MUST be driven by
    # Rubric.deterministic, not a hardcoded rubric.name literal. A rubric
    # renamed away from "literal_mention" but still declaring
    # deterministic=True must receive the same grep-based deterministic path.
    renamed = get_rubric("literal_mention").model_copy(update={"name": "custom_literal_check"})
    assert renamed.deterministic is True
    client = FakeClient(['{"score": false, "count": 0, "rationale": "No mention."}'])
    judge = AnthropicJudge("claude-test", client=client)
    result = await judge.judge_one(sample_generations[1], renamed)
    assert result.score is True
    assert result.metadata["judge_grep_disagreement"] is True


@pytest.mark.asyncio
async def test_grep_disagreement_reaches_drilldown_and_reliability_table(sample_generations) -> None:
    """The judge/grep crosscheck (ARCHITECTURE.md §4) must be reportable, not just computed."""
    client = FakeClient(['{"score": false, "count": 0, "rationale": "No mention."}'])
    judge = AnthropicJudge("claude-test", client=client)
    rubric = get_rubric("literal_mention")
    generation = sample_generations[1]
    judgment = await judge.judge_one(generation, rubric)
    now = datetime.now(UTC)
    run = EvalRun(
        generations=[generation],
        judgments=[judgment],
        rubrics=[rubric],
        judge_model=judge.model_name,
        n_repeats=1,
        manifest=RunManifest(tool_version="test", started_at=now, finished_at=now),
    )

    table = _drilldown(run)
    row = table.set_index("id").loc[generation.id]
    assert row["literal_mention_count"] == 1
    assert bool(row["literal_mention_judge_grep_disagreement"]) is True

    reliability = consistency_report(run).reliability
    literal_row = reliability[reliability["rubric"] == "literal_mention"].iloc[0]
    assert literal_row["judge_grep_disagreement_rate"] == pytest.approx(1.0)


def _find_unsupported_keywords(node: object, path: str = "schema") -> list[tuple[str, str]]:
    """Recursively collect (path, keyword) pairs Anthropic's structured-output API rejects."""
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for keyword in (*_UNSUPPORTED_SCHEMA_KEYWORDS, "uniqueItems"):
            if keyword in node:
                found.append((path, keyword))
        if node.get("minItems") not in (None, 0, 1):
            found.append((path, "minItems"))
        for key, value in node.items():
            found.extend(_find_unsupported_keywords(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            found.extend(_find_unsupported_keywords(item, f"{path}[{index}]"))
    return found


def test_sanitize_schema_strips_keywords_anthropic_rejects_and_keeps_the_hint() -> None:
    """Anthropic's API 400s on raw (non-Pydantic-derived) schemas containing minimum/maximum/
    uniqueItems/etc -- verified live against platform.claude.com on 2026-06-23. The SDK only
    auto-strips these for schemas derived from a native type via messages.parse(); our rubrics
    hand-author plain dicts, so we must strip them ourselves before sending output_config."""
    schema = {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 1, "maximum": 10},
            "tags": {"type": "array", "items": {"type": "string"}, "uniqueItems": True, "minItems": 1},
            "note": {"type": "string", "minLength": 1, "maxLength": 500},
        },
        "additionalProperties": False,
    }
    sanitized = _sanitize_schema(schema)
    assert not _find_unsupported_keywords(sanitized)
    assert "1" in sanitized["properties"]["score"]["description"]
    assert "10" in sanitized["properties"]["score"]["description"]
    assert "unique" in sanitized["properties"]["tags"]["description"]
    assert sanitized["properties"]["tags"]["minItems"] == 1


def test_every_steering_rubric_schema_is_structured_output_api_compatible() -> None:
    for rubric in STEERING_RUBRICS:
        sanitized = _sanitize_schema(rubric.output_schema)
        assert not _find_unsupported_keywords(sanitized), rubric.name


@pytest.mark.asyncio
async def test_request_sends_the_sanitized_not_raw_schema(sample_generations) -> None:
    client = FakeClient(['{"score": 8, "rationale": "Readable."}'])
    judge = AnthropicJudge("claude-test", client=client)
    await judge.judge_one(sample_generations[0], get_rubric("coherence"))
    sent_schema = client.messages.calls[0]["output_config"]["format"]["schema"]
    assert not _find_unsupported_keywords(sent_schema)

