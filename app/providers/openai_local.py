from __future__ import annotations

import json
from typing import Any, TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from app.llm_client import LLMRequest, LLMResponse

T = TypeVar("T", bound=BaseModel)


class OpenAILocalClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080/v1",
        api_key: str = "sk-local",
        timeout: float = 120.0,
    ) -> None:
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        if request.tools is not None:
            kwargs["tools"] = request.tools

        response = self.client.chat.completions.create(**kwargs)

        message = response.choices[0].message

        return LLMResponse(
            text=message.content or "",
            raw=response,
        )

    def structured(
        self,
        request: LLMRequest,
        schema: type[T],
        retries: int = 1,
    ) -> T:
        json_schema = schema.model_json_schema()
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            messages = [
                {
                    "role": "system",
                    "content": (
                        request.system
                        + "\nReturn only valid JSON matching the provided schema. "
                        + "Do not wrap the JSON in markdown. "
                        + "Do not include explanations outside the JSON."
                    ),
                },
                {"role": "user", "content": request.user},
            ]

            if attempt > 0 and last_error is not None:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your previous answer failed validation. "
                            f"Validation error: {last_error}. "
                            "Return corrected JSON only."
                        ),
                    }
                )

            response = self.client.chat.completions.create(
                model=request.model,
                messages=messages,
                temperature=0.0,
                max_tokens=request.max_tokens,
                response_format={
                    "type": "json_object",
                    "schema": json_schema,
                },
                extra_body={
                    "seed": 42,
                },
            )

            content = response.choices[0].message.content or ""

            try:
                data = json.loads(content)
                return schema.model_validate(data)
            except (json.JSONDecodeError, ValidationError) as error:
                last_error = error

        raise RuntimeError(f"Failed to produce valid {schema.__name__}: {last_error}")