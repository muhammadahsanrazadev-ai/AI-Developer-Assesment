import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol

import openai
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class AgentOutputError(ValueError):
    """Raised by an agent's post-validation when parsed output breaks a business rule."""


@dataclass
class LLMResponse:
    content: str
    tokens_used: int


class LLMClient(Protocol):
    def complete(self, system_prompt: str, user_message: str, temperature: float) -> LLMResponse: ...


class LLMClientError(Exception):
    pass


class OpenAIClient:
    def __init__(self, api_key: str, model: str, timeout: float = 60.0, max_retries: int = 2):
        if not api_key:
            raise LLMClientError("OPENAI_API_KEY is not configured.")
        self.model = model
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)

    def complete(self, system_prompt: str, user_message: str, temperature: float) -> LLMResponse:
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
            )
        except openai.OpenAIError as exc:
            raise LLMClientError(f"{type(exc).__name__}: {exc}") from exc

        tokens = response.usage.total_tokens if response.usage else 0
        content = response.choices[0].message.content if response.choices else None
        return LLMResponse(content=content or "", tokens_used=tokens)


@dataclass
class AgentResult:
    ok: bool
    data: Any = None
    error: str | None = None
    tokens_used: int = 0
    attempts: int = 0


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_json(content: str) -> Any:
    text = _FENCE_RE.sub("", content.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


class BaseAgent(ABC):
    name: str = "agent"
    system_prompt: str = ""
    output_model: type[BaseModel]
    temperature: float = 0.2

    def __init__(self, llm_client: LLMClient, max_retries: int = 1):
        self.llm = llm_client
        self.max_retries = max_retries

    @abstractmethod
    def build_user_message(self, **inputs: Any) -> str: ...

    def post_validate(self, output: BaseModel, **inputs: Any) -> Any:
        return output

    def run(self, **inputs: Any) -> AgentResult:
        user_message = self.build_user_message(**inputs)
        tokens_used = 0
        last_error = "no attempt made"

        for attempt in range(1, self.max_retries + 2):
            try:
                response = self.llm.complete(self.system_prompt, user_message, self.temperature)
            except LLMClientError as exc:
                logger.warning("%s: LLM call failed: %s", self.name, exc)
                return AgentResult(ok=False, error=f"LLM call failed: {exc}",
                                   tokens_used=tokens_used, attempts=attempt)
            tokens_used += response.tokens_used

            try:
                parsed = extract_json(response.content)
                output = self.output_model.model_validate(parsed)
                data = self.post_validate(output, **inputs)
                return AgentResult(ok=True, data=data, tokens_used=tokens_used, attempts=attempt)
            except json.JSONDecodeError as exc:
                last_error = f"Response was not valid JSON ({exc.msg})."
            except ValidationError as exc:
                last_error = f"Response did not match the schema: {_summarise(exc)}"
            except AgentOutputError as exc:
                last_error = f"Response broke a rule: {exc}"

            logger.warning("%s: attempt %d invalid: %s", self.name, attempt, last_error)
            user_message = (
                f"{self.build_user_message(**inputs)}\n\n"
                f"Your previous response was rejected. {last_error} "
                "Return ONLY a JSON object that follows the schema exactly."
            )

        return AgentResult(ok=False, error=last_error, tokens_used=tokens_used,
                           attempts=self.max_retries + 1)


def _summarise(exc: ValidationError, limit: int = 3) -> str:
    parts = []
    for err in exc.errors()[:limit]:
        location = ".".join(str(p) for p in err["loc"]) or "root"
        parts.append(f"{location}: {err['msg']}")
    return "; ".join(parts)


def normalise_domain(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"^[a-z]+://", "", value)
    value = value.split("/")[0].split("?")[0]
    return value.removeprefix("www.")
