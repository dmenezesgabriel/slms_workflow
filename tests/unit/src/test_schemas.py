from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import ValidationError

from src.schemas import ToolDecision


def test_tool_decision_rejects_unknown_tool_name() -> None:
    with pytest.raises(ValidationError):
        ToolDecision(
            needs_tool=True,
            tool_name=cast(Any, "unknown"),
            arguments={},
            reason="invalid",
        )
