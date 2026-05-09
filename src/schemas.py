from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

IntentName = Literal[
    "summarization",
    "question_answering",
    "function_calling",
    "classification",
    "image_understanding",
    "general",
    "unclassified",
]

ToolName = Literal[
    "none",
    "calculator",
    "web_search",
    "web_fetch",
    "wikipedia",
    "playwright",
    "duckdb",
]


class IntentClassification(BaseModel):
    intent: IntentName
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: Any) -> float:
        confidence = float(value)

        if confidence > 1.0 and confidence <= 100.0:
            return confidence / 100.0

        return confidence


class SummaryResult(BaseModel):
    title: str
    summary: str
    key_points: list[str]


class ToolDecision(BaseModel):
    needs_tool: bool
    # Constrained to the stable tool interface while still forcing constrained
    # JSON generation to emit a value. Use "none" when no tool is needed.
    tool_name: ToolName = "none"
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str


class FinalAnswer(BaseModel):
    answer: str


class ClassificationResult(BaseModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: Any) -> float:
        confidence = float(value)

        if confidence > 1.0 and confidence <= 100.0:
            return confidence / 100.0

        return confidence


class ImageDescription(BaseModel):
    description: str
    visible_objects: list[str] = Field(default_factory=list)
    visible_text: list[str] = Field(default_factory=list)


class AgentStep(BaseModel):
    thought: str
    action: Literal[
        "web_search",
        "web_fetch",
        "wikipedia",
        "calculator",
        "summarize",
        "classify",
        "answer",
        "final_answer",
    ]
    action_input: str
    is_final: bool
