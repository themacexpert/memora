# **Prerequisites**

Before using Memora, you'll need to set up the following:

1. **Neo4j Database**  
     - Option A: [Install Neo4j locally (Free)](https://neo4j.com/docs/operations-manual/current/installation/)  
     - Option B: Use [Neo4j AuraDB Cloud (Free Option available)](https://neo4j.com/cloud/platform/aura-graph-database/)

2. **Qdrant Vector Database**  
     - Option A: [Install Qdrant locally (Free)](https://qdrant.tech/documentation/quick-start/)  
     - Option B: Use [Qdrant Cloud (Free Option available)](https://qdrant.tech/documentation/cloud/)

3. **LLM Provider API Key**  
   Choose one of the following providers and obtain an API key:  
     - [OpenAI](https://platform.openai.com/)  
     - [Azure OpenAI](https://azure.microsoft.com/en-us/products/cognitive-services/openai-service)  
     - [Together AI](https://www.together.ai/)  
     - [Groq](https://groq.com/)

4. **Optional: Rust/Cargo Setup**  
   The `neo4j-rust-ext` package may require Rust/Cargo for building from source if pre-built wheels are unavailable or fail to install on your system.  

    - **For Unix-like systems**:  
        Run the following command in your terminal:  
        ```console
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
        ```
    - **For other platforms or installation methods**:  
        Refer to the [Rust installation guide](https://www.rust-lang.org/tools/install).  

    **Note:** This setup is necessary if you encounter build errors related to the `neo4j-rust-ext` or `py-rust-stemmers` package.


## **Installation**

Install Memora using pip:

```bash
pip install memora-core
```

## **Basic Setup**

Here's how to initialize Memora with the databases and an LLM provider:

```python
from memora import Memora
from qdrant_client import AsyncQdrantClient
from memora.vector_db import QdrantDB
from memora.graph_db import Neo4jGraphInterface
from memora.llm_backends import GroqBackendLLM

# Initialize databases
vector_db = QdrantDB(async_client=AsyncQdrantClient(url="QDRANT_URL", api_key="QDRANT_API_KEY"))

graph_db = Neo4jGraphInterface(uri="Neo4jURI", username="Username", password="Password", database="DBName")

# Only call setup on the very first run - (creates necessary indexes, contraints, etc.)
await vector_db.setup()
await graph_db.setup()


# Initialize Memora with Groq as the LLM provider
memora = Memora(
    vector_db=vector_db,
    graph_db=graph_db,
    # Fast model for memory search queries / filtering.
    memory_search_model=GroqBackendLLM(api_key="GROQ_API_KEY", model="llama-3.1-8b-instant"),
    # Powerful model for memory extraction
    extraction_model=GroqBackendLLM(api_key="GROQ_API_KEY", model="llama-3.3-70b-specdec", max_tokens=8000)
)

```

### **Creating An Organization, User, and Agent**

```python
# Create an organization
org = await memora.graph.create_organization("My Organization")
org_id = org['org_id'] # Short UUID e.g 'gmDr4sUiWMCqbGAiV8jjbU'

# Create a user in the organization
user = await memora.graph.create_user(org_id, "Alice")
user_id = user['user_id'] # Short UUID e.g '89sSRXoz53gdWPJoTEEass'

# Create an agent belonging to the organization and user (optionally).
agent = await memora.graph.create_agent(org_id, "Jenny, Personal AI", user_id=user_id)
agent_id = agent['agent_id'] # Short UUID e.g 'CcyKXxhi2skEcDpRzNZim7'

```

!!! note "Important Note"
    For organization, user, agent, and interaction IDs, we use `shortuuid.uuid()` to generate compact short UUIDs, a base57-encoded version of standard UUIDs. They are shorter but retain the same uniqueness.

    For memory IDs, we use the standard UUIDs `uuid.uuid4()`, as these are supported as vector IDs for the vast majority of vector databases.

## **Core Operations**

### **1. Saving an Interaction and its Memories**

```python
# Example interaction
interaction = [
    {"role": "user", "content": "I had another peanut incident today; it confirms I am allergic."},
    {"role": "assistant", "content": "Oh Jake, I'm sorry to hear that. Are you okay? I'll make sure to keep peanuts 🥜 away from any future food-related situations."},
    {"role": "user", "content": "Yes, I'm okay, though it stressed out Sarah, my wife, which isn't cool because she is due in December."},
    {"role": "assistant", "content": "I'm glad you're fine now, and that's wonderful news about Sarah's pregnancy! Congratulations to you both. When in December is she due?"},
    {"role": "user", "content": "December 15th."},
    {"role": "assistant", "content": "Congrats again, and feel free to bombard me with every baby question you have 👶🍼, we're raising this baby together LOL 😉"}
]

# Save the interaction and its memories
interaction_id, created_at_timestamp = await memora.save_or_update_interaction_and_memories(
    org_id=org_id,
    user_id=user_id,
    agent_id=agent_id,
    interaction=interaction,
    current_datetime=datetime.now()
)

```

### **2. Updating An Existing Interaction and its Memories**

The updated interaction will be compared with the existing one:

  - If differences are found, truncates existing record from that point and
    replaces with updated version. Old memories from truncated message(s)
    remain but are not linked to the truncated message(s).
  - If no differences, appends new messages from the update.

```python
updated_interaction = interaction + [
    {"role": "user", "content": "Thanks! We're pretty sure it's a girl, but we'll know for certain at the next ultrasound."},
    {"role": "assistant", "content": "The anticipation must be building. Do you have any name ideas?."}
]

# Update the existing interaction (In this case it simply appends the new messages)
interaction_id, updated_at_timestamp = await memora.save_or_update_interaction_and_memories(
    org_id=org_id,
    user_id=user_id,
    agent_id=agent_id,
    interaction=updated_interaction,
    interaction_id=interaction_id,  # Pass the existing interaction_id to update
    current_datetime=datetime.now()
)
```

### **3. Searching Memories**

```python
from memora.vector_db.base import MemorySearchScope

# Returns a consolidated list of results for all queries (sorted by relevance), instead of individual lists per query.
memories = await memora.search_memories_as_one(
    org_id=org_id,
    user_id=user_id,
    search_queries=["Who is my wife?", "When is my wife due?"],
    search_across_agents=True
)
# memories: [{"memory_id": "uuid string", "memory": "Jake married Sarah on August 12th, 2023", obtained_at: "iso timestamp"},{"memory_id": "uuid string", "memory": "Jake's wife Sarah is due on December 15th", obtained_at: "iso timestamp"}, ...]



# Perform a batch search for memories, obtaining a list of results for each query, and can specify the search scope
batch_memories = await memora.search_memories_as_batch(
    org_id=org_id,
    search_queries=["user's allergies", "user's family details"],
    user_id=user_id,
    memory_search_scope=MemorySearchScope.USER,  # Can be "user" or "organization"
    search_across_agents=True
)
# batch_memories: [[{"memory_id": "uuid string", "memory": "Jake has confirmed he is allergic to peanuts", obtained_at: "iso timestamp"}, ...], [{"memory_id": "uuid string", "memory": "Jake's wife Sarah is due on December 15th", obtained_at: "iso timestamp"}, ...]]
```

### **4. Recall Memories for a User's Message in Interaction**

```python
recalled_memories, memory_ids = await memora.recall_memories_for_message(
    org_id,
    user_id,
    latest_msg="Sarah is really in pain more nowdays, so both of us can't sleep.",
    # Optional: Add previous messages in the interaction for context.
    preceding_msg_for_context=[],
    # Optional: Exclude previously recalled memories (e.g They are already in the conversation). See sample personal assistant below.
    filter_out_memory_ids_set={'4b9df118-fa11-4e29-abfd-3b02587aa251'}  
)

# recalled_memories: [{"memory": "Jake's wife Sarah is due on December 15th", "obtained_at": "iso timestamp"}, {"memory": "Jake and Sarah are pretty confident the baby’s a girl but will confirm at the next ultrasound.", "obtained_at": "iso timestamp"}, ...]

# memory_ids: ["uuid string", "uuid string", ...]
```


### **5. Managing Memories**

```python
# Get all memories for a user
all_memories = await memora.graph.get_all_user_memories(org_id, user_id)

# Get memories from a specific interaction
interaction_memories = await memora.graph.get_all_interaction_memories(org_id, user_id, interaction_id)

# Get the history of a specific memory, this contains all updates of a memory in descending order (starting with the latest version to the oldest)
history = await memora.graph.get_user_memory_history(org_id, user_id, "memory_uuid")

# Delete a specific memory
await memora.graph.delete_user_memory(org_id, user_id, "memory_uuid")
```

!!! note
    For more methods, see the `API Reference` page on your desired GraphDB implementation. (Just [Neo4j](api/graph_db/neo4j.md) for now.)


## **A Simple Example**

```python
from openai import AsyncOpenAI

... # Preceding code where you have initialized memora, and stored org_id and user_id in variables.

# Async client initialization
client = AsyncOpenAI(api_key="YourOpenAIAPIKey")

messages=[{ "role": "system", "content": "You are jake's assistant, given memories in 'memory recall: ...'"}]

user_message = "Hello, what is my wife's name ?"
recalled_memories, _ = await memora.recall_memories_for_message(org_id, user_id, latest_msg=user_message)

include_memory_in_message = """
    memory recall: {memories}\n---\nmessage: {message}
""".format(memories=str(recalled_memories), message=user_message)

messages.append({'role': 'user', 'content': include_memory_in_message})
response = await client.chat.completions.create(model="gpt-4o", messages=messages)

print(f">>> Assistant Reply: {response.choices[0].message.content}")

```

## **A Tad Bit Complex Personal Assistant with Memora**

Here's a sample example of a personal assistant that using Memora:

```python
from typing import *
from groq import AsyncGroq
from qdrant_client import AsyncQdrantClient
from memora.vector_db import QdrantDB
from memora.graph_db import Neo4jGraphInterface
from memora.llm_backends import GroqBackendLLM

class PersonalAssistant:

    def __init__(self, org_id: str, user_id: str, system_prompt: str):

        self.org_id = org_id
        self.user_id = user_id
        
        # Initialize databases
        vector_db = QdrantDB(async_client=AsyncQdrantClient(url="QDRANT_URL", api_key="QDRANT_API_KEY"))
        graph_db = Neo4jGraphInterface(
            uri="NEO4J_URI",
            username="NEO4J_USERNAME", password="NEO4J_PASSWORD",
            database="NEO4J_DATABASE"
        )

        self.memora = Memora(
            vector_db=vector_db, graph_db=graph_db,
            memory_search_model=GroqBackendLLM(api_key="GROQ_API_KEY", model="llama-3.1-8b-instant"),
            extraction_model=GroqBackendLLM(api_key="GROQ_API_KEY", model="llama-3.3-70b-specdec", max_tokens=8000),
        )

        # We recommend using your LLM provider implementation (openai, groq client etc.) instead of BaseBackendLLM for the chat model to utilize features like streaming and tools.
        self.chat_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

        # Track history: clean version without memory recalls. See "Why Track Two histories?" below.
        self.base_history = [{"role": "system", "content": system_prompt}]

        # Version with memory recalls for prompting
        self.prompt_history = self.base_history.copy()
        self.already_recalled_memory_ids: Set[str] = set()

    async def chat(self, user_message: str) -> str:

        recalled_memories, recalled_memory_ids = await self.memora.recall_memories_for_message(
            self.org_id, self.user_id,
            user_message, preceding_msg_for_context=self.base_history[1:], # Exclude system prompt.
            filter_out_memory_ids_set=self.already_recalled_memory_ids
        )

        include_memory_in_message = """
            memory recall: {memories}\n---\nmessage: {message}
        """.format(memories=str(recalled_memories), message=user_message)

        # Get model response
        response = await self.chat_client.chat.completions.create(
            messages=self.prompt_history + [{"role": "user", "content": include_memory_in_message}],
            model="llama-3.3-70b-specdec",
            stream=False
        )
        assistant_reply = response.choices[0].message.content

        # Update conversation histories
        self.base_history.extend([{"role": "user", "content": user_message}, {"role": "assistant", "content": assistant_reply}])
        
        # Note: This version uses the message with memory recalled.
        self.prompt_history.extend([{"role": "user", "content": include_memory_in_message}, {"role": "assistant", "content": assistant_reply}])
        
        self.already_recalled_memory_ids.update(recalled_memory_ids or [])
        
        return assistant_reply

    async def save_interaction(self) -> Tuple[str, str]:

        interaction_id, created_at = await self.memora.save_or_update_interaction_and_memories(
            self.org_id, self.user_id, 
            interaction=self.base_history[1:] # Always use the base_history with system prompt for saving / updating.
        )
        return interaction_id, created_at


async def main():

    assistant = PersonalAssistant(
        org_id, user_id, 
        "You are jake's assistant, given memories in 'memory recall: ...'"
    )

    while True:
        msg = input(">>> Jake: ")
        if msg == "quit()":
            break
        print(f">>> Assistant: {await assistant.chat(msg)}")

    interaction_id, created_at = await assistant.save_interaction()
    print(f"Interaction saved with ID: {interaction_id} and created at: {created_at}")
```

???+ note "Why Track Two histories?"

    We need two versions:

    1. **Base History**: Contains only the user message and the assistant's reply.
    2. **Prompted History**: Includes the recalled memories along with the user message and the assistant's reply. This version is used for prompting.

    The recalled memories are kept in the prompted history for many reasons one being so later in the same interaction if the user asks why the AI provided a particular reply, the AI can reference the memories listed under `memory recall` above that user message.

    When saving the interaction or using preceding messages for context in a memory search, we use the base history without the memory recalls. This is because for saving, we only need new memories from that interaction and when referencing preceding messages, we focus on what was previously said, so their memory recalls are not necessary.


## Advanced Usage

For more advanced usage, please refer to our [Advanced Usage Guide](advanced_usage.md).