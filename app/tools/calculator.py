from __future__ import annotations

import ast
import operator
from typing import Any, Callable

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
    raise ValueError(f"Expression not allowed: {type(node).__name__}")


def run(arguments: dict[str, Any]) -> str:
    expression = arguments.get("expression")
    if not isinstance(expression, str):
        raise ValueError("arguments.expression must be a string")
    return str(_eval_node(ast.parse(expression, mode="eval")))
