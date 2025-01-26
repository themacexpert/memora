import asyncio
from datetime import datetime
from typing import Set, Tuple

from groq import AsyncGroq
from qdrant_client import AsyncQdrantClient

from memora import Memora
from memora.graph_db import Neo4jGraphInterface
from memora.llm_backends import GroqBackendLLM
from memora.vector_db import QdrantDB


class PersonalAssistant:

    def __init__(self, org_id: str, user_id: str, system_prompt: str):

        self.org_id = org_id
        self.user_id = user_id

        # Initialize databases
        vector_db = QdrantDB(
            async_client=AsyncQdrantClient(url="QDRANT_URL", api_key="QDRANT_API_KEY")
        )
        graph_db = Neo4jGraphInterface(
            uri="NEO4J_URI",
            username="NEO4J_USERNAME",
            password="NEO4J_PASSWORD",
            database="NEO4J_DATABASE",
        )

        self.memora = Memora(
            vector_db=vector_db,
            graph_db=graph_db,
            memory_search_model=GroqBackendLLM(
                api_key="GROQ_API_KEY", model="mixtral-8x7b-32768"
            ),
            extraction_model=GroqBackendLLM(
                api_key="GROQ_API_KEY", model="llama-3.3-70b-versatile", max_tokens=8000
            ),
        )

        # We recommend using your LLM provider implementation (openai, groq client etc.) instead of BaseBackendLLM for the chat model to utilize features like streaming and tools.
        self.chat_client = AsyncGroq(api_key="GROQ_API_KEY")

        # Track history: clean version without memory recalls. See "Why Track Two histories?" below.
        self.base_history = [{"role": "system", "content": system_prompt}]

        # Version with memory recalls for prompting
        self.prompt_history = self.base_history.copy()
        self.already_recalled_memory_ids: Set[str] = set()

    async def chat(self, user_message: str) -> str:

        recalled_memories, recalled_memory_ids = (
            await self.memora.recall_memories_for_message(
                self.org_id,
                self.user_id,
                user_message,
                preceding_msg_for_context=self.base_history[
                    1:
                ],  # Exclude system prompt.
                filter_out_memory_ids_set=self.already_recalled_memory_ids,
            )
        )

        include_memory_in_message = """
            memory recall: {memories}\n---\nmessage: {message}
        """.format(
            memories=str(
                [memory.memory_and_timestamp_dict() for memory in recalled_memories]
            ),
            message=user_message,
        )

        # Get model response
        response = await self.chat_client.chat.completions.create(
            messages=self.prompt_history
            + [{"role": "user", "content": include_memory_in_message}],
            model="llama-3.3-70b-versatile",
            stream=False,
        )
        assistant_reply = response.choices[0].message.content

        # Update conversation histories
        self.base_history.extend(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_reply},
            ]
        )

        # Note: This version uses the message with memory recalled.
        self.prompt_history.extend(
            [
                {"role": "user", "content": include_memory_in_message},
                {"role": "assistant", "content": assistant_reply},
            ]
        )

        self.already_recalled_memory_ids.update(recalled_memory_ids or [])

        return assistant_reply

    async def save_interaction(self) -> Tuple[str, datetime]:

        interaction_id, created_at = (
            await self.memora.save_or_update_interaction_and_memories(
                self.org_id,
                self.user_id,
                interaction=self.base_history[
                    1:
                ],  # Always use the base_history with system prompt for saving / updating.
            )
        )
        return interaction_id, created_at


async def main():

    org_id = "ORG_ID"
    user_id = "USER_ID"

    assistant = PersonalAssistant(
        org_id,
        user_id,
        "You are jake's assistant, given memories in 'memory recall: ...'",
    )

    while True:
        msg = input(">>> Jake: ")
        if msg == "quit()":
            break
        print(f">>> Assistant: {await assistant.chat(msg)}")

    interaction_id, created_at = await assistant.save_interaction()
    print(
        f"Interaction saved with ID: {interaction_id} and created at: {str(created_at)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
