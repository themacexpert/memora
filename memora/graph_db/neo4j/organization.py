from typing_extensions import override
import shortuuid
import neo4j

from ..base import BaseGraphDB

class Neo4jOrganization(BaseGraphDB):

    @override
    async def create_organization(self, org_name: str) -> dict:
        """Creates a new organization in Neo4j.
        
        Args:
            org_name: Name of the organization to create
            
        Returns:
            Dict containing org_id, org_name and created_at
        """
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
    async def delete_organization(self, org_id: str) -> None:
        """
        Deletes an organization and all its associated data from Neo4j.
        
        ⚠️ DANGER: This operation will delete all nodes and relationships from this organization this includes users, agents, memeories, interactions e.t.c

        Args:
            org_id: UUID of the organization to delete
        """
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
