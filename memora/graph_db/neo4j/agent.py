import shortuuid
import neo4j
from typing import Dict, List, Optional
from typing_extensions import override

from ..base import BaseGraphDB


class Neo4jAgent(BaseGraphDB):

    @override
    async def create_agent(self, org_id: str, agent_label: str, user_id: Optional[str] = None) -> Dict[str, str]:

        agent_id = shortuuid.uuid()
        
        async def create_agent_tx(tx):
            if user_id:
                result = await tx.run("""
                    MATCH (o:Org {org_id: $org_id}), (u:User {org_id: $org_id, user_id: $user_id})
                    CREATE (a:Agent {
                        org_id: $org_id,
                        user_id: $user_id,
                        agent_id: $agent_id,
                        agent_label: $agent_label,
                        created_at: datetime()
                    })
                    CREATE (o)-[:HAS_AGENT]->(a)
                    CREATE (u)-[:HAS_AGENT]->(a)
                    RETURN a{.org_id, .user_id, .agent_id, .agent_label, created_at: toString(a.created_at)} as agent
                """, org_id=org_id, user_id=user_id, agent_id=agent_id, agent_label=agent_label)
            else:
                result = await tx.run("""
                    MATCH (o:Org {org_id: $org_id})
                    CREATE (a:Agent {
                        org_id: $org_id,
                        agent_id: $agent_id,
                        agent_label: $agent_label,
                        created_at: datetime()
                    })
                    CREATE (o)-[:HAS_AGENT]->(a)
                    RETURN a{.org_id, .agent_id, .agent_label, created_at: toString(a.created_at)} as agent
                """, org_id=org_id, agent_id=agent_id, agent_label=agent_label)
            
            record = await result.single()
            return record["agent"]

        async with self.driver.session(database=self.database, default_access_mode=neo4j.WRITE_ACCESS) as session:
            agent_data = await session.execute_write(create_agent_tx)
            return agent_data

    @override
    async def delete_agent(self, org_id: str, agent_id: str) -> None:

        async def delete_agent_tx(tx):
            # Using node key (org_id, agent_id) for faster lookup
            await tx.run("""
                MATCH (a:Agent {org_id: $org_id, agent_id: $agent_id})
                DETACH DELETE a
            """, org_id=org_id, agent_id=agent_id)

        async with self.driver.session(database=self.database, default_access_mode=neo4j.WRITE_ACCESS) as session:
            await session.execute_write(delete_agent_tx)

    @override
    async def get_agent(self, org_id: str, agent_id: str) -> Dict[str, str]:

        async def get_agent_tx(tx):
            result = await tx.run("""
                MATCH (a:Agent {org_id: $org_id, agent_id: $agent_id})
                RETURN a{.org_id, .user_id, .agent_id, .agent_label, created_at: toString(a.created_at)} as agent
            """, org_id=org_id, agent_id=agent_id)
            record = await result.single()
            return record["agent"]

        async with self.driver.session(database=self.database, default_access_mode=neo4j.READ_ACCESS) as session:
            return await session.execute_read(get_agent_tx)

    @override
    async def get_all_org_agents(self, org_id: str) -> List[Dict[str, str]]:

        async def get_org_agents_tx(tx):
            result = await tx.run("""
                MATCH (o:Org {org_id: $org_id})-[:HAS_AGENT]->(a:Agent)
                RETURN a{.org_id, .agent_id, .agent_label, created_at: toString(a.created_at)} as agent
            """, org_id=org_id)
            records = await result.fetch()
            return [record["agent"] for record in records]

        async with self.driver.session(database=self.database, default_access_mode=neo4j.READ_ACCESS) as session:
            agents = await session.execute_read(get_org_agents_tx)
            return agents

    @override
    async def get_all_user_agents(self, org_id: str, user_id: str) -> List[Dict[str, str]]:

        async def get_user_agents_tx(tx):
            result = await tx.run("""
                MATCH (u:User {org_id: $org_id, user_id: $user_id})-[:HAS_AGENT]->(a:Agent)
                RETURN a{.org_id, .user_id, .agent_id, .agent_label, created_at: toString(a.created_at)} as agent
            """, org_id=org_id, user_id=user_id)
            records = await result.fetch()
            return [record["agent"] for record in records]

        async with self.driver.session(database=self.database, default_access_mode=neo4j.READ_ACCESS) as session:
            agents = await session.execute_read(get_user_agents_tx)
            return agents

