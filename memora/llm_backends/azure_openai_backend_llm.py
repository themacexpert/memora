from typing import *
from pydantic import BaseModel
from typing_extensions import override
from openai import AsyncAzureOpenAI

from .base import BaseBackendLLM


class AzureOpenAIBackendLLM(BaseBackendLLM):

    def __init__(
        self,
        azure_openai_client: AsyncAzureOpenAI = None,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        top_p: float = 1,
        max_tokens: int = 1024,
    ):
        """
        Initialize the AzureOpenAILLM class with the Azure OpenAI client and specific parameters.

        Args:
            azure_openai_client (AsyncAzureOpenAI): A pre-initialized Async Azure OpenAI client
            model (str): The name of the Azure OpenAI model to use
            temperature (float): The temperature to use for sampling
            top_p (float): The top_p value to use for sampling
            max_tokens (int): The maximum number of tokens to generate

        Example:
            ```python
            from openai import AsyncAzureOpenAI
            from memora.llm_backends.azure_openai_backend_llm import AzureOpenAIBackendLLM

            azure_openai_llm = AzureOpenAIBackendLLM(
                azure_openai_client=AsyncAzureOpenAI(
                    azure_endpoint="AZURE_OPENAI_ENDPOINT",
                    api_key="AZURE_OPENAI_API_KEY",
                    api_version="API_VERSION", # e.g "2024-08-01-preview" or later
                    max_retries=3
                    )
                )
            ```
        """

        self.azure_client = azure_openai_client
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens

    @override
    async def close(self) -> None:
        """Closes the LLM connection."""

        await self.azure_client.close()
        self.azure_client = None

    @override
    @property
    def get_model_kwargs(self) -> Dict[str, Any]:
        """Returns dictionary of model configuration parameters"""

        return {
            "model": self.model,
            "top_p": self.top_p,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    @override
    async def __call__(
        self,
        messages: List[Dict[str, str]],
        output_schema_model: Type[BaseModel] | None = None,
    ) -> Union[str, BaseModel]:
        """
        Process messages and generate response (📌 Streaming is not supported, as full response is required at once)

        Args:
            messages (List[Dict[str, str]]): List of message dicts with role and content e.g [{"role": "user", "content": "Hello!"}, ...]
            output_schema_model (Type[BaseModel] | None): Optional Pydantic base model for structured output (📌 Ensure the api version and selected model supportes this.)

        Returns:
            Union[str, BaseModel]: Generated text response as a string, or an instance of the output schema model if specified
        """

        if output_schema_model:
            response = await self.azure_client.beta.chat.completions.parse(
                messages=messages,
                **self.get_model_kwargs,
                response_format=output_schema_model,
            )
            return response.choices[0].message.parsed
        else:
            response = await self.azure_client.chat.completions.create(
                messages=messages,
                **self.get_model_kwargs,
            )
            return response.choices[0].message.content
