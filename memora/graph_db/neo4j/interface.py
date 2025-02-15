import logging
from typing import Optional

import neo4j
from neo4j import AsyncGraphDatabase
from typing_extensions import override

from ...vector_db.base import BaseVectorDB
from .agent import Neo4jAgent
from .interaction import Neo4jInteraction
from .memory import Neo4jMemory
from .organization import Neo4jOrganization
from .user import Neo4jUser


class Neo4jGraphInterface(
    Neo4jOrganization, Neo4jAgent, Neo4jUser, Neo4jInteraction, Neo4jMemory
):

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str,
        associated_vector_db: Optional[BaseVectorDB] = None,
        enable_logging: bool = False,
    ):
        """
        A unified interface for interacting with the Neo4j graph database.

        Args:
            uri (str): The URI of the Neo4j database.
            username (str): The username for authentication.
            password (str): The password for authentication.
            database (str): The name of the Neo4j database.
            associated_vector_db (Optional[BaseVectorDB]): The vector database to be associated with the graph for data consistency (e.g adding / deleting memories across both.)
            enable_logging (bool): Whether to enable console logging

        Example:
            ```python
            from memora.graph_db.neo4j import Neo4jGraphInterface
            from qdrant_client import AsyncQdrantClient
            from memora.vector_db.qdrant import QdrantDB

            neo4j_interface = Neo4jGraphInterface(
                uri="Neo4jURI",
                username="Neo4jUsername",
                password="Neo4jPassword",
                database="Neo4jDatabaseName",
                # Optional Association
                associated_vector_db=QdrantDB(async_client=AsyncQdrantClient(url="QDRANT_URL", api_key="QDRANT_API_KEY"))
            )
            ```
        """

        self.driver = AsyncGraphDatabase.driver(uri=uri, auth=(username, password))
        self.database = database
        self.associated_vector_db = associated_vector_db

        # Configure logging
        self.logger = logging.getLogger(__name__)
        if enable_logging:
            logging.basicConfig(level=logging.INFO)

    @override
    def get_associated_vector_db(self) -> Optional[BaseVectorDB]:
        """
        The vector database associated with the graph database, these is used inside the graph transactional blocks
        to ensure data consistency when handling memories across both stores (e.g., saving memories to the vector
        store and creating corresponding nodes in the graph db).
        """
        return self.associated_vector_db

    @override
    async def close(self):
        self.logger.info("Closing Neo4j driver")
        await self.driver.close()

    # Setup method
    @override
    async def setup(self, *args, **kwargs) -> None:
        """Sets up Neo4j database constraints and indices for the graph schema."""

        async def create_constraints_and_indexes(tx):
            self.logger.info("Creating constraints and indexes")
            # Organization node key
            await tx.run(
                """
                CREATE CONSTRAINT unique_org_id IF NOT EXISTS 
                FOR (o:Org) REQUIRE o.org_id IS NODE KEY
            """
            )

            # User node key
            await tx.run(
                """
                CREATE CONSTRAINT unique_org_user IF NOT EXISTS
                FOR (u:User) REQUIRE (u.org_id, u.user_id) IS NODE KEY
            """
            )

            # Agent node key
            await tx.run(
                """
                CREATE CONSTRAINT unique_org_agent IF NOT EXISTS 
                FOR (a:Agent) REQUIRE (a.org_id, a.agent_id) IS NODE KEY
            """
            )

            # Memory node key
            await tx.run(
                """
                CREATE CONSTRAINT unique_user_memory IF NOT EXISTS
                FOR (m:Memory) REQUIRE (m.org_id, m.user_id, m.memory_id) IS NODE KEY
            """
            )

            # Interaction node key
            await tx.run(
                """
                CREATE CONSTRAINT unique_user_interaction IF NOT EXISTS
                FOR (i:Interaction) REQUIRE (i.org_id, i.user_id, i.interaction_id) IS NODE KEY
            """
            )

            # Date node key
            await tx.run(
                """
                CREATE CONSTRAINT unique_user_date IF NOT EXISTS
                FOR (d:Date) REQUIRE (d.org_id, d.user_id, d.date) IS NODE KEY
            """
            )

        self.logger.info("Setting up Neo4j database constraints and indices")
        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            await session.execute_write(create_constraints_and_indexes)
        self.logger.info("Setup complete")

    # Migration method
    async def migrate_to_schema_for_memora_v0_3_x(self, *args, **kwargs) -> None:
        """
        Migrate the Neo4j graph database schema to the version that works with Memora v0.3.x

        This migration involves establishing :DATE_OBTAINED relationships between `Memory` nodes and `Date` nodes based on
        their `org_id, user_id, obtained_at` attributes and dropping the index `:Interaction (updated_at) -> interaction_updated_timestamp` (because
        Neo4j does not utilize it for index-backed sorting)
        """

        async def link_memories_to_dates(tx):
            self.logger.info(
                "Linking Memory nodes to Date nodes based on org_id, user_id, obtained_at"
            )
            await tx.run(
                """
                MATCH (memory:Memory)
                MERGE (date:Date {org_id: memory.org_id, user_id: memory.user_id, date: date(memory.obtained_at)})
                MERGE (memory)-[:DATE_OBTAINED]->(date)
                """
            )
            self.logger.info("Memory nodes successfully linked to their Date nodes")

        async def drop_index(tx):
            self.logger.info(
                "Dropping interaction_updated_timestamp_index index if it exists"
            )
            await tx.run(
                """
                DROP INDEX interaction_updated_timestamp_index IF EXISTS
                """
            )
            self.logger.info("Index dropped (if it existed)")

        self.logger.info(
            "Starting migration to graph schema that works with Memora v0.3.x"
        )
        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            await session.execute_write(link_memories_to_dates)
            await session.execute_write(drop_index)
        self.logger.info("Migration of graph schema completed")
