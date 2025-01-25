from typing import List, Optional

import neo4j
import neo4j.exceptions
import shortuuid
from typing_extensions import override

from memora.schema import models

from ..base import BaseGraphDB


class Neo4jAgent(BaseGraphDB):

    @override
    async def create_agent(
        self, org_id: str, agent_label: str, user_id: Optional[str] = None
    ) -> models.Agent:
        """
        Creates a new agent in the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_label (str): Label/name for the agent.
            user_id (Optional[str]): Optional Short UUID of the user. This is used when the agent is created
                specifically for a user, indicating that both the organization and the
                user will have this agent.

        Returns:
            Agent containing:

                + org_id: Short UUID string
                + user_id: Optional Short UUID string
                + agent_id: Short UUID string
                + agent_label: Agent label/name
                + created_at: DateTime object of when the agent was created
        """

        if not all(param and isinstance(param, str) for param in (org_id, agent_label)):
            raise ValueError(
                "Both `org_id` and `agent_label` must be a string and have a value."
            )

        if user_id:
            if not isinstance(user_id, str):
                raise ValueError("`user_id` must be a string.")

        agent_id = shortuuid.uuid()
        self.logger.info(f"Creating new agent with ID {agent_id}")

        async def create_agent_tx(tx):
            if user_id:
                result = await tx.run(
                    """
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
                    RETURN a{.org_id, .user_id, .agent_id, .agent_label, .created_at} as agent
                """,
                    org_id=org_id,
                    user_id=user_id,
                    agent_id=agent_id,
                    agent_label=agent_label,
                )
            else:
                result = await tx.run(
                    """
                    MATCH (o:Org {org_id: $org_id})
                    CREATE (a:Agent {
                        org_id: $org_id,
                        agent_id: $agent_id,
                        agent_label: $agent_label,
                        created_at: datetime()
                    })
                    CREATE (o)-[:HAS_AGENT]->(a)
                    RETURN a{.org_id, .agent_id, .agent_label, .created_at} as agent
                """,
                    org_id=org_id,
                    agent_id=agent_id,
                    agent_label=agent_label,
                )

            record = await result.single()
            return record["agent"] if record else None

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            agent_data = await session.execute_write(create_agent_tx)

            if agent_data is None:
                self.logger.info(f"Failed to create agent {agent_id}")
                raise neo4j.exceptions.Neo4jError("Failed to create agent.")

            self.logger.info(f"Successfully created agent {agent_id}")
            return models.Agent(
                org_id=agent_data["org_id"],
                agent_id=agent_data["agent_id"],
                user_id=agent_data.get("user_id"),
                agent_label=agent_data["agent_label"],
                created_at=(agent_data["created_at"]).to_native(),
            )

    @override
    async def update_agent(
        self, org_id: str, agent_id: str, new_agent_label: str
    ) -> models.Agent:
        """
        Updates an existing agent in the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_id (str): Short UUID string identifying the agent to update.
            new_agent_label (str): New label/name for the agent.

        Returns:
            Agent containing:

                + org_id: Short UUID string
                + user_id: Optional Short UUID string
                + agent_id: Short UUID string
                + agent_label: Agent label/name
                + created_at: DateTime object of when the agent was created
        """

        if not all(
            param and isinstance(param, str)
            for param in (org_id, agent_id, new_agent_label)
        ):
            raise ValueError(
                "`org_id`, `agent_id` and `new_agent_name` must be strings and have a value."
            )

        self.logger.info(f"Updating agent {agent_id}")

        async def update_agent_tx(tx):
            result = await tx.run(
                """
                MATCH (a:Agent {org_id: $org_id, agent_id: $agent_id})
                SET a.agent_label = $new_agent_label
                RETURN a{.org_id, .user_id, .agent_id, .agent_label, .created_at} as agent
            """,
                org_id=org_id,
                agent_id=agent_id,
                new_agent_label=new_agent_label,
            )

            record = await result.single()
            return record["agent"] if record else None

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            agent_data = await session.execute_write(update_agent_tx)

            if agent_data is None:
                self.logger.info(
                    f"Failed to update agent {agent_id}: Agent does not exist"
                )
                raise neo4j.exceptions.Neo4jError(
                    "Agent (`org_id`, `agent_id`) does not exist."
                )

            self.logger.info(f"Successfully updated agent {agent_id}")
            return models.Agent(
                org_id=agent_data["org_id"],
                agent_id=agent_data["agent_id"],
                user_id=agent_data.get("user_id"),
                agent_label=agent_data["agent_label"],
                created_at=(agent_data["created_at"]).to_native(),
            )

    @override
    async def delete_agent(self, org_id: str, agent_id: str) -> None:
        """
        Deletes an agent from the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_id (str): Short UUID string identifying the agent to delete.
        """

        if not all(param and isinstance(param, str) for param in (org_id, agent_id)):
            raise ValueError(
                "`org_id` and `agent_id` must be strings and have a value."
            )

        self.logger.info(f"Deleting agent {agent_id}")

        async def delete_agent_tx(tx):
            # Using node key (org_id, agent_id) for faster lookup
            await tx.run(
                """
                MATCH (a:Agent {org_id: $org_id, agent_id: $agent_id})
                DETACH DELETE a
            """,
                org_id=org_id,
                agent_id=agent_id,
            )

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            await session.execute_write(delete_agent_tx)
            self.logger.info(f"Successfully deleted agent {agent_id}")

    @override
    async def get_agent(self, org_id: str, agent_id: str) -> models.Agent:
        """
        Gets a specific agent belonging to the specified organization from the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_id (str): Short UUID string identifying the agent to retrieve.

        Returns:
            Agent containing:

                + org_id: Short UUID string
                + user_id: Optional Short UUID string
                + agent_id: Short UUID string
                + agent_label: Agent label/name
                + created_at: DateTime object of when the agent was created
        """

        async def get_agent_tx(tx):
            result = await tx.run(
                """
                MATCH (a:Agent {org_id: $org_id, agent_id: $agent_id})
                RETURN a{.org_id, .user_id, .agent_id, .agent_label, .created_at} as agent
            """,
                org_id=org_id,
                agent_id=agent_id,
            )
            record = await result.single()
            return record["agent"] if record else None

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            agent_data = await session.execute_read(get_agent_tx)

            if agent_data is None:
                self.logger.info(
                    f"Failed to get agent {agent_id}: Agent does not exist"
                )
                raise neo4j.exceptions.Neo4jError(
                    "Agent (`org_id`, `agent_id`) does not exist."
                )

            return models.Agent(
                org_id=agent_data["org_id"],
                agent_id=agent_data["agent_id"],
                user_id=agent_data.get("user_id"),
                agent_label=agent_data["agent_label"],
                created_at=(agent_data["created_at"]).to_native(),
            )

    @override
    async def get_all_org_agents(self, org_id: str) -> List[models.Agent]:
        """
        Gets all agents belonging to the specified organization from the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.

        Returns:
            A List[Agent], each containing:

                + org_id: Short UUID string
                + user_id: Optional Short UUID string
                + agent_id: Short UUID string
                + agent_label: Agent label/name
                + created_at: DateTime object of when the agent was created
        """

        if not isinstance(org_id, str) or not org_id:
            raise ValueError("`org_id` must be a string and have a value.")

        self.logger.info(f"Getting all agents for organization {org_id}")

        async def get_org_agents_tx(tx):
            result = await tx.run(
                """
                MATCH (o:Org {org_id: $org_id})-[:HAS_AGENT]->(a:Agent)
                RETURN a{.org_id, .user_id, .agent_id, .agent_label, .created_at} as agent
            """,
                org_id=org_id,
            )
            records = await result.value("agent", [])
            return records

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            all_agents_data = await session.execute_read(get_org_agents_tx)

            return [
                models.Agent(
                    org_id=agent_data["org_id"],
                    agent_id=agent_data["agent_id"],
                    user_id=agent_data.get("user_id"),
                    agent_label=agent_data["agent_label"],
                    created_at=(agent_data["created_at"]).to_native(),
                )
                for agent_data in all_agents_data
            ]

    @override
    async def get_all_user_agents(
        self, org_id: str, user_id: str
    ) -> List[models.Agent]:
        """
        Gets all agents for a user within an organization from the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user.

        Returns:
            A List[Agent], each containing:

                + org_id: Short UUID string
                + user_id: Optional Short UUID string
                + agent_id: Short UUID string
                + agent_label: Agent label/name
                + created_at: DateTime object of when the agent was created
        """

        if not all(param and isinstance(param, str) for param in (org_id, user_id)):
            raise ValueError("`org_id` and `user_id` must be strings and have a value.")

        self.logger.info(
            f"Getting all agents for user {user_id} in organization {org_id}"
        )

        async def get_user_agents_tx(tx):
            result = await tx.run(
                """
                MATCH (u:User {org_id: $org_id, user_id: $user_id})-[:HAS_AGENT]->(a:Agent)
                RETURN a{.org_id, .user_id, .agent_id, .agent_label, .created_at} as agent
            """,
                org_id=org_id,
                user_id=user_id,
            )
            records = await result.value("agent", [])
            return records

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            all_agents_data = await session.execute_read(get_user_agents_tx)

            return [
                models.Agent(
                    org_id=agent_data["org_id"],
                    agent_id=agent_data["agent_id"],
                    user_id=agent_data.get("user_id"),
                    agent_label=agent_data["agent_label"],
                    created_at=(agent_data["created_at"]).to_native(),
                )
                for agent_data in all_agents_data
            ]
