import os
from typing import *
from pydantic import BaseModel
from typing_extensions import override
from openai import AsyncAzureOpenAI

from .base import BaseBackendLLM

class AzureOpenAIBackendLLM(BaseBackendLLM):
    def __init__(self,
                model: str = os.getenv("AZURE_OPENAI_MODEL_ID"),
                temperature: float = 0.7,
                top_p: float = 1,
                max_tokens: int = 512,
                max_retries: int = 3,
                endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_key: str = os.getenv("AZURE_OPENAI_API_KEY"),
                api_version: str = "2024-08-01-preview"
                ):
        """Initialize the AzureOpenAILLM class with specific parameters."""

        super().__init__(model, temperature, top_p, max_tokens, max_retries)
        self.azure_client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            max_retries=max_retries
        )

    @override
    async def close(self):
        await self.azure_client.close()
        self.azure_client = None

    @override
    @property
    def get_model_kwargs(self) -> Dict[str, Any]:

        return {
            "model": self.model,
            "top_p": self.top_p,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

    @override
    async def __call__(self, messages: List[Dict[str, str]], output_schema_model: Type[BaseModel] | None = None) -> Union[str, BaseModel]:

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
