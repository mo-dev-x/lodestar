"""Judge implementations with lazy loading for the network-backed provider."""

from typing import TYPE_CHECKING, Any

from lodestar.judges.base import Judge
from lodestar.judges.cache import JudgeCache
from lodestar.judges.mock import MockJudge

if TYPE_CHECKING:
    from lodestar.judges.anthropic import AnthropicJudge


def __getattr__(name: str) -> Any:
    if name == "AnthropicJudge":
        from lodestar.judges.anthropic import AnthropicJudge

        return AnthropicJudge
    raise AttributeError(name)

__all__ = ["AnthropicJudge", "Judge", "JudgeCache", "MockJudge"]
