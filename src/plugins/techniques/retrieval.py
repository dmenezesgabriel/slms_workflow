from __future__ import annotations

from src.plugins.contracts import PluginInput, PluginOutput, PluginSpec


class RetrievalPlugin:
    spec = PluginSpec(
        name="retrieval.default",
        kind="technique",
        version="1.0.0",
        description="Retrieve web context for grounding answers",
    )

    _retriever = None

    def execute(self, input: PluginInput) -> PluginOutput:
        if self._retriever is None:
            from src.retrievers.default import create_default_retriever

            self._retriever = create_default_retriever()
        text = input.data.get("text", "")
        context = self._retriever.fetch_context(text)
        return PluginOutput(data={"result": context, "length": len(context)})
