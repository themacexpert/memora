from typing import Dict, List, Optional, Any
from typing_extensions import override
import uuid
from qdrant_client import AsyncQdrantClient, models
from .base import BaseVectorDB, MemorySearchScope


class QdrantDB(BaseVectorDB):

    def __init__(
        self,
        async_client: AsyncQdrantClient = None,
        collection_name: str = "memory_collection",
        vector_embedding_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        sparse_vector_embedding_model: str = "prithivida/Splade_PP_en_v1",
        embed_models_cache_dir: str = "./cache",
    ):
        """
        Initialize the QdrantDB class.

        Args:
            async_client (AsyncQdrantClient): A pre-initialized Async Qdrant client
            collection_name (str): Name of the Qdrant collection
            vector_embedding_model (str): The name of the HuggingFace dense vector embedding model to use
            sparse_vector_embedding_model (str): The name of the HuggingFace sparse vector embedding model to use
            embed_models_cache_dir (str): Directory to cache the embedding models

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
        self.vector_embedding_model = vector_embedding_model
        self.sparse_vector_embedding_model = sparse_vector_embedding_model

        self.async_client.set_model(
            self.vector_embedding_model, cache_dir=embed_models_cache_dir
        )
        self.async_client.set_sparse_model(
            self.sparse_vector_embedding_model, cache_dir=embed_models_cache_dir
        )

        # Set the collection name.
        self.collection_name = collection_name

    @override
    async def close(self) -> None:
        """Closes the qdrant database connection."""

        await self.async_client.close()

    # Setup methods
    @override
    async def setup(self, *args, **kwargs) -> None:
        """Setup the QdrantDB by creating the collection and payload indices."""

        await self._create_collection()
        await self._create_payload_indices()

    async def _create_collection(self) -> None:
        """Create collection with vector and sparse vector configs for hybrid search."""

        if not await self.async_client.collection_exists(self.collection_name):
            await self.async_client.create_collection(
                collection_name=self.collection_name,
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

        Raises:
            ValueError: If the lengths of memory_ids and memories don't match
        """

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
            # parallel=0  # Use all CPU cores
        )

    @override
    async def search_memory(
        self,
        query: str,
        memory_search_scope: MemorySearchScope,
        org_id: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Memory search with optional user/agent filtering.

        Args:
            query (str): Search query string
            memory_search_scope (MemorySearchScope): Memory search scope (organization or user)
            org_id (str): Organization ID for filtering
            user_id (Optional[str]): Optional user ID for filtering
            agent_id (Optional[str]): Optional agent ID for filtering

        Returns:
            List[Dict[str, Any]] containing search results with at least:

                + memory: str
                + score: float
                + memory_id: str
                + org_id: str
                + user_id: str
                + obtained_at: Iso format timestamp
        """

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
    ) -> List[List[Dict[str, Any]]]:
        """
        Batch memory search with optional user/agent filtering.

        Args:
            queries (List[str]): List of search query strings
            memory_search_scope (MemorySearchScope): Memory search scope (organization or user)
            org_id (str): Organization ID for filtering
            user_id (Optional[str]): Optional user ID for filtering
            agent_id (Optional[str]): Optional agent ID for filtering

        Returns:
            List[List[Dict[str, Any]]] of search results for each query, where each dictionary contains at least:

                + memory: str
                + score: float
                + memory_id: str
                + org_id: str
                + user_id: str
                + obtained_at: Iso format timestamp
        """

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
                {
                    "memory": point.payload.pop("document"),
                    **point.payload,
                    "score": point.score,
                    "memory_id": point.id,
                }
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

        await self.async_client.delete(
            collection_name=self.collection_name,
            points_selector=models.PointIdsList(points=[memory_id]),
        )

    @override
    async def delete_memories(self, memory_ids: List[str]) -> None:
        """
        Delete multiple memories by their IDs.

        Args:
            memory_ids (List[str]): List of memory IDs to delete
        """

        await self.async_client.delete(
            collection_name=self.collection_name,
            points_selector=models.PointIdsList(points=memory_ids),
        )

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
