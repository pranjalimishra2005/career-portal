from abc import ABC, abstractmethod
from typing import Type, TypeVar, Optional, List, Dict, Any
from pydantic import BaseModel, Field

# Generic type variable for any Pydantic model
T = TypeVar("T", bound=BaseModel)


class LLMMessage(BaseModel):
    role: str = Field(..., description="system, user, or assistant")
    content: str = Field(..., description="Message text")


class LLMResponse(BaseModel):
    content: str
    raw_response: Optional[Dict[str, Any]] = None
    provider: str


class BaseLLMProvider(ABC):
    """
    Abstract interface for LLM providers (Gemini, Groq, Ollama).
    Guarantees standard behavior across all free API tiers.
    """

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        """Generates plain text response."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_retries: int = 2,
    ) -> T:
        """
        Generates a strictly validated Pydantic model instance.
        If the output does not parse or validate, it retries with the error feedback.
        """
        pass