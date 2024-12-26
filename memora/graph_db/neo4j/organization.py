from typing_extensions import override
import shortuuid
import neo4j

from ..base import BaseGraphDB

from typing import Dict

class Neo4jOrganization(BaseGraphDB):

    @override
    async def create_organization(self, org_name: str) -> Dict[str, str]:
        org_id = shortuuid.uuid()
        
        async def create_org_tx(tx):
            result = await tx.run("""
                CREATE (o:Org {
                    org_id: $org_id,
                    org_name: $org_name,
                    created_at: datetime()
                })
                RETURN o{.org_id, .org_name, created_at: toString(o.created_at)} as org
            """, 
            org_id=org_id, org_name=org_name)

            record = await result.single()
            return record["org"]

        async with self.driver.session(database=self.database, default_access_mode=neo4j.WRITE_ACCESS) as session:
            org_data = await session.execute_write(create_org_tx)
            return org_data

    @override
    async def update_organization(self, org_id: str, new_org_name: str) -> Dict[str, str]:
        async def update_org_tx(tx):
            result = await tx.run("""
                MATCH (o:Org {org_id: $org_id})
                SET o.org_name = $new_org_name
                RETURN o{.org_id, .org_name} as org
            """, 
            org_id=org_id, new_org_name=new_org_name)

            record = await result.single()
            return record["org"]

        async with self.driver.session(database=self.database, default_access_mode=neo4j.WRITE_ACCESS) as session:
            org_data = await session.execute_write(update_org_tx)
            return org_data
    
    @override
    async def delete_organization(self, org_id: str) -> None:

        async def delete_org_tx(tx):
            # Delete all nodes and relationships associated with the org
            await tx.run("""
                CALL apoc.periodic.iterate("
                MATCH (o:Org {org_id: $org_id})
                CALL apoc.path.subgraphNodes(o, {}) YIELD node
                RETURN node",
                "DETACH DELETE node",
                {batchSize: 1000, parallel: true, params: {org_id: $org_id}})
            """, org_id=org_id)

        async with self.driver.session(database=self.database, default_access_mode=neo4j.WRITE_ACCESS) as session:
            await session.execute_write(delete_org_tx)

    @override
    async def get_organization(self, org_id: str) -> Dict[str, str]:
        
        async def get_org_tx(tx):
            result = await tx.run("""
                MATCH (o:Org {org_id: $org_id})
                RETURN o{.org_id, .org_name, created_at: toString(o.created_at)} as org
            """, org_id=org_id)
            record = await result.single()
            return record["org"]

        async with self.driver.session(database=self.database, default_access_mode=neo4j.READ_ACCESS) as session:
            org_data = await session.execute_read(get_org_tx)
            return org_data