from app.core.config import settings
from app.llm.base import BaseLLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.groq_provider import GroqProvider


def get_llm_provider(provider_name: str = None) -> BaseLLMProvider:
    """
    Factory returning the active provider based on DEFAULT_LLM_PROVIDER in .env.
    Automatically selects whichever provider has a valid active API key configured.
    """
    active_provider = provider_name or settings.DEFAULT_LLM_PROVIDER

    # Smart fallback: if requested provider lacks an API key, switch to the configured one
    has_groq = bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY != "dummy_key_for_now")
    has_gemini = bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "dummy_key_for_now")

    if active_provider == "gemini" and not has_gemini and has_groq:
        active_provider = "groq"
    elif active_provider == "groq" and not has_groq and has_gemini:
        active_provider = "gemini"

    if active_provider == "groq":
        return GroqProvider()
    elif active_provider == "gemini":
        return GeminiProvider()
    else:
        if has_groq:
            return GroqProvider()
        elif has_gemini:
            return GeminiProvider()
        raise ValueError(f"No configured LLM API key found. Please provide GROQ_API_KEY or GEMINI_API_KEY.")
