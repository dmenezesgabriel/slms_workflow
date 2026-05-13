from __future__ import annotations

from src.plugins.contracts import PluginInput, PluginOutput, PluginSpec
from src.techniques.scoring import score_result as _score


class ScoringPlugin:
    spec = PluginSpec(
        name="scoring.default",
        kind="technique",
        version="1.0.0",
        description="Score the quality of a text result",
    )

    def execute(self, input: PluginInput) -> PluginOutput:
        text = input.data["text"]
        score = _score(text)
        return PluginOutput(
            data={
                "result": (
                    f"quality={score.quality:.2f} "
                    f"usable={score.is_usable} reason={score.reason}"
                ),
                "quality": score.quality,
                "is_usable": score.is_usable,
                "reason": score.reason,
            }
        )
