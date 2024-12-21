from abc import ABC, abstractmethod
from typing import Any, Dict, List, Union
from pydantic import BaseModel
from typing import Type

class BaseBackendLLM(ABC):
    """Abstract base class for LLMs used as backends by Memora."""

    def __init__(self, model: str, temperature: float, top_p: float, max_tokens: int, max_retries: int):
        """Initialize the base LLM class with common parameters.

        Args:
            model: The identifier for the specific model to use
            temperature: Controls randomness in responses.
            top_p: Controls diversity via nucleus sampling.
            max_tokens: Maximum number of tokens to generate.
            max_retries: Maximum number of retry attempts.
        """
        
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.stream = False  # Stream is always False because we need the full response at once.
        self.max_tokens = max_tokens
        self.max_retries = max_retries

    @abstractmethod
    async def close(self):
        """Closes the LLM connection."""
        pass

    @property
    @abstractmethod
    def get_model_kwargs(self) -> Dict[str, Any]:
        """Returns dictionary of model configuration parameters"""
        pass

    @abstractmethod
    async def __call__(self, messages: List[Dict[str, str]], output_schema_model: Type[BaseModel] | None = None) -> Union[str, BaseModel]:
        """
        Process messages and generate response
        
        Args:
            messages: List of message dicts with role and content
            output_schema_model: Optional Pydantic base model for structured output (ensure your model provider supports this for the chosen model)
        Returns:
            Generated text response as a string, or an instance of the output schema model if specified
        """
        pass