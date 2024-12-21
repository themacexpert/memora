import os
from typing import *
from pydantic import BaseModel
from typing_extensions import override
from openai import AsyncOpenAI

from .base import BaseBackendLLM

class OpenAIBackendLLM(BaseBackendLLM):
    def __init__(self,
                model: str = os.getenv("OPENAI_MODEL_ID"),
                temperature: float = 0.7,
                top_p: float = 1,
                max_tokens: int = 512,
                max_retries: int = 3,
                api_key: str = os.getenv("OPENAI_API_KEY")
                ):
        """Initialize the OpenAILLM class with specific parameters."""

        super().__init__(model, temperature, top_p, max_tokens, max_retries)
        self.openai_client = AsyncOpenAI(
            api_key=api_key,
            max_retries=max_retries
        )

    @override
    async def close(self):
        await self.openai_client.close()
        self.openai_client = None

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
            response = await self.openai_client.beta.chat.completions.parse(
                messages=messages,
                **self.get_model_kwargs,
                response_format=output_schema_model,
            )
            return response.choices[0].message.parsed
        else:
            response = await self.openai_client.chat.completions.create(
                messages=messages,
                **self.get_model_kwargs,
            )
            return response.choices[0].message.content
