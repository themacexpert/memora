from typing import List

import neo4j
import neo4j.exceptions
import shortuuid
from typing_extensions import override

from memora.schema import models

from ..base import BaseGraphDB


class Neo4jUser(BaseGraphDB):

    @override
    async def create_user(self, org_id: str, user_name: str) -> models.User:
        """
        Creates a new user in the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_name (str): Name for the user.

        Returns:
            User containing:

                + org_id: Short UUID string
                + user_id: Short UUID string
                + user_name: User's name
                + created_at: DateTime object of when the user was created
        """

        if not all(param and isinstance(param, str) for param in (org_id, user_name)):
            raise ValueError(
                "Both `org_id` and `user_name` must be a string and have a value."
            )

        user_id = shortuuid.uuid()
        self.logger.info(f"Creating new user with ID {user_id}")

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
                RETURN u{.org_id, .user_id, .user_name, .created_at} as user
            """,
                org_id=org_id,
                user_id=user_id,
                user_name=user_name,
            )
            record = await result.single()
            return record["user"] if record else None

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            user_data = await session.execute_write(create_user_tx)

            if user_data is None:
                self.logger.info(f"Failed to create user {user_id}")
                raise neo4j.exceptions.Neo4jError("Failed to create user.")

            return models.User(
                org_id=user_data["org_id"],
                user_id=user_data["user_id"],
                user_name=user_data["user_name"],
                created_at=(user_data["created_at"]).to_native(),
            )

    @override
    async def update_user(
        self, org_id: str, user_id: str, new_user_name: str
    ) -> models.User:
        """
        Updates an existing user in the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user to update.
            new_user_name (str): The new name for the user.

        Returns:
            User containing:

                + org_id: Short UUID string
                + user_id: Short UUID string
                + user_name: User's name
                + created_at: DateTime object of when the user was created.
        """

        if not all(
            param and isinstance(param, str)
            for param in (org_id, user_id, new_user_name)
        ):
            raise ValueError(
                "`org_id`, `user_id` and `new_user_name` must be strings and have a value."
            )

        self.logger.info(f"Updating user {user_id}")

        async def update_user_tx(tx):
            result = await tx.run(
                """
                MATCH (u:User {org_id: $org_id, user_id: $user_id})
                SET u.user_name = $new_user_name
                RETURN u{.org_id, .user_id, .user_name, .created_at} as user
            """,
                org_id=org_id,
                user_id=user_id,
                new_user_name=new_user_name,
            )

            record = await result.single()
            return record["user"] if record else None

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            user_data = await session.execute_write(update_user_tx)

            if user_data is None:
                self.logger.info(
                    f"Failed to update user {user_id}: User does not exist"
                )
                raise neo4j.exceptions.Neo4jError(
                    "User (`org_id`, `user_id`) does not exist."
                )

            return models.User(
                org_id=user_data["org_id"],
                user_id=user_data["user_id"],
                user_name=user_data["user_name"],
                created_at=(user_data["created_at"]).to_native(),
            )

    @override
    async def delete_user(self, org_id: str, user_id: str) -> None:
        """
        Deletes a user from the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user to delete.
        """

        if not all(param and isinstance(param, str) for param in (org_id, user_id)):
            raise ValueError("`org_id` and `user_id` must be strings and have a value.")

        self.logger.info(f"Deleting user {user_id}")

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
    async def get_user(self, org_id: str, user_id: str) -> models.User:
        """
        Gets a specific user belonging to the specified organization from the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user to retrieve.

        Returns:
            User containing:

                + org_id: Short UUID string
                + user_id: Short UUID string
                + user_name: User's name
                + created_at: DateTime object of when the user was created.
        """

        if not all(param and isinstance(param, str) for param in (org_id, user_id)):
            raise ValueError("`org_id` and `user_id` must be strings and have a value.")

        async def get_user_tx(tx):
            result = await tx.run(
                """
                MATCH (u:User {org_id: $org_id, user_id: $user_id})
                RETURN u{.org_id, .user_id, .user_name, .created_at} as user
            """,
                org_id=org_id,
                user_id=user_id,
            )
            record = await result.single()
            return record["user"] if record else None

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            user_data = await session.execute_read(get_user_tx)

            if user_data is None:
                self.logger.info(f"Failed to get user {user_id}: User does not exist")
                raise neo4j.exceptions.Neo4jError(
                    "User (`org_id`, `user_id`) does not exist."
                )

            return models.User(
                org_id=user_data["org_id"],
                user_id=user_data["user_id"],
                user_name=user_data["user_name"],
                created_at=(user_data["created_at"]).to_native(),
            )

    @override
    async def get_all_org_users(self, org_id: str) -> List[models.User]:
        """
        Gets all users belonging to the specified organization from the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.

        Returns:
            List[User], each containing:

                + org_id: Short UUID string
                + user_id: Short UUID string
                + user_name: User's name
                + created_at: DateTime object of when the user was created.
        """

        if not isinstance(org_id, str) or not org_id:
            raise ValueError("`org_id` must be a string and have a value.")

        self.logger.info(f"Getting all users for organization {org_id}")

        async def get_users_tx(tx):
            result = await tx.run(
                """
                MATCH (o:Org {org_id: $org_id})<-[:BELONGS_TO]-(u:User)
                RETURN u{.org_id, .user_id, .user_name, .created_at} as user
            """,
                org_id=org_id,
            )
            records = await result.value("user", [])
            return records

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:

            all_users_data = await session.execute_read(get_users_tx)

            return [
                models.User(
                    org_id=user_data["org_id"],
                    user_id=user_data["user_id"],
                    user_name=user_data["user_name"],
                    created_at=(user_data["created_at"]).to_native(),
                )
                for user_data in all_users_data
            ]
