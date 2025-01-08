# **Changelog**

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),  
and this project adheres to [Semantic Versioning](https://semver.org/).

## **[0.1.6] - 2025-01-08**
### **Fixed**
- **Contrary Memories Validation**:  
  - Fixed a bug related to the validation error for `contrary_memories` when saving or updating an interaction.
- **Weird Index Error**:
  - Fixed an index error that occurred when updating an interaction to a shorter and different one.

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
