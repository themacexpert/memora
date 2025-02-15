import logging
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from qdrant_client import AsyncQdrantClient, models
from typing_extensions import override

import memora.schema.models as schema_models
from memora.vector_db.base import BaseVectorDB, MemorySearchScope


class QdrantDB(BaseVectorDB):

    def __init__(
        self,
        async_client: AsyncQdrantClient = None,
        collection_name: str = "memory_collection_v0_2",
        embed_models_cache_dir: str = "./cache",
        enable_logging: bool = False,
    ):
        """
        Initialize the QdrantDB class.

        Args:
            async_client (AsyncQdrantClient): A pre-initialized Async Qdrant client
            collection_name (str): Name of the Qdrant collection
            embed_models_cache_dir (str): Directory to cache the embedding models
            enable_logging (bool): Whether to enable console logging

        Example:
            ```python
            from qdrant_client import AsyncQdrantClient
            from memora.vector_db.qdrant import QdrantDB

            qdrant_db = QdrantDB(
                            async_client=AsyncQdrantClient(url="QDRANT_URL", api_key="QDRANT_API_KEY")
                        )
            ```
        """

        # Set Qdrant Client.
        self.async_client: AsyncQdrantClient = async_client

        # Set both dense and sparse embedding models to use for hybrid search.
        self.vector_embedding_model: str = (
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        self.sparse_vector_embedding_model: str = "prithivida/Splade_PP_en_v1"

        self.async_client.set_model(
            self.vector_embedding_model, cache_dir=embed_models_cache_dir
        )
        self.async_client.set_sparse_model(
            self.sparse_vector_embedding_model, cache_dir=embed_models_cache_dir
        )

        # Set the collection name.
        self.collection_name = collection_name

        # Configure logging
        self.logger = logging.getLogger(__name__)
        if enable_logging:
            logging.basicConfig(level=logging.INFO)

    @override
    async def close(self) -> None:
        """Closes the qdrant database connection."""

        await self.async_client.close()
        self.logger.info("QdrantDB connection closed")

    # Setup methods
    @override
    async def setup(self, *args, **kwargs) -> None:
        """Setup the QdrantDB by creating the collection and payload indices."""

        await self._create_collection_if_not_exists()
        await self._create_payload_indices()
        self.logger.info("QdrantDB setup completed")

    async def _create_collection_if_not_exists(
        self, collection_name: Optional[str] = None
    ) -> None:
        """
        Create collection (if not exists) with vector and sparse vector configs for hybrid search.

        Args:
            collection_name (Optional[str]): Name for the Qdrant collection. Defaults to self.collection_name.
        """

        collection_name = collection_name or self.collection_name

        if not await self.async_client.collection_exists(collection_name):
            await self.async_client.create_collection(
                collection_name=collection_name,
                vectors_config=self.async_client.get_fastembed_vector_params(),
                sparse_vectors_config=self.async_client.get_fastembed_sparse_vector_params(),
                hnsw_config=models.HnswConfigDiff(
                    payload_m=16,
                    # Disable global index creation to utilize org_id and user_id
                    # payload indices for multi-tenancy.
                    m=0,
                ),
                quantization_config=models.ScalarQuantization(
                    scalar=models.ScalarQuantizationConfig(
                        type=models.ScalarType.INT8,
                        quantile=0.95,
                        # Store quantized vectors in RAM for faster access.
                        always_ram=True,
                    ),
                ),
            )
            self.logger.info(f"Created collection: {collection_name}")

    async def _create_payload_indices(self) -> None:
        """Create payload indices for multi-tenancy."""

        # Create org_id index
        await self.async_client.create_payload_index(
            collection_name=self.collection_name,
            field_name="org_id",
            field_schema=models.KeywordIndexParams(
                type="keyword",
                is_tenant=True,
            ),
        )

        # Create org_user_id index
        await self.async_client.create_payload_index(
            collection_name=self.collection_name,
            field_name="org_user_id",
            field_schema=models.KeywordIndexParams(
                type="keyword",
                is_tenant=True,
            ),
        )
        self.logger.info("Created payload indexes on vector DB.")

    # Embedding helper methods
    def _dense_embed_queries(self, queries: List[str]) -> List[List[float]]:
        """Embed queries using the dense vector embedding model."""
        return list(
            self.async_client.embedding_models[self.vector_embedding_model].embed(
                queries
            )
        )

    def _sparse_embed_queries(self, queries: List[str]) -> List[List[float]]:
        """Embed queries using the sparse vector embedding model."""
        return list(
            self.async_client.sparse_embedding_models[
                self.sparse_vector_embedding_model
            ].embed(queries)
        )

    # Core memory operations
    @override
    async def add_memories(
        self,
        org_id: str,
        user_id: str,
        agent_id: str,
        memory_ids: List[uuid.UUID],
        memories: List[str],
        obtained_at: str,
    ) -> None:
        """
        Add memories to collection with their org_id, user_id, agent_id, and obtained_at datetime as metadata.

        Args:
            org_id (str): Organization ID for the memories
            user_id (str): User ID for the memories
            agent_id (str): Agent ID for the memories
            memory_ids (List[uuid.UUID]): List of UUIDs for each memory
            memories (List[str]): List of memory strings to add
            obtained_at (str): ISO format datetime string when the memories were obtained
        """

        if not memories:
            raise ValueError("At least one memory and its memory id is required")

        if len(memories) != len(memory_ids):
            raise ValueError("Length of memories and memory_ids must match")

        metadata = [
            {
                "org_id": org_id,
                "org_user_id": f"{org_id}:{user_id}",
                "user_id": user_id,
                "agent_id": agent_id,
                "obtained_at": obtained_at,
            }
            for _ in memories
        ]

        await self.async_client.add(
            collection_name=self.collection_name,
            documents=memories,
            metadata=metadata,
            ids=[str(memory_id) for memory_id in memory_ids],
            # parallel=_  # Use all CPU cores
        )
        self.logger.info(
            f"Added {len(memories)} memories to collection: {self.collection_name}"
        )

    @override
    async def search_memory(
        self,
        query: str,
        memory_search_scope: MemorySearchScope,
        org_id: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> List[Tuple[schema_models.Memory, float]]:
        """
        Memory search with optional user/agent filtering.

        Args:
            query (str): Search query string
            memory_search_scope (MemorySearchScope): Memory search scope (organization or user)
            org_id (str): Organization ID for filtering
            user_id (Optional[str]): Optional user ID for filtering
            agent_id (Optional[str]): Optional agent ID for filtering

        Returns:
            List[Tuple[Memory, float]] containing tuple of search results and score:
                Memory:

                    + org_id: str
                    + agent_id: str
                    + user_id: str
                    + memory_id: str
                    + memory: str
                    + obtained_at: datetime

                float: Score of the memory
        """

        if not query:
            raise ValueError("A query is required")

        results = await self.search_memories(
            queries=[query],
            memory_search_scope=memory_search_scope,
            org_id=org_id,
            user_id=user_id,
            agent_id=agent_id,
        )
        return results[0] if results else []

    @override
    async def search_memories(
        self,
        queries: List[str],
        memory_search_scope: MemorySearchScope,
        org_id: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> List[List[Tuple[schema_models.Memory, float]]]:
        """
        Batch memory search with optional user/agent filtering.

        Args:
            queries (List[str]): List of search query strings
            memory_search_scope (MemorySearchScope): Memory search scope (organization or user)
            org_id (str): Organization ID for filtering
            user_id (Optional[str]): Optional user ID for filtering
            agent_id (Optional[str]): Optional agent ID for filtering

        Returns:
            List[List[Tuple[Memory, float]]] of search results for each query, with a tuple containing:
                Memory:

                    + org_id: str
                    + agent_id: str
                    + user_id: str
                    + memory_id: str
                    + memory: str
                    + obtained_at: datetime

                float: Score of the memory
        """

        if not queries:
            raise ValueError("At least one query is required")

        # Build filter conditions
        filter_conditions = []

        if (
            memory_search_scope == MemorySearchScope.ORGANIZATION
        ):  # Search memories across the organization.
            filter_conditions.append(
                models.FieldCondition(
                    key="org_id", match=models.MatchValue(value=org_id)
                )
            )
        elif (
            memory_search_scope == MemorySearchScope.USER
        ):  # Search memories for a specific user in an organization.

            if user_id is None:
                raise ValueError(
                    "user_id is required in addition to org_id for user-specific search"
                )

            filter_conditions.append(
                models.FieldCondition(
                    key="org_user_id",
                    match=models.MatchValue(value=f"{org_id}:{user_id}"),
                )
            )

        if (
            agent_id
        ):  # If agent id is provided, filter by agent also regardless of memory search scope.
            filter_conditions.append(
                models.FieldCondition(
                    key="agent_id", match=models.MatchValue(value=agent_id)
                )
            )

        # Embed queries
        dense_embeddings = self._dense_embed_queries(queries)
        sparse_embeddings = self._sparse_embed_queries(queries)

        search_results = await self.async_client.query_batch_points(
            collection_name=self.collection_name,
            requests=[
                models.QueryRequest(
                    prefetch=[
                        models.Prefetch(
                            query=models.SparseVector(
                                indices=sparse.indices, values=sparse.values
                            ),
                            using=self.async_client.get_sparse_vector_field_name(),
                            limit=12,
                        ),
                        models.Prefetch(
                            query=dense,
                            using=self.async_client.get_vector_field_name(),
                            score_threshold=0.4,
                            limit=12,
                        ),
                    ],
                    filter=(
                        models.Filter(must=filter_conditions)
                        if filter_conditions
                        else None
                    ),
                    with_payload=True,
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    params=models.SearchParams(
                        quantization=models.QuantizationSearchParams(rescore=False)
                    ),
                )
                for sparse, dense in zip(sparse_embeddings, dense_embeddings)
            ],
        )

        search_results = [
            [
                (
                    schema_models.Memory(
                        org_id=point.payload["org_id"],
                        agent_id=point.payload["agent_id"],
                        user_id=point.payload["user_id"],
                        memory_id=point.id,
                        memory=point.payload["document"],
                        obtained_at=datetime.fromisoformat(
                            point.payload["obtained_at"]
                        ),
                    ),
                    point.score,
                )
                for point in query.points
                if point.score > 0.35  # Filter out low relevance memory.
            ]
            for query in search_results
        ]
        return search_results

    @override
    async def delete_memory(self, memory_id: str) -> None:
        """
        Delete a memory by its ID with optional org/user filtering.

        Args:
            memory_id (str): ID of the memory to delete
        """
        if memory_id:
            await self.async_client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(points=[memory_id]),
            )
            self.logger.info(f"Deleted memory with ID: {memory_id}")

    @override
    async def delete_memories(self, memory_ids: List[str]) -> None:
        """
        Delete multiple memories by their IDs.

        Args:
            memory_ids (List[str]): List of memory IDs to delete
        """

        if memory_ids:
            await self.async_client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(points=memory_ids),
            )
            self.logger.info(f"Deleted memories with IDs: {memory_ids}")

    @override
    async def delete_all_user_memories(self, org_id: str, user_id: str) -> None:
        """
        Delete all memories associated with a specific user.

        Args:
            org_id (str): Organization ID the user belongs to
            user_id (str): ID of the user whose memories should be deleted
        """

        await self.async_client.delete(
            collection_name=self.collection_name,
            points_selector=models.Filter(
                must=models.FieldCondition(
                    key="org_user_id",
                    match=models.MatchValue(value=f"{org_id}:{user_id}"),
                )
            ),
        )
        self.logger.info(
            f"Deleted all memories for user {user_id} in organization {org_id}"
        )

    @override
    async def delete_all_organization_memories(self, org_id: str) -> None:
        """
        Delete all memories associated with an organization.

        Args:
            org_id (str): ID of the organization whose memories should be deleted
        """

        filter_conditions = [
            models.FieldCondition(key="org_id", match=models.MatchValue(value=org_id))
        ]

        await self.async_client.delete(
            collection_name=self.collection_name,
            points_selector=models.Filter(must=filter_conditions),
        )
        self.logger.info(f"Deleted all memories for organization {org_id}")
