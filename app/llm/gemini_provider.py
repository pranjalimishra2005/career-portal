import json
import re
import asyncio
import warnings
from typing import Type, Optional

warnings.filterwarnings("ignore", category=FutureWarning)

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from pydantic import ValidationError

from app.core.config import settings
from app.llm.base import BaseLLMProvider, T


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini implementation of BaseLLMProvider.
    Includes adaptive rate-limit backoff handling for free tier (429 ResourceExhausted).
    """

    def __init__(self, model_name: str = "gemini-flash-latest", api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key or settings.GEMINI_API_KEY
        if self.api_key and self.api_key != "dummy_key_for_now":
            genai.configure(api_key=self.api_key)

    def _clean_json_markdown(self, text: str) -> str:
        """Strips markdown code fences (e.g. ```json ... ```) if returned."""
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text

    def _extract_retry_delay(self, error_message: str) -> int:
        """Parses Google's exact retry_delay from the error string, defaulting to 25s."""
        match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", error_message)
        if match:
            return int(match.group(1)) + 2  # add 2s buffer
        match_alt = re.search(r"retry in (\d+)", error_message)
        if match_alt:
            return int(match_alt.group(1)) + 2
        return 25

    async def _call_with_backoff(self, model, prompt_or_parts):
        """
        Executes generate_content_async with adaptive backoff
        matching Google's exact rate-limit window.
        """
        max_rate_retries = 3

        for attempt in range(max_rate_retries):
            try:
                return await model.generate_content_async(prompt_or_parts)
            except (google_exceptions.ResourceExhausted, google_exceptions.TooManyRequests) as e:
                if attempt == max_rate_retries - 1:
                    raise e
                wait_time = self._extract_retry_delay(str(e))
                print(f"\n[Gemini Rate Limit] Free tier quota reached. Waiting {wait_time}s for Google quota window to reset...")
                await asyncio.sleep(wait_time)

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        if not self.api_key or self.api_key == "dummy_key_for_now":
            raise ValueError("GEMINI_API_KEY is not set.")

        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_instruction,
            generation_config={"temperature": temperature}
        )
        response = await self._call_with_backoff(model, prompt)
        return response.text

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_retries: int = 2,
    ) -> T:
        if not self.api_key or self.api_key == "dummy_key_for_now":
            raise ValueError("GEMINI_API_KEY is not set.")

        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        base_instruction = (
            (system_instruction + "\n\n" if system_instruction else "")
            + f"You MUST reply with a single valid JSON object strictly matching this JSON Schema:\n{schema_json}\n"
            + "Do not include markdown ticks, conversational preamble, or explanations. Output the raw JSON string only."
        )

        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=base_instruction,
            generation_config={"temperature": temperature}
        )

        current_prompt = prompt
        last_error = ""

        for attempt in range(max_retries + 1):
            if attempt > 0:
                current_prompt = (
                    f"{prompt}\n\n"
                    f"CRITICAL: Your previous response was invalid. Error details:\n{last_error}\n"
                    f"Please correct the JSON output according to the schema."
                )

            response = await self._call_with_backoff(model, current_prompt)
            raw_text = self._clean_json_markdown(response.text)

            try:
                return response_model.model_validate_json(raw_text)
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = str(e)
            

        raise ValueError(
            f"Failed to generate valid {response_model.__name__} after {max_retries + 1} attempts. "
            f"Last error: {last_error}"
        )