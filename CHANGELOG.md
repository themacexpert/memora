# **Changelog**

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),  
and this project adheres to [Semantic Versioning](https://semver.org/).

## **[0.2.0] - 2025-01-25**

### **Added**
- **Memory Source Tracing**:
  - All memories now include their source messages that triggered them
  - Any method that returns memories (e.g., `get_user_memory`, `get_interaction`, ...) will include the source messages in the returned Memory model:
    ```python
    ...
    # Get a memory with its source messages
    memoryObj = await graph.get_user_memory(org_id, user_id, memory_id)
    
    print(memoryObj.memory)  # "Jake is allergic to peanuts"
    print(memoryObj.message_sources)  # List of MessageBlock(s) that triggered this memory e.g [MessageBlock(role="user", content="I had another peanut incident today; it confirms I am allergic.", msg_position=0), ...]
    
    # Each message source contains:
    for msg in memoryObj.message_sources:
        print(f"Role: {msg.role}")         # e.g., "user" or "assistant"
        print(f"Content: {msg.content}")    # The actual message content
        print(f"Position: {msg.msg_position}")  # Position in the interaction
    ```

    The Memory model structure:
    ```python
    class Memory(BaseModel):
        org_id: str
        agent_id: str
        user_id: str
        interaction_id: Optional[str]
        memory_id: str
        memory: str
        obtained_at: datetime
        message_sources: Optional[List[MessageBlock]] = Field(
            description="List of messages that triggered this memory. Note: A memory "
            "will lose its message sources if its interaction was updated with a "
            "conflicting conversation thread that led to those message(s) truncation."
        )
    ```

    This feature helps track the context and origin of each memory, making it easier to understand how and when memories were formed.

- **New Graph Methods**:
  - Added `get_all_organizations()` method to retrieve all organizations in the system (By [@alejmrm](https://github.com/alejmrm) in [#9](https://github.com/elzai/memora/pull/9))
  - Added organization and project arguments to `OpenAIBackendLLM`.
    ```python
    from memora.llm_backends import OpenAIBackendLLM

    openai_backend_llm = OpenAIBackendLLM(
        api_key="OPENAI_API_KEY",
        model="gpt-4o",
        organization="openai_org_id",
        project="openai_project_id",
    )
    ```

### **Changed**
- **⚠️ Breaking Changes**:
  - All methods now return Pydantic models instead of dictionaries for better type safety and validation:
    - Graph and vector database methods return models defined in `memora.schema.models`
    - See documentation for model schemas details. [Docs on Models](https://elzai.github.io/memora/api/schema/models/)

  - Renamed Graph Method `get_all_users` → `get_all_org_users` for clarity

  - Vector Database:
    - Collection naming convention updated:
      - Old default: `memory_collection`
      - New default: `memory_collection_v0_2`

    - Changed default dense embedding model from `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (768dim) to `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384dim) for good accuracy, at lower memory (now just ~700 MB instead of prior ~1.5 GB)

    - **Migration Required**: Users must call `vector_db.migrate_to_v0_2()` to migrate existing memories to the new collection that uses current dense embedding model.
    ```python
    await vector_db.migrate_to_v0_2(
        former_collection_name="memory_collection",
        new_collection_name="memory_collection_v0_2",
        delete_former_collection_after=True  # Optional
    )
    ```

  - Removed Graph methods `get_all_interaction_memories` and `get_interaction_messages` in favor of new unified `get_interaction` method with boolean flags:
    ```python
    ...
    # DEPRECATED - These methods no longer exist
    messages = await graph.get_interaction_messages(org_id, user_id, interaction_id)
    memories = await graph.get_all_interaction_memories(org_id, user_id, interaction_id)

    # NEW - Use get_interaction with boolean flags
    # Get both messages and memories
    interaction = await graph.get_interaction(
        org_id, 
        user_id, 
        interaction_id, 
        with_messages=True,  # Include messages
        with_memories=True   # Include memories
    )
    # Access messages and memories through the returned Interaction model
    messages = interaction.messages  # List[MessageBlock]
    memories = interaction.memories  # List[Memory]

    # Get only messages
    messages_only_interaction = await graph.get_interaction(
        org_id, 
        user_id, 
        interaction_id, 
        with_messages=True,
        with_memories=False
    )

    # Get only memories
    memories_only_interaction = await graph.get_interaction(
        org_id, 
        user_id, 
        interaction_id, 
        with_messages=False,
        with_memories=True
    )
    ```

    The new method returns an `Interaction` Pydantic model containing:
    ```python
    class Interaction(BaseModel):
        org_id: str
        agent_id: str
        interaction_id: str
        user_id: str
        created_at: datetime
        updated_at: datetime
        messages: Optional[List[MessageBlock]]  # Included if with_messages=True
        memories: Optional[List[Memory]]        # Included if with_memories=True
    ```

### **Fixed**
- **Update Interaction Inconsistency**:  
  - Fixed bug where memories were no longer linked to their source messages after the update, even though the update to the interaction was just appending new messages.
  - Fixed update to interaction not being stored when the update is shorter than existing interaction (e.g. different conversation thread).

### **Removed**
- Removed ability to configure dense and sparse embeddings - now just defaults to `prithivida/Splade_PP_en_v1` and `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` for optimal performance
  ```python
  ...
  ### Deprecated
  qdrant_db = QdrantDB(
                        async_client=AsyncQdrantClient(url="QDRANT_URL", api_key="QDRANT_API_KEY"),
                        vector_embedding_model= "another_supported_HF_dense_model",
                        sparse_vector_embedding_model= "another_supported_HF_sparse_model",
                      )

  ### Now
  qdrant_db = QdrantDB(async_client=AsyncQdrantClient(url="QDRANT_URL", api_key="QDRANT_API_KEY"))
  ```

---

## **[0.1.6] - 2025-01-08**

### **Fixed**
- **Contrary Memories Validation**:  
  - Fixed a bug related to the validation error for `contrary_memories` when saving or updating an interaction.
- **Weird Index Error**:
  - Fixed an index error that occurred when updating an interaction to a shorter and different one.

---

## **[0.1.5] - 2025-01-05**

### **Added**
- **Vector-Graph Database Association**:  
    - You can now directly associate a vector database with the graph database, so graph methods calls results in memories added / deleted across both databases.  
    - Association can be done by setting `.associated_vector_db` or during initialization.  
      ```python
      from memora.graph_db.neo4j import Neo4jGraphInterface
      from qdrant_client import AsyncQdrantClient
      from memora.vector_db.qdrant import QdrantDB

      neo4j_interface = Neo4jGraphInterface(
          uri="Neo4jURI",
          username="Neo4jUsername",
          password="Neo4jPassword",
          database="Neo4jDatabaseName",
      )

      neo4j_interface.associated_vector_db = QdrantDB(async_client=AsyncQdrantClient(url="QDRANT_URL", api_key="QDRANT_API_KEY"))

      # OR at initialization

      neo4j_interface = Neo4jGraphInterface(
          uri="Neo4jURI",
          username="Neo4jUsername",
          password="Neo4jPassword",
          database="Neo4jDatabaseName",
          # Association
          associated_vector_db=QdrantDB(async_client=AsyncQdrantClient(url="QDRANT_URL", api_key="QDRANT_API_KEY"))
      )
      ```

### **Changed**
  - **⚠️ Breaking Changes**:
    - Every subclass of `BaseGraphDB` must now implement `def get_associated_vector_db(self)` that returns the vector database (`BaseVectorDB`) associated with the graph database or `None`.

    - Previously, users had to pass the vector database's callable method to certain graph database's method to ensure data consistency within a transaction. This is no longer required.  
    e.g 
    ```python
    ...
    # DEPRECATED
    await memora.graph.delete_user_memory(org_id, user_id, "memory_uuid", memora.vector_db.delete_memory)
    # ... and other graph methods that required passing the vector method as a callable before.

    # Now
    await memora.graph.delete_user_memory(org_id, user_id, "memory_uuid")
    # ... the same goes for other graph methods, no need to pass the vector method as a callable anymore.
    ```

---
