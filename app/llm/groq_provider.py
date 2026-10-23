import json
import re
import asyncio
from typing import Type, Optional, List
from groq import AsyncGroq, RateLimitError
from pydantic import ValidationError

from app.core.config import settings
from app.llm.base import BaseLLMProvider, T

FALLBACK_MODELS = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "openai/gpt-oss-120b"]


class GroqProvider(BaseLLMProvider):
    """
    Groq implementation of BaseLLMProvider with multi-model fallback.
    Tries 'openai/gpt-oss-20b', 'qwen/qwen3.8-27b', and 'openai/gpt-oss-120b'
    to seamlessly handle rate limits (TPD / TPM) on the free tier.
    """

    def __init__(self, model_name: str = "openai/gpt-oss-20b", api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key or settings.GROQ_API_KEY
        self.client = None
        if self.api_key and self.api_key != "dummy_key_for_now":
            self.client = AsyncGroq(api_key=self.api_key)

    def _clean_json_markdown(self, text: str) -> str:
        """Strips markdown code fences (e.g. ```json ... ```) if returned."""
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text

    def _extract_retry_delay(self, error_message: str) -> float:
        """Parses Groq's exact retry_delay from the error string, e.g. '1m55.776s' or '2.15s'."""
        min_sec_match = re.search(r"try again in (\d+)m(\d+(?:\.\d+)?)s", error_message)
        if min_sec_match:
            minutes = float(min_sec_match.group(1))
            seconds = float(min_sec_match.group(2))
            return (minutes * 60) + seconds + 1.0

        sec_match = re.search(r"try again in (\d+(?:\.\d+)?)s", error_message)
        if sec_match:
            return float(sec_match.group(1)) + 1.0

        return 3.0

    async def _call_with_backoff(self, **create_kwargs):
        """
        Executes a Groq chat completion with adaptive fallback across available models.
        If a model is rate-limited (e.g. daily TPD reached), immediately switches to the next model.
        """
        models_to_try = [self.model_name] + [m for m in FALLBACK_MODELS if m != self.model_name]
        last_exception = None

        for idx, model in enumerate(models_to_try):
            create_kwargs["model"] = model
            try:
                return await self.client.chat.completions.create(**create_kwargs)
            except RateLimitError as e:
                last_exception = e
                err_str = str(e).lower()
                wait_time = self._extract_retry_delay(str(e))

                # If daily quota (TPD) was exhausted or wait time is long (> 8s), immediately try next model
                if "tpd" in err_str or "tokens per day" in err_str or wait_time > 8.0:
                    print(f"[GroqProvider] Rate limit on {model}. Rotating to fallback model...")
                    continue

                # Short rate limit (e.g. burst TPM), sleep and retry once
                await asyncio.sleep(min(wait_time, 4.0))
                try:
                    return await self.client.chat.completions.create(**create_kwargs)
                except RateLimitError as e2:
                    last_exception = e2
                    continue
            except Exception as e:
                last_exception = e
                if idx < len(models_to_try) - 1:
                    continue
                raise e

        if last_exception:
            raise last_exception

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        if not self.client:
            raise ValueError("GROQ_API_KEY is not set in .env.")

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        response = await self._call_with_backoff(
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_retries: int = 2,
    ) -> T:
        if not self.client:
            raise ValueError("GROQ_API_KEY is not set in .env.")

        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        sys_msg_prefix = f"{system_instruction}\n\n" if system_instruction else ""
        sys_msg = (
            f"{sys_msg_prefix}"
            f"You MUST reply with a single valid JSON object strictly matching this JSON Schema:\n"
            f"{schema_json}\n\n"
            f"Output raw valid JSON only. Do not wrap in markdown or add conversational preamble."
        )

        current_prompt = prompt
        last_error = ""

        for attempt in range(max_retries + 1):
            if attempt > 0:
                current_prompt = (
                    f"{prompt}\n\n"
                    f"CRITICAL: Your previous response was invalid. Error details:\n"
                    f"{last_error}\n\n"
                    f"Please output strictly conforming JSON."
                )

            messages = [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": current_prompt}
            ]

            response = await self._call_with_backoff(
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"}
            )

            raw_text = self._clean_json_markdown(response.choices[0].message.content)

            try:
                return response_model.model_validate_json(raw_text)
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = str(e)

        raise ValueError(
            f"Failed to generate valid {response_model.__name__} after {max_retries + 1} attempts. Last error: {last_error}"
        )
