from __future__ import annotations

from src.plugins.registry import PluginRegistry
from src.plugins.techniques.ner import NERPlugin
from src.plugins.techniques.retrieval import RetrievalPlugin
from src.plugins.techniques.scoring import ScoringPlugin
from src.plugins.tools.calculator import CalculatorPlugin


def build_plugin_registry() -> PluginRegistry:
    """Create and populate the default plugin registry.
    This is an explicit composition function — no module-level side effects.
    """
    registry = PluginRegistry()
    registry.register(NERPlugin())
    registry.register(ScoringPlugin())
    registry.register(RetrievalPlugin())
    registry.register(CalculatorPlugin())
    return registry
