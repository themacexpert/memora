from typing import List

import neo4j
import neo4j.exceptions
import shortuuid
from typing_extensions import override

from memora.schema import models

from ..base import BaseGraphDB


class Neo4jOrganization(BaseGraphDB):

    @override
    async def create_organization(self, org_name: str) -> models.Organization:
        """
        Creates a new organization in the Neo4j graph database.

        Args:
            org_name (str): The name of the organization to create.

        Returns:
            Organization object containing:

                + org_id: Short UUID string
                + org_name: Organization name
                + created_at: DateTime object of when the organization was created
        """

        if not isinstance(org_name, str) or not org_name:
            raise TypeError("`org_name` must be a string and have a value.")

        org_id = shortuuid.uuid()
        self.logger.info(f"Creating organization with ID {org_id}")

        async def create_org_tx(tx):
            result = await tx.run(
                """
                CREATE (o:Org {
                    org_id: $org_id,
                    org_name: $org_name,
                    created_at: datetime()
                })
                RETURN o{.org_id, .org_name, .created_at} as org
            """,
                org_id=org_id,
                org_name=org_name,
            )

            record = await result.single()
            return record["org"] if record else None

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:

            org_data = await session.execute_write(create_org_tx)

            if org_data is None:
                self.logger.info(f"Failed to create organization {org_id}")
                raise neo4j.exceptions.Neo4jError("Failed to create organization.")

            self.logger.info(f"Successfully created organization {org_id}")
            return models.Organization(
                org_id=org_data["org_id"],
                org_name=org_data["org_name"],
                created_at=(org_data["created_at"]).to_native(),
            )

    @override
    async def update_organization(
        self, org_id: str, new_org_name: str
    ) -> models.Organization:
        """
        Updates an existing organization in the Neo4j graph database.

        Args:
            org_id (str): The Short UUID of the organization to update.
            new_org_name (str): The new name for the organization.

        Returns:
            Organization object containing:

                + org_id: Short UUID string
                + org_name: Organization name
                + created_at: DateTime object of when the organization was created
        """

        if not all(
            param and isinstance(param, str) for param in (org_id, new_org_name)
        ):
            raise ValueError(
                "Both `org_id` and `new_org_name` must be a string and have a value."
            )

        self.logger.info(f"Updating organization {org_id}")

        async def update_org_tx(tx):
            result = await tx.run(
                """
                MATCH (o:Org {org_id: $org_id})
                SET o.org_name = $new_org_name
                RETURN o{.org_id, .org_name, .created_at} as org
            """,
                org_id=org_id,
                new_org_name=new_org_name,
            )

            record = await result.single()
            return record["org"] if record else None

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:

            org_data = await session.execute_write(update_org_tx)

            if org_data is None:
                self.logger.info(f"Organization {org_id} not found")
                raise neo4j.exceptions.Neo4jError(
                    "Organization (`org_id`) does not exist."
                )

            self.logger.info(f"Successfully updated organization {org_id}")
            return models.Organization(
                org_id=org_data["org_id"],
                org_name=org_data["org_name"],
                created_at=(org_data["created_at"]).to_native(),
            )

    @override
    async def delete_organization(self, org_id: str) -> None:
        """
        Deletes an organization from the Neo4j graph database.

        Warning:
            This operation will delete all nodes and relationships from this organization
            including users, agents, memories, interactions etc.

        Args:
            org_id (str): Short UUID string identifying the organization to delete.
        """

        if not isinstance(org_id, str) or not org_id:
            raise TypeError("`org_id` must be a string and have a value.")

        self.logger.info(f"Deleting organization {org_id} and all associated data")

        async def delete_org_tx(tx):
            # Delete all nodes and relationships associated with the org
            await tx.run(
                """
                CALL apoc.periodic.iterate("
                MATCH (o:Org {org_id: $org_id})
                CALL apoc.path.subgraphNodes(o, {}) YIELD node
                RETURN node",
                "DETACH DELETE node",
                {batchSize: 1000, parallel: true, params: {org_id: $org_id}})
            """,
                org_id=org_id,
            )

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            await session.execute_write(delete_org_tx)
            self.logger.info(f"Successfully deleted organization {org_id}")

    @override
    async def get_organization(self, org_id: str) -> models.Organization:
        """
        Gets a specific organization from the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization to retrieve.

        Returns:
            Organization object containing:

                + org_id: Short UUID string
                + org_name: Organization name
                + created_at: DateTime object of when the organization was created
        """

        if not isinstance(org_id, str) or not org_id:
            raise TypeError("`org_id` must be a string and have a value.")

        async def get_org_tx(tx):
            result = await tx.run(
                """
                MATCH (o:Org {org_id: $org_id})
                RETURN o{.org_id, .org_name, .created_at} as org
            """,
                org_id=org_id,
            )
            record = await result.single()
            return record["org"] if record else None

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            org_data = await session.execute_read(get_org_tx)

            if org_data is None:
                self.logger.info(f"Organization {org_id} not found")
                raise neo4j.exceptions.Neo4jError(
                    "Organization (`org_id`) does not exist."
                )

            return models.Organization(
                org_id=org_data["org_id"],
                org_name=org_data["org_name"],
                created_at=(org_data["created_at"]).to_native(),
            )

    @override
    async def get_all_organizations(self) -> List[models.Organization]:
        """
        Gets all organizations from the graph database.

        Returns:
            List[Organization] each containing:

                + org_id: Short UUID string
                + org_name: Organization name
                + created_at: DateTime object of when the organization was created
        """

        self.logger.info("Getting all organizations")

        async def get_all_org_tx(tx):
            result = await tx.run(
                """
                MATCH (o:Org)
                RETURN o{.org_id, .org_name, .created_at} as org
            """
            )
            records = await result.value("org", [])
            return records

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:

            all_org_data = await session.execute_read(get_all_org_tx)

            return [
                models.Organization(
                    org_id=org_data["org_id"],
                    org_name=org_data["org_name"],
                    created_at=(org_data["created_at"]).to_native(),
                )
                for org_data in all_org_data
            ]
