import shortuuid
import neo4j
from typing import Dict, List
from typing_extensions import override

from ..base import BaseGraphDB


class Neo4jUser(BaseGraphDB):

    @override
    async def create_user(self, org_id: str, user_name: str) -> Dict[str, str]:
        """
        Creates a new user in the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_name (str): Name for the user.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + user_id: Short UUID string
                + user_name: User's name
                + created_at: ISO format timestamp
        """

        user_id = shortuuid.uuid()

        async def create_user_tx(tx):
            result = await tx.run(
                """
                MATCH (o:Org {org_id: $org_id})
                CREATE (u:User {
                    org_id: $org_id,
                    user_id: $user_id,
                    user_name: $user_name,
                    created_at: datetime()
                })
                CREATE (u)-[:BELONGS_TO]->(o)
                CREATE (ic:InteractionCollection {
                    org_id: $org_id,
                    user_id: $user_id
                })
                CREATE (mc:MemoryCollection {
                    org_id: $org_id,
                    user_id: $user_id
                })
                CREATE (u)-[:INTERACTIONS_IN]->(ic)
                CREATE (u)-[:HAS_MEMORIES]->(mc)
                RETURN u{.org_id, .user_id, .user_name, created_at: toString(u.created_at)} as user
            """,
                org_id=org_id,
                user_id=user_id,
                user_name=user_name,
            )
            record = await result.single()
            return record["user"]

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            user_data = await session.execute_write(create_user_tx)
            return user_data

    @override
    async def update_user(
        self, org_id: str, user_id: str, new_user_name: str
    ) -> Dict[str, str]:
        """
        Updates an existing user in the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user to update.
            new_user_name (str): The new name for the user.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + user_id: Short UUID string
                + user_name: User's name
        """

        async def update_user_tx(tx):
            result = await tx.run(
                """
                MATCH (u:User {org_id: $org_id, user_id: $user_id})
                SET u.user_name = $new_user_name
                RETURN u{.org_id, .user_id, .user_name} as user
            """,
                org_id=org_id,
                user_id=user_id,
                new_user_name=new_user_name,
            )

            record = await result.single()
            return record["user"]

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            user_data = await session.execute_write(update_user_tx)
            return user_data

    @override
    async def delete_user(self, org_id: str, user_id: str) -> None:
        """
        Deletes a user from the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user to delete.
        """

        async def delete_user_tx(tx):
            await tx.run(
                """
                MATCH (u:User {org_id: $org_id, user_id: $user_id})
                OPTIONAL MATCH (u)-[:INTERACTIONS_IN]->(interactioncollection)
                OPTIONAL MATCH (interactioncollection)-[:HAD_INTERACTION]->(interaction)
                OPTIONAL MATCH (interaction)-[:FIRST_MESSAGE|IS_NEXT*]->(message)
                OPTIONAL MATCH (u)-[:HAS_MEMORIES]->(memcollection)
                OPTIONAL MATCH (memcollection)-[:INCLUDES]->(memory)
                OPTIONAL MATCH (interaction)-[:HAS_OCCURRENCE_ON]->(date)
                DETACH DELETE u, interactioncollection, interaction, message, memcollection, memory, date
            """,
                org_id=org_id,
                user_id=user_id,
            )

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            await session.execute_write(delete_user_tx)

    @override
    async def get_user(self, org_id: str, user_id: str) -> Dict[str, str]:
        """
        Gets a specific user belonging to the specified organization from the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user to retrieve.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + user_id: Short UUID string
                + user_name: User's name
                + created_at: ISO format timestamp
        """

        async def get_user_tx(tx):
            result = await tx.run(
                """
                MATCH (u:User {org_id: $org_id, user_id: $user_id})
                RETURN u{.org_id, .user_id, .user_name, created_at: toString(u.created_at)} as user
            """,
                org_id=org_id,
                user_id=user_id,
            )
            record = await result.single()
            return record["user"]

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            user = await session.execute_read(get_user_tx)
            return user

    @override
    async def get_all_users(self, org_id: str) -> List[Dict[str, str]]:
        """
        Gets all users belonging to the specified organization from the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.

        Returns:
            List[Dict[str, str]], each containing:

                + org_id: Short UUID string
                + user_id: Short UUID string
                + user_name: User's name
                + created_at: ISO format timestamp
        """

        async def get_users_tx(tx):
            result = await tx.run(
                """
                MATCH (o:Org {org_id: $org_id})<-[:BELONGS_TO]-(u:User)
                RETURN u{.org_id, .user_id, .user_name, created_at: toString(u.created_at)} as user
            """,
                org_id=org_id,
            )
            records = await result.value("user", [])
            return records

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            users = await session.execute_read(get_users_tx)
            return users
