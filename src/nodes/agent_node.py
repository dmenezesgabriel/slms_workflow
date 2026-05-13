from __future__ import annotations

from pydantic import BaseModel

from src.llm_client import LLMClient


class AgentNode:
    id = "agent"

    def execute(self, input: str, llm: LLMClient) -> BaseModel:
        from src.agent import run_agent

        return run_agent(input, llm)
