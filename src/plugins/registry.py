from __future__ import annotations

from src.plugins.contracts import Plugin


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        if plugin.spec.name in self._plugins:
            raise ValueError(f"Duplicate plugin registration: {plugin.spec.name!r}")
        self._plugins[plugin.spec.name] = plugin

    def resolve(self, name: str) -> Plugin:
        plugin = self._plugins.get(name)
        if plugin is None:
            raise KeyError(f"Unknown plugin: {name!r}. Registered: {sorted(self._plugins)}")
        return plugin

    @property
    def registered_names(self) -> list[str]:
        return sorted(self._plugins)

    @property
    def registered_count(self) -> int:
        return len(self._plugins)

    def items(self) -> dict[str, Plugin]:
        return dict(self._plugins)
