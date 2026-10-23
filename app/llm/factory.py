from app.core.config import settings
from app.llm.base import BaseLLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.groq_provider import GroqProvider


def get_llm_provider(provider_name: str = None) -> BaseLLMProvider:
    """
    Factory returning the active provider based on DEFAULT_LLM_PROVIDER in .env.
    Supports 'groq' and 'gemini' seamlessly.
    """
    active_provider = provider_name or settings.DEFAULT_LLM_PROVIDER

    if active_provider == "groq":
        return GroqProvider()
    elif active_provider == "gemini":
        return GeminiProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {active_provider}")