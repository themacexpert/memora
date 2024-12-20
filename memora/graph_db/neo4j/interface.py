import os
import neo4j
from neo4j import AsyncGraphDatabase
from datetime import date
from typing import Dict, List, Tuple
from typing_extensions import override

from .organization import Neo4jOrganization
from .agent import Neo4jAgent
from .user import Neo4jUser

class Neo4jGraphInterface(Neo4jOrganization, Neo4jAgent, Neo4jUser):

    def __init__(self,
                 uri: str = os.getenv("NEO4J_URI"),
                 username: str = os.getenv("NEO4J_USERNAME"),
                 password: str = os.getenv("NEO4J_PASSWORD"),
                 database: str = os.getenv("NEO4J_DATABASE")):

        self.driver = AsyncGraphDatabase.driver(uri=uri, auth=(username, password))
        self.database = database

    @override
    async def close(self):
        await self.driver.close()

    # Setup method
    @override
    async def setup(self, *args, **kwargs) -> None:
        """Sets up Neo4j database constraints and indices for the graph schema."""
    
        async def create_constraints_and_indexes(tx):
            # Organization node key
            await tx.run("""
                CREATE CONSTRAINT unique_org_id IF NOT EXISTS 
                FOR (o:Org) REQUIRE o.org_id IS NODE KEY
            """)

            # User node key
            await tx.run("""
                CREATE CONSTRAINT unique_org_user IF NOT EXISTS
                FOR (u:User) REQUIRE (u.org_id, u.user_id) IS NODE KEY
            """)

            # Agent node key
            await tx.run("""
                CREATE CONSTRAINT unique_org_agent IF NOT EXISTS 
                FOR (a:Agent) REQUIRE (a.org_id, a.agent_id) IS NODE KEY
            """)

            # Memory node key
            await tx.run("""
                CREATE CONSTRAINT unique_user_memory IF NOT EXISTS
                FOR (m:Memory) REQUIRE (m.org_id, m.user_id, m.memory_id) IS NODE KEY
            """)

            # Interaction node key
            await tx.run("""
                CREATE CONSTRAINT unique_user_interaction IF NOT EXISTS
                FOR (i:Interaction) REQUIRE (i.org_id, i.user_id, i.interaction_id) IS NODE KEY
            """)

            # Date node key
            await tx.run("""
                CREATE CONSTRAINT unique_user_date IF NOT EXISTS
                FOR (d:Date) REQUIRE (d.org_id, d.user_id, d.date) IS NODE KEY
            """)

        async with self.driver.session(database=self.database, default_access_mode=neo4j.WRITE_ACCESS) as session:
            await session.execute_write(create_constraints_and_indexes)

    # Interaction methods
    @override
    async def add_interaction_with_memories(
        self,
        org_id: str,
        agent_id: str, 
        user_id: str,
        interaction_date: date = date.today(),
        memories: List[str] = []
    ) -> str:
        return await add_interaction_with_memories(
            self.driver,
            org_id,
            agent_id,
            user_id,
            interaction_date,
            memories
        )

    @override
    async def update_interaction_with_memories(
        self,
        org_id: str,
        interaction_id: str,
        user_id: str,
        updated_date: date = date.today(),
        new_memories: List[str] = []
    ) -> Tuple[str, str]:
        return await update_interaction_with_memories(
            self.driver,
            org_id,
            interaction_id,
            user_id,
            updated_date,
            new_memories
        )

    @override
    async def delete_user_interaction(self, org_id: str, user_id: str, interaction_id: str) -> None:
        await delete_user_interaction(self.driver, org_id, user_id, interaction_id)

    @override
    async def delete_all_user_interactions(self, org_id: str, user_id: str) -> None:
        await delete_all_user_interactions(self.driver, org_id, user_id)

    @override
    async def get_all_interaction_memories(self, org_id: str, user_id: str, interaction_id: str) -> List[Dict[str, str]]:
        return await get_all_interaction_memories(self.driver, org_id, user_id, interaction_id)

    # Memory methods
    @override
    async def get_user_memory(self, org_id: str, user_id: str, memory_id: str) -> Dict[str, str]:
        return await get_user_memory(self.driver, org_id, user_id, memory_id)

    @override
    async def get_all_user_memories(self, org_id: str, user_id: str) -> List[Dict[str, str]]:
        return await get_all_user_memories(self.driver, org_id, user_id)

    @override
    async def delete_user_memory(self, org_id: str, user_id: str, memory_id: str) -> None:
        await delete_user_memory(self.driver, org_id, user_id, memory_id)

    @override
    async def delete_all_user_memories(self, org_id: str, user_id: str) -> None:
        await delete_all_user_memories(self.driver, org_id, user_id)
