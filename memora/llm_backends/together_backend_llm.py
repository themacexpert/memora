import os
from typing import *
from pydantic import BaseModel
from typing_extensions import override
from together import AsyncTogether

from .base import BaseBackendLLM

class TogetherBackendLLM(BaseBackendLLM):
    def __init__(self,
                model: str = os.getenv("TOGETHER_MODEL_ID"),
                temperature: float = 0.7,
                top_p: float = 1,
                max_tokens: int = 512,
                max_retries: int = 3,
                api_key: str = os.getenv("TOGETHER_API_KEY")
                ):
        
        super().__init__(model, temperature, top_p, max_tokens, max_retries)
        self.together_client = AsyncTogether(api_key=api_key, max_retries=max_retries)

    @override
    async def close(self):
        self.together_client = None

    @override
    @property
    def get_model_kwargs(self) -> Dict[str, Any]:

        return {
            "model": self.model,
            "top_p": self.top_p,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False
        }
    
    @override
    async def __call__(self, messages: List[Dict[str, str]], output_schema_model: Type[BaseModel] | None = None) -> Union[str, BaseModel]:
        
        if output_schema_model:
            response = await self.together_client.chat.completions.create(
                messages=messages,
                **self.get_model_kwargs,
                response_format={"type": "json_object", "schema": output_schema_model.model_json_schema()},
            )
            content = response.choices[0].message.content
            return output_schema_model.model_validate_json(content)
        
        else:
            response = await self.together_client.chat.completions.create(
                messages=messages,
                **self.get_model_kwargs,
            )
            return response.choices[0].message.content
