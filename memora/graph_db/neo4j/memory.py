from typing_extensions import override
import neo4j
from typing import Dict, List, Optional, Callable, Awaitable

from ..base import BaseGraphDB

class Neo4jMemory(BaseGraphDB):

    @override
    async def fetch_user_memories_resolved(self, org_id: str, user_id: str, memory_ids: List[str])-> List[Dict[str, str]]:

        results = await self.fetch_user_memories_resolved_batch(org_id, user_id, [memory_ids])
        return results[0]

    @override
    async def fetch_user_memories_resolved_batch(self, org_id: str, user_id: str, batch_memory_ids: List[List[str]])-> List[List[Dict[str, str]]]:
        
        async def fetch_resolved_batch_tx(tx):
            result = await tx.run("""
                MATCH (user:User {org_id: $org_id, user_id: $user_id})
                                  
                UNWIND $batch_memory_ids AS memory_ids
                CALL (user, memory_ids) {
                    UNWIND memory_ids AS id
                    MATCH (memory:Memory {org_id: $org_id, user_id: $user_id, memory_id: memory_id})
                                  
                    // Use the most up to date contrary update memory if it exists
                    OPTIONAL MATCH (memory)-[:CONTRARY_UPDATE*]->(contraryMemory:Memory) WHERE NOT (contraryMemory)-[:CONTRARY_UPDATE]->()
                    WITH coalesce(contraryMemory, memory) AS memoryToReturn
                                  
                    MATCH (agent:Agent {org_id: memoryToReturn.org_id, agent_id: memoryToReturn.agent_id})
                                  
                    // Case-insensitive 'user_' or 'agent_' followed by UUID and optional ('s) placeholders are replaced with actual names
                    RETURN collect(DISTINCT memoryToReturn{
                                                .memory_id, 
                                                memory: apoc.text.replace(
                                                    apoc.text.replace(memoryToReturn.memory, '(?i)user_[a-z0-9\\-]+(?:\\'s)?', user.user_name), 
                                                    '(?i)agent_[a-z0-9\\-]+(?:\\'s)?',  agent.agent_label
                                                ),
                                                obtained_at: toString(memoryToReturn.obtained_at)
                                            }) as resolved_memories
                }
                RETURN resolved_memories

            """, org_id=org_id, user_id=user_id, batch_memory_ids=batch_memory_ids)

            records = await result.value("resolved_memories", [])
            return records

        async with self.driver.session(database=self.database, default_access_mode=neo4j.READ_ACCESS) as session:
            return await session.execute_read(fetch_resolved_batch_tx)

    @override
    async def get_user_memory(self, org_id: str, user_id: str, memory_id: str) -> Dict[str, str]:
        
        async def get_memory_tx(tx):
            result = await tx.run("""
                MATCH (m:Memory {org_id: $org_id, user_id: $user_id, memory_id: $memory_id})
                RETURN m{.memory_id, .memory, obtained_at: toString(m.obtained_at)} as memory
            """, org_id=org_id, user_id=user_id, memory_id=memory_id)
            record = await result.single()
            return record["memory"]

        async with self.driver.session(database=self.database, default_access_mode=neo4j.READ_ACCESS) as session:
            return await session.execute_read(get_memory_tx)

    @override
    async def get_all_user_memories(self, org_id: str, user_id: str, agent_id: Optional[str] = None) -> List[Dict[str, str]]:
        
        async def get_all_memories_tx(tx):

            if agent_id: # Filter to only memories from interactions with this agent.
                result = await tx.run("""
                    MATCH (u:User {org_id: $org_id, user_id: $user_id})-[:HAS_MEMORIES]->(mc:MemoryCollection)
                    MATCH (mc)-[:INCLUDES]->(m:Memory)
                    WHERE m.agent_id = $agent_id
                    RETURN m{.memory_id, .memory, obtained_at: toString(m.obtained_at)} as memory
                """, org_id=org_id, user_id=user_id, agent_id=agent_id)
            
            else: # Fetch all.
                result = await tx.run("""
                    MATCH (u:User {org_id: $org_id, user_id: $user_id})-[:HAS_MEMORIES]->(mc:MemoryCollection)
                    MATCH (mc)-[:INCLUDES]->(m:Memory)
                    RETURN m{.memory_id, .memory, obtained_at: toString(m.obtained_at)} as memory
                """, org_id=org_id, user_id=user_id)


            records = await result.value("memory", [])
            return records

        async with self.driver.session(database=self.database, default_access_mode=neo4j.READ_ACCESS) as session:
            return await session.execute_read(get_all_memories_tx)

    @override
    async def delete_user_memory(self, org_id: str, user_id: str, memory_id: str, vector_db_delete_memory_by_id_fn: Callable[..., Awaitable[None]]) -> None:
        
        async def delete_memory_tx(tx):
            await tx.run("""
                MATCH (m:Memory {org_id: $org_id, user_id: $user_id, memory_id: $memory_id})
                DETACH DELETE m
            """, org_id=org_id, user_id=user_id, memory_id=memory_id)

            # Delete memory from vector DB.
            await vector_db_delete_memory_by_id_fn(memory_id)

        async with self.driver.session(database=self.database, default_access_mode=neo4j.WRITE_ACCESS) as session:
            await session.execute_write(delete_memory_tx)

    @override
    async def delete_all_user_memories(self, org_id: str, user_id: str, vector_db_delete_all_user_memories_fn: Callable[..., Awaitable[None]]) -> None:
        
        async def delete_all_memories_tx(tx):
            await tx.run("""
                MATCH (u:User {org_id: $org_id, user_id: $user_id})-[:HAS_MEMORIES]->(mc:MemoryCollection)
                MATCH (mc)-[:INCLUDES]->(memory:Memory)
                DETACH DELETE memory
            """, org_id=org_id, user_id=user_id)

            # Delete all memories from vector DB.
            await vector_db_delete_all_user_memories_fn(org_id, user_id)

        async with self.driver.session(database=self.database, default_access_mode=neo4j.WRITE_ACCESS) as session:
            await session.execute_write(delete_all_memories_tx)

