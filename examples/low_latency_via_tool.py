import asyncio
import json

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

ORG_ID = "ORG_ID"
USER_ID = "USER_ID"

# Define the memory search tool
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_memories",
            "description": "Search through user's memories with specific queries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of search queries to find relevant memories.",
                    }
                },
                "required": ["queries"],
            },
        },
    }
]


async def main():

    org_id = "ORG_ID"
    user_id = "USER_ID"

    # Async client initialization
    client = AsyncOpenAI(api_key="YourOpenAIAPIKey")

    messages = [
        {
            "role": "system",
            "content": "You are an assistant. When responding to the user, if you need memory to provide the best response, call the 'search_memories' tool with the required search queries.",
        },
        {
            "role": "user",
            "content": "Hey, what’s the name of the restaurant we went to last weekend? The one with the amazing tacos?",
        },
    ]

    # Step 1: Prompt the model.
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools,  # Include the memory search tool in the request
    )

    # Step 2: Extract the response and any tool call responses
    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls

    messages.append(response_message)  # Add the LLM's response to the conversation

    if tool_calls:  # The memory search tool was called.

        # There is only one tool (memory search, so we just extract the arguments).
        search_args = json.loads(
            tool_calls[0].function.arguments
        )  # Example: {"queries": ["restaurant last weekend", "amazing tacos"]}
        queries = search_args["queries"]  # ["restaurant last weekend", "amazing tacos"]

        # Step 3: Perform memory search with queries as a single batch
        recalled_memories = await memora.search_memories_as_one(
            org_id=org_id,
            user_id=user_id,
            search_queries=queries,
            search_across_agents=True,
        )

        # e.g recalled_memories: [
        # Memory(..., memory_id='uuid string', memory="Jake confirmed Chezy has the best tacos, saying his mouth literally watered.", obtained_at=datetime(...), message_sources=[...]),
        # Memory(..., memory_id='uuid string', memory="Jake is planing to go to Chezy this weekend.", obtained_at=datetime(...), message_sources=[...]),
        # ...]

        # Add the tool response to the conversation
        messages.append(
            {
                "tool_call_id": tool_calls[0].id,
                "role": "tool",  # Indicates this message is from tool use
                "name": "search_memories",
                "content": str(
                    [memory.memory_and_timestamp_dict() for memory in recalled_memories]
                ),
            }
        )

        # Make a final API call with the updated conversation that has the memories of the tool call.
        final_response = await client.chat.completions.create(
            model="gpt-4o", messages=messages
        )

        # Print the final response
        print(f">>> Assistant Reply: {final_response.choices[0].message.content}")

    else:  # The memory search tool wasn't called
        print(f">>> Assistant Reply: {response_message.content}")


if __name__ == "__main__":
    asyncio.run(main())
