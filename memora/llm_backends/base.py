from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type, Union

from pydantic import BaseModel


class BaseBackendLLM(ABC):
    """Abstract base class for LLMs used in the backend by Memora."""

    @abstractmethod
    async def close(self) -> None:
        """Closes the LLM connection."""
        pass

    @property
    @abstractmethod
    def get_model_kwargs(self) -> Dict[str, Any]:
        """
        Returns dictionary of model configuration parameters

        Example:
            return {
                "model": self.model, # model_name: gpt-4o
                "temperature": self.temperature, # 1
                "top_p": self.top_p, # 1
                "max_tokens": self.max_tokens, # 1024
                "stream": False,
            }
        """
        pass

    @abstractmethod
    async def __call__(
        self,
        messages: List[Dict[str, str]],
        output_schema_model: Type[BaseModel] | None = None,
    ) -> Union[str, BaseModel]:
        """
        Process messages and generate response (📌 Streaming is not supported, as full response is required at once)

        Args:
            messages (List[Dict[str, str]]): List of message dicts with role and content e.g [{"role": "user", "content": "Hello!"}, ...]
            output_schema_model (Type[BaseModel] | None): Optional Pydantic base model for structured output (📌 Ensure your model provider supports this for the chosen model)

        Returns:
            Union[str, BaseModel]: Generated text response as a string, or an instance of the output schema model if specified
        """
        pass
