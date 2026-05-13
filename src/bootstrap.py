"""Composition root: builds the composed NodeRegistry from base + plugin nodes.

This module is the single point where concrete plugins are instantiated.
Importing it triggers plugin construction — only the bootstrap or top-level
entrypoint should import it.
"""

from __future__ import annotations

from src.handlers import NODE_REGISTRY as _BASE_REGISTRY
from src.nodes.base import NodeRegistry
from src.nodes.plugin_node import PluginNode
from src.plugins.manifest import build_plugin_registry


def _build_default_registry() -> NodeRegistry:
    """Base handlers nodes + plugin-backed nodes."""
    plugin_registry = build_plugin_registry()
    plugin_nodes = [
        PluginNode("ner.default", plugin_registry),
        PluginNode("scoring.default", plugin_registry),
        PluginNode("retrieval.default", plugin_registry),
        PluginNode("tool.calculator", plugin_registry),
    ]
    return NodeRegistry([*_BASE_REGISTRY.all(), *plugin_nodes])


DEFAULT_REGISTRY: NodeRegistry = _build_default_registry()
