from typing import Dict, List, Optional, Any
from typing_extensions import override
import os
import uuid
from qdrant_client import AsyncQdrantClient, models
from .base import BaseVectorDB, MemorySearchScope


class QdrantDB(BaseVectorDB):

    def __init__(self, 
                 url: str = os.getenv("QDRANT_URL"),
                 api_key: str = os.getenv("QDRANT_API_KEY"),
                 collection_name: str = "memory_collection",
                 vector_embedding_model: str = os.getenv("VECTOR_EMBEDDING_MODEL"),
                 sparse_vector_embedding_model: str = os.getenv("SPARSE_VECTOR_EMBEDDING_MODEL"),
                 embed_models_cache_dir: str = './cache'):
        
        # Connect to Qdrant
        self.client: AsyncQdrantClient = AsyncQdrantClient(url=url,api_key=api_key)

        # Set both dense and sparse embedding models to use for hybrid search.
        self.vector_embedding_model = vector_embedding_model
        self.sparse_vector_embedding_model = sparse_vector_embedding_model
        
        self.client.set_model(self.vector_embedding_model, cache_dir=embed_models_cache_dir)
        self.client.set_sparse_model(self.sparse_vector_embedding_model, cache_dir=embed_models_cache_dir)

        # Set the collection name.
        self.collection_name = collection_name

    @override
    async def close(self):
        await self.client.close()

    # Setup methods
    @override
    async def setup(self, *args, **kwargs) -> None:
        """Setup the QdrantDB by creating the collection and payload indices."""
        
        await self._create_collection()
        await self._create_payload_indices()

    async def _create_collection(self) -> None:
        """Create collection with vector and sparse vector configs for hybrid search."""

        if not await self.client.collection_exists(self.collection_name):
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=self.client.get_fastembed_vector_params(),
                sparse_vectors_config=self.client.get_fastembed_sparse_vector_params(),
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
        await self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="org_id",
            field_schema=models.KeywordIndexParams(
                type="keyword",
                is_tenant=True,
            ),
        )

        # Create org_user_id index
        await self.client.create_payload_index(
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
        return list(self.client.embedding_models[self.vector_embedding_model].embed(queries))
    
    def _sparse_embed_queries(self, queries: List[str]) -> List[List[float]]:
        """Embed queries using the sparse vector embedding model."""
        return list(self.client.sparse_embedding_models[self.sparse_vector_embedding_model].embed(queries))

    # Core memory operations
    @override
    async def add_memories(
            self,
            org_id: str,
            user_id: str,
            agent_id: str,
            memory_ids: List[uuid.UUID],
            memories: List[str],
            obtained_at: str
    ) -> None:

        if len(memories) != len(memory_ids):
            raise ValueError("Length of memories and memory_ids must match")

        metadata = [
            {
                "org_id": org_id,
                "org_user_id": f"{org_id}:{user_id}",
                "user_id": user_id,
                "agent_id": agent_id,
                "obtained_at": obtained_at
            }
            for _ in memories
        ]

        await self.client.add(
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
            agent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:

        results = await self.search_memories(
            queries=[query],
            memory_search_scope=memory_search_scope,
            org_id=org_id,
            user_id=user_id,
            agent_id=agent_id
        )
        return results[0] if results else []

    @override
    async def search_memories(
            self,
            queries: List[str],
            memory_search_scope: MemorySearchScope,
            org_id: str,
            user_id: Optional[str] = None,
            agent_id: Optional[str] = None
    ) -> List[List[Dict[str, Any]]]:

        # Build filter conditions
        filter_conditions = []

        if memory_search_scope == MemorySearchScope.ORGANIZATION: # Search memories across the organization.
            filter_conditions.append(
                models.FieldCondition(
                    key="org_id",
                    match=models.MatchValue(value=org_id)
                )
            )
        elif memory_search_scope == MemorySearchScope.USER: # Search memories for a specific user in an organization.
            
            if user_id is None:
                raise ValueError("user_id is required in addition to org_id for user-specific search")
            
            filter_conditions.append(
                models.FieldCondition(
                    key="org_user_id",
                    match=models.MatchValue(value=f"{org_id}:{user_id}")
                )
            )


        if agent_id: # If agent id is provided, filter by agent also regardless of memory search scope.
            filter_conditions.append(
                models.FieldCondition(
                    key="agent_id",
                    match=models.MatchValue(value=agent_id)
                )
            )

        # Embed queries
        dense_embeddings = self._dense_embed_queries(queries)
        sparse_embeddings = self._sparse_embed_queries(queries)

        search_results = await self.client.query_batch_points(
            collection_name=self.collection_name,
            requests=[
                models.QueryRequest(
                    prefetch=[
                        models.Prefetch(
                            query=models.SparseVector(indices=sparse.indices, values=sparse.values),
                            using=self.client.get_sparse_vector_field_name(),
                            limit=10
                        ),
                        models.Prefetch(
                            query=dense,
                            using=self.client.get_vector_field_name(),
                            score_threshold=0.35,
                            limit=10
                        )
                    ],

                    filter=models.Filter(
                        must=filter_conditions
                    ) if filter_conditions else None,

                    with_payload=True,
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    params=models.SearchParams(quantization=models.QuantizationSearchParams(rescore=False))
                )
                for sparse, dense in zip(sparse_embeddings, dense_embeddings)
            ]
        )

        search_results = [
            [
                {'memory': point.payload.pop('document'), **point.payload, 'score': point.score, 'memory_id': point.id} 
                for point in query.points
                if point.score > 0.35 # Filter out low relevance memory.
            ] 
            for query in search_results
            ]
        return search_results

    @override
    async def delete_memory(self, memory_id: str) -> None:
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.PointIdsList(points=[memory_id])
        )

    @override 
    async def delete_memories(self, memory_ids: List[str]) -> None:
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.PointIdsList(points=memory_ids)
        )

    @override
    async def delete_all_user_memories(self, org_id: str, user_id: str) -> None:

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.Filter(
                must=models.FieldCondition(
                    key="org_user_id",
                    match=models.MatchValue(value=f"{org_id}:{user_id}")
                )
            )
        )

    @override
    async def delete_all_organization_memories(self, org_id: str) -> None:
        filter_conditions = [
            models.FieldCondition(
                key="org_id",
                match=models.MatchValue(value=org_id)
            )
        ]

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.Filter(
                must=filter_conditions
            )
        )