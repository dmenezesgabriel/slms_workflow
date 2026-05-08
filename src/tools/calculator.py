from __future__ import annotations

import ast
import math
import operator
import re
from typing import Any, Callable

from src.tools.base import ToolBase

_OpFn = Callable[..., int | float]

_BIN_OPS: dict[type[ast.operator], _OpFn] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS: dict[type[ast.unaryop], _OpFn] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_MATH_FNS: dict[str, Callable[[float], float]] = {
    "sqrt": math.sqrt,
    "abs": abs,
    "ceil": math.ceil,
    "floor": math.floor,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
}

_TRAILING_RESULT = re.compile(r"\s*=\s*[\d.]+\s*$")


def _eval_node(node: ast.AST) -> int | float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        bin_op = type(node.op)
        if bin_op not in _BIN_OPS:
            raise ValueError(f"Operator not allowed: {bin_op.__name__}")
        return _BIN_OPS[bin_op](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        unary_op = type(node.op)
        if unary_op not in _UNARY_OPS:
            raise ValueError(f"Operator not allowed: {unary_op.__name__}")
        return _UNARY_OPS[unary_op](_eval_node(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _MATH_FNS:
            raise ValueError(f"Function not allowed: {ast.unparse(node.func)}")
        if len(node.args) != 1 or node.keywords:
            raise ValueError("Math functions take exactly one argument")
        return _MATH_FNS[node.func.id](float(_eval_node(node.args[0])))
    raise ValueError(f"Expression not allowed: {type(node).__name__}")


class Calculator(ToolBase):
    name = "calculator"
    description = "Evaluates a Python arithmetic expression safely"
    parameters: dict[str, str] = {"expression": "Python arithmetic string, e.g. '3 + 4 * 2'"}

    def execute(self, arguments: dict[str, Any]) -> str:
        expression = arguments.get("expression")
        if not isinstance(expression, str):
            raise ValueError("arguments.expression must be a string")
        expression = _TRAILING_RESULT.sub("", expression).strip()
        result = _eval_node(ast.parse(expression, mode="eval"))
        return str(int(result) if isinstance(result, float) and result.is_integer() else result)
