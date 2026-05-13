from __future__ import annotations

from src.plugins.contracts import PluginInput, PluginOutput, PluginSpec


class CalculatorPlugin:
    spec = PluginSpec(
        name="tool.calculator",
        kind="tool",
        version="1.0.0",
        description="Evaluate arithmetic expressions safely",
    )

    def execute(self, input: PluginInput) -> PluginOutput:
        from src.tools.calculator import Calculator as _Calculator

        expression = input.data.get("text", "")
        calc = _Calculator()
        result = calc.execute({"expression": expression})
        return PluginOutput(data={"result": result})
