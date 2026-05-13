from __future__ import annotations

from src.plugins.contracts import PluginInput, PluginOutput, PluginSpec
from src.techniques import ner as _ner


class NERPlugin:
    spec = PluginSpec(
        name="ner.default",
        kind="technique",
        version="1.0.0",
        description="Named entity recognition using spaCy",
    )

    def execute(self, input: PluginInput) -> PluginOutput:
        text = input.data["text"]
        entities = _ner.extract(text)
        labels = ", ".join(f"{e.text}({e.label})" for e in entities)
        return PluginOutput(
            data={"result": labels or "no entities found", "entity_count": len(entities)}
        )
