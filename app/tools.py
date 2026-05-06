from __future__ import annotations

import ast
import operator
from dataclasses import dataclass
from typing import Any

from app.schemas import ToolDecision


@dataclass(frozen=True)
class ToolExecutionResult:
    success: bool
    tool_name: str
    result: str
    error: str | None = None


_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval_math_node(node: ast.AST) -> int | float:
    if isinstance(node, ast.Expression):
        return _safe_eval_math_node(node.body)

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value

    if isinstance(node, ast.BinOp):
        operator_type = type(node.op)

        if operator_type not in _ALLOWED_OPERATORS:
            raise ValueError(f"Operator not allowed: {operator_type.__name__}")

        left = _safe_eval_math_node(node.left)
        right = _safe_eval_math_node(node.right)

        return _ALLOWED_OPERATORS[operator_type](left, right)

    if isinstance(node, ast.UnaryOp):
        operator_type = type(node.op)

        if operator_type not in _ALLOWED_OPERATORS:
            raise ValueError(f"Operator not allowed: {operator_type.__name__}")

        operand = _safe_eval_math_node(node.operand)

        return _ALLOWED_OPERATORS[operator_type](operand)

    raise ValueError(f"Expression not allowed: {type(node).__name__}")


def calculator(expression: str) -> str:
    parsed = ast.parse(expression, mode="eval")
    result = _safe_eval_math_node(parsed)
    return str(result)


def execute_tool_decision(decision: ToolDecision) -> ToolExecutionResult:
    if not decision.needs_tool:
        return ToolExecutionResult(
            success=False,
            tool_name="none",
            result="No tool was needed.",
            error=None,
        )

    if decision.tool_name != "calculator":
        return ToolExecutionResult(
            success=False,
            tool_name=decision.tool_name or "unknown",
            result="",
            error=f"Unsupported tool: {decision.tool_name}",
        )

    expression = decision.arguments.get("expression")

    if not isinstance(expression, str):
        return ToolExecutionResult(
            success=False,
            tool_name="calculator",
            result="",
            error="Calculator requires arguments.expression as a string.",
        )

    try:
        result = calculator(expression)
        return ToolExecutionResult(
            success=True,
            tool_name="calculator",
            result=result,
            error=None,
        )
    except Exception as error:
        return ToolExecutionResult(
            success=False,
            tool_name="calculator",
            result="",
            error=str(error),
        )