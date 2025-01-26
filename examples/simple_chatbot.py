import asyncio

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from memora import Memora
from memora.graph_db import Neo4jGraphInterface
from memora.llm_backends import OpenAIBackendLLM
from memora.vector_db import QdrantDB

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

memora = Memora(
    vector_db=vector_db,
    graph_db=graph_db,
    # Fast model for memory search queries / filtering.
    memory_search_model=OpenAIBackendLLM(api_key="OPENAI_API_KEY", model="gpt-4o-mini"),
    # Powerful model for memory extraction
    extraction_model=OpenAIBackendLLM(api_key="OPENAI_API_KEY", model="gpt-4o"),
    enable_logging=True,
)

org_id = "ORG_ID"
user_id = "USER_ID"


async def main():
    # Async client initialization
    client = AsyncOpenAI(api_key="YourOpenAIAPIKey")

    messages = [
        {
            "role": "system",
            "content": "You are jake's assistant, given memories in 'memory recall: ...'",
        }
    ]

    user_message = "Hello, what is my wife's name ?"
    recalled_memories, _ = await memora.recall_memories_for_message(
        org_id, user_id, latest_msg=user_message
    )

    include_memory_in_message = """
        memory recall: {memories}\n---\nmessage: {message}
    """.format(
        memories=str(
            [memory.memory_and_timestamp_dict() for memory in recalled_memories]
        ),
        message=user_message,
    )

    messages.append({"role": "user", "content": include_memory_in_message})
    response = await client.chat.completions.create(model="gpt-4o", messages=messages)

    print(f">>> Assistant Reply: {response.choices[0].message.content}")


if __name__ == "__main__":
    asyncio.run(main())
