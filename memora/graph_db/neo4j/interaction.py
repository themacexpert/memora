import uuid
from datetime import datetime
from typing import Dict, List, Tuple

import neo4j
import shortuuid
from typing_extensions import override

from memora.schema import models
from memora.schema.storage_schema import MemoriesAndInteraction

from ..base import BaseGraphDB


class Neo4jInteraction(BaseGraphDB):

    async def _add_messages_to_interaction_from_top(
        self,
        tx,
        org_id: str,
        user_id: str,
        interaction_id: str,
        messages: List[Dict[str, str]],
    ) -> None:
        """Add messages to an interaction from the very top, linking the first message to the interaction."""

        if messages:  # Called only if there are messages to be added.
            await tx.run(
                """
                    MATCH (interaction:Interaction {
                        org_id: $org_id, 
                        user_id: $user_id, 
                        interaction_id: $interaction_id
                    })

                    CREATE (msg1:MessageBlock {msg_position: 0, role: $messages[0].role, content: $messages[0].content})
                    CREATE (interaction)-[:FIRST_MESSAGE]->(msg1)

                    // Step 1: Create the remaining message nodes and collect them in a list.
                    WITH msg1
                    UNWIND RANGE(1, SIZE($messages) - 1) AS idx
                    CREATE (msg:MessageBlock {msg_position: idx, role: $messages[idx].role, content: $messages[idx].content})

                    // Step 2: Create a chain with the messages all connected via IS_NEXT from the first message.
                    WITH msg1, COLLECT(msg) AS nodeList
                    WITH [msg1] + nodeList AS nodeList

                    UNWIND RANGE(1, SIZE(nodeList) - 1) AS idx
                    WITH nodeList[idx] AS currentNode, nodeList[idx - 1] AS previousNode
                    CREATE (previousNode)-[:IS_NEXT]->(currentNode)

                """,
                org_id=org_id,
                user_id=user_id,
                interaction_id=interaction_id,
                messages=messages,
            )

    async def _append_messages_to_interaction(
        self,
        tx,
        org_id: str,
        user_id: str,
        interaction_id: str,
        messages: List[Dict[str, str]],
    ) -> None:
        """Finds the last message in the interaction and links (append) this chain of new messages to it."""

        await tx.run(
            """
                    // Find the last message in the interaction.
                    MATCH p=(interaction: Interaction {org_id: $org_id, user_id: $user_id, interaction_id: $interaction_id})-[r:FIRST_MESSAGE|IS_NEXT*]->(m:MessageBlock)
                    WHERE NOT (m)-[:IS_NEXT]->()

                    // Create the update messages from truncation point.
                    UNWIND RANGE(m.msg_position+1, SIZE($messages) - 1) AS idx
                    CREATE (msg:MessageBlock {msg_position: idx, role: $messages[idx].role, content: $messages[idx].content})

                    // Create a chain with the update messages all connected via IS_NEXT.
                    WITH m, COLLECT(msg) AS nodeList
                    WITH [m] + nodeList AS nodeList
                    UNWIND RANGE(1, SIZE(nodeList) - 1) AS idx
                    WITH nodeList[idx] AS currentNode, nodeList[idx - 1] AS previousNode
                    CREATE (previousNode)-[:IS_NEXT]->(currentNode)
                """,
            org_id=org_id,
            user_id=user_id,
            interaction_id=interaction_id,
            messages=messages,
        )

    async def _truncate_interaction_message_below_point(
        self,
        tx,
        org_id: str,
        user_id: str,
        interaction_id: str,
        truncation_point_inclusive: int,
    ) -> None:
        """
        Will truncate every message in an interaction below the given truncation point.

        Note:
            - `truncation_point_inclusive` is zero indexed and inclusive so `truncation_point_inclusive = n` will start deleting from the message at `nth` position.
            - Setting `truncation_point_inclusize` to 0 will delete all messages of the interaction.

        Raises:
            ValueError: When `truncation_point_inclusive` is < 0 (Less than Zero).
        """

        if truncation_point_inclusive == 0:
            # Delete every message in the interaction:
            await tx.run(
                """
                MATCH (interaction: Interaction {org_id: $org_id, user_id: $user_id, interaction_id: $interaction_id})-[r:FIRST_MESSAGE|IS_NEXT*]->(m:MessageBlock)
                DETACH DELETE m
            """,
                org_id=org_id,
                user_id=user_id,
                interaction_id=interaction_id,
            )

        elif truncation_point_inclusive > 0:
            # Delete all messages in the interaction below the truncation point.
            await tx.run(
                f"""
                MATCH (interaction: Interaction {{org_id: $org_id, user_id: $user_id, interaction_id: $interaction_id}})-[r:FIRST_MESSAGE|IS_NEXT*{truncation_point_inclusive}]->(m:MessageBlock)
                MATCH (m)-[:IS_NEXT*]->(n)
                DETACH DELETE n
            """,
                org_id=org_id,
                user_id=user_id,
                interaction_id=interaction_id,
            )

        else:
            raise ValueError(
                "`truncation_point_inclusive` should be > 0 (Greater than Zero)."
            )

    async def _add_memories_with_their_source_links(
        self,
        tx,
        org_id: str,
        user_id: str,
        agent_id: str,
        interaction_id: str,
        memories_and_interaction: MemoriesAndInteraction,
        new_memory_ids: List[str],
        new_contrary_memory_ids: List[str],
    ) -> None:
        """Add all memories and link to their source message and interaction."""

        await tx.run(
            """
                // Retrieve all messages in the interaction, and the users memory collection.
                MATCH (interaction: Interaction {org_id: $org_id, user_id: $user_id, interaction_id: $interaction_id})-[r:FIRST_MESSAGE|IS_NEXT*]->(m:MessageBlock)
                MATCH (user:User {org_id: $org_id, user_id: $user_id})-[:HAS_MEMORIES]->(mc)
                MATCH (date:Date {org_id: $org_id, user_id: $user_id, date: date(datetime($interaction_date))})

                WITH collect(m) as messages, interaction, mc, date

                // Create the memory nodes.
                UNWIND $memories_and_source as memory_tuple
                CREATE (memory:Memory {
                    org_id: $org_id, 
                    user_id: $user_id, 
                    agent_id: $agent_id,
                    interaction_id: $interaction_id, 
                    memory_id: memory_tuple[0],  
                    memory: memory_tuple[1], 
                    obtained_at: datetime($interaction_date)
                })
                
                // Link to interaction
                CREATE (interaction)<-[:INTERACTION_SOURCE]-(memory)

                // Link to user's memory collection
                CREATE (mc)-[:INCLUDES]->(memory)

                // Link to date
                CREATE (memory)-[:DATE_OBTAINED]->(date)

                // For each memory, Link to it's source message in the interaction.
                WITH memory, memory_tuple[2] as all_memory_source_msg_pos, messages
                UNWIND all_memory_source_msg_pos as source_msg_pos

                WITH messages[source_msg_pos] as message_node, memory
                CREATE (message_node)<-[:MESSAGE_SOURCE]-(memory)

            """,
            org_id=org_id,
            user_id=user_id,
            agent_id=agent_id,
            interaction_id=interaction_id,
            interaction_date=memories_and_interaction.interaction_date.isoformat(),
            memories_and_source=[
                (memory_id, memory_obj.memory, memory_obj.source_msg_block_pos)
                for memory_id, memory_obj in zip(
                    (new_memory_ids + new_contrary_memory_ids),  # All memory ids
                    (
                        memories_and_interaction.memories
                        + memories_and_interaction.contrary_memories
                    ),  # All memories
                )
            ],
        )

    async def _link_update_contrary_memories_to_existing_memories(
        self,
        tx,
        org_id: str,
        user_id: str,
        new_contrary_memory_ids: List[str],
        memories_and_interaction: MemoriesAndInteraction,
    ) -> None:
        """Link the new contary memories as updates to the old memory they contradicted."""

        await tx.run(
            """
                UNWIND $contrary_and_existing_ids as contrary_and_existing_id_tuple
                MATCH (new_contrary_memory:Memory {org_id: $org_id, user_id: $user_id, memory_id: contrary_and_existing_id_tuple[0]})
                MATCH (old_memory:Memory {org_id: $org_id, user_id: $user_id, memory_id: contrary_and_existing_id_tuple[1]})
                
                MERGE (new_contrary_memory)<-[:CONTRARY_UPDATE]-(old_memory)

            """,
            org_id=org_id,
            user_id=user_id,
            contrary_and_existing_ids=[
                (contrary_memory_id, contrary_memory_obj.existing_contrary_memory_id)
                for contrary_memory_id, contrary_memory_obj in zip(
                    new_contrary_memory_ids, memories_and_interaction.contrary_memories
                )
            ],
        )

    @override
    async def save_interaction_with_memories(
        self,
        org_id: str,
        agent_id: str,
        user_id: str,
        memories_and_interaction: MemoriesAndInteraction,
    ) -> Tuple[str, datetime]:
        """
        Creates a new interaction record with associated memories.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_id (str): Short UUID string identifying the agent.
            user_id (str): Short UUID string identifying the user.
            memories_and_interaction (MemoriesAndInteraction): Contains both the interaction and the associated memories.

        Note:
            If the graph database is associated with a vector database, the memories are also stored there for data consistency.

        Returns:
            Tuple[str, datetime] containing:

                + interaction_id: Short UUID string identifying the created interaction
                + created_at: DateTime object of when the interaction was created.
        """

        if not all(
            param and isinstance(param, str) for param in (org_id, user_id, agent_id)
        ):
            raise ValueError(
                "`org_id`, `user_id` and `agent_id` must be strings and have a value."
            )

        interaction_id = shortuuid.uuid()
        new_memory_ids = [
            str(uuid.uuid4()) for _ in range(len(memories_and_interaction.memories))
        ]
        new_contrary_memory_ids = [
            str(uuid.uuid4())
            for _ in range(len(memories_and_interaction.contrary_memories))
        ]

        self.logger.info(
            f"Saving interaction {interaction_id} for user {user_id} with agent {agent_id}"
        )

        async def save_tx(tx):

            # Create interaction and connect to date of occurance.
            await tx.run(
                """
                MATCH (u:User {org_id: $org_id, user_id: $user_id})-[:INTERACTIONS_IN]->(ic)
                CREATE (interaction:Interaction {
                    org_id: $org_id,
                    user_id: $user_id,
                    agent_id: $agent_id,
                    interaction_id: $interaction_id,
                    created_at: datetime($interaction_date),
                    updated_at: datetime($interaction_date)
                })
                CREATE (ic)-[:HAD_INTERACTION]->(interaction)

                WITH interaction, u
                MERGE (d:Date {
                    org_id: $org_id,
                    user_id: $user_id,
                    date: date(datetime($interaction_date))
                })
                CREATE (interaction)-[:HAS_OCCURRENCE_ON]->(d)

            """,
                org_id=org_id,
                user_id=user_id,
                agent_id=agent_id,
                interaction_id=interaction_id,
                interaction_date=memories_and_interaction.interaction_date.isoformat(),
            )

            if not memories_and_interaction.interaction:
                self.logger.info(
                    f"No messages to save for interaction {interaction_id}"
                )
                return (
                    interaction_id,
                    memories_and_interaction.interaction_date.isoformat(),
                )

            # Add the messages to the interaction.
            self.logger.info(f"Adding messages to interaction {interaction_id}")
            await self._add_messages_to_interaction_from_top(
                tx,
                org_id,
                user_id,
                interaction_id,
                memories_and_interaction.interaction,
            )

            if new_memory_ids or new_contrary_memory_ids:
                # Add the all memories (new & new contrary) and connect to their interaction message source.
                self.logger.info("Adding memories and linking to their message source")
                await self._add_memories_with_their_source_links(
                    tx,
                    org_id,
                    user_id,
                    agent_id,
                    interaction_id,
                    memories_and_interaction,
                    new_memory_ids,
                    new_contrary_memory_ids,
                )

            if new_contrary_memory_ids:
                # Link the new contary memories as updates to the old memory they contradicted.
                self.logger.info(
                    "Linking contrary memories to existing memories they contradicted"
                )
                await self._link_update_contrary_memories_to_existing_memories(
                    tx,
                    org_id,
                    user_id,
                    new_contrary_memory_ids,
                    memories_and_interaction,
                )

            if new_memory_ids or new_contrary_memory_ids:
                if (
                    self.associated_vector_db
                ):  # If the graph database is associated with a vector database
                    # Add memories to vector DB within this transcation function to ensure data consistency (They succeed or fail together).
                    await self.associated_vector_db.add_memories(
                        org_id=org_id,
                        user_id=user_id,
                        agent_id=agent_id,
                        memory_ids=(
                            new_memory_ids + new_contrary_memory_ids
                        ),  # All memory ids
                        memories=[
                            memory_obj.memory
                            for memory_obj in (
                                memories_and_interaction.memories
                                + memories_and_interaction.contrary_memories
                            )
                        ],  # All memories
                        obtained_at=memories_and_interaction.interaction_date.isoformat(),
                    )

            return interaction_id, memories_and_interaction.interaction_date

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            result = await session.execute_write(save_tx)
            self.logger.info(
                f"Successfully saved interaction {interaction_id} for user {user_id}"
            )
            return result

    @override
    async def update_interaction_and_memories(
        self,
        org_id: str,
        agent_id: str,
        user_id: str,
        interaction_id: str,
        updated_memories_and_interaction: MemoriesAndInteraction,
    ) -> Tuple[str, datetime]:
        """
        Update an existing interaction record and add new memories.

        Compares updated interaction with existing one:
            - If differences are found, truncates existing record from that point and
            replaces with updated version. Old memories from truncated message(s)
            remain but become standalone (no longer linked to truncated messages).
            - If no differences, appends new messages from the update.

        New memories are always added, regardless of interaction changes.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_id (str): Short UUID string identifying the agent in the updated interaction.
            user_id (str): Short UUID string identifying the user.
            interaction_id (str): Short UUID string identifying the interaction to update.
            updated_memories_and_interaction (MemoriesAndInteraction): Contains both the updated interaction and the associated new memories.

        Note:
            If the graph database is associated with a vector database, the memories are also stored there for data consistency.

        Returns:
            Tuple[str, datetime] containing:

                + interaction_id: Short UUID string identifying the updated interaction
                + updated_at: DateTime object of when the interaction was last updated.
        """

        if not all(
            param and isinstance(param, str) for param in (org_id, user_id, agent_id)
        ):
            raise ValueError(
                "`org_id`, `user_id` and `agent_id` must be strings and have a value."
            )

        self.logger.info(
            f"Updating interaction {interaction_id} for user {user_id} with agent {agent_id}"
        )

        new_memory_ids = [
            str(uuid.uuid4())
            for _ in range(len(updated_memories_and_interaction.memories))
        ]
        new_contrary_memory_ids = [
            str(uuid.uuid4())
            for _ in range(len(updated_memories_and_interaction.contrary_memories))
        ]

        # First get the existing messages.
        existing_messages: List[models.MessageBlock] = (
            await self.get_interaction(
                org_id, user_id, interaction_id, with_messages=True, with_memories=False
            )
        ).messages

        updated_interaction_length = len(updated_memories_and_interaction.interaction)
        existing_interaction_length = len(existing_messages)

        async def update_tx(tx):

            # Case 1: Empty updated interaction - delete all existing messages
            if updated_interaction_length == 0:
                self.logger.info(
                    f"Truncating all messages from interaction {interaction_id} as updated interaction is empty"
                )
                await self._truncate_interaction_message_below_point(
                    tx, org_id, user_id, interaction_id, truncation_point_inclusive=0
                )

            # Case 2: Empty existing interaction - add all new messages from the top
            elif existing_interaction_length == 0:
                self.logger.info(f"Adding all messages to interaction {interaction_id}")
                await self._add_messages_to_interaction_from_top(
                    tx,
                    org_id,
                    user_id,
                    interaction_id,
                    updated_memories_and_interaction.interaction,
                )

            # Case 3: Both interactions have messages - compare and update
            else:
                # Find first point of difference
                truncate_from = -1
                for i in range(
                    min(existing_interaction_length, updated_interaction_length)
                ):
                    if (
                        existing_messages[i].role
                        != updated_memories_and_interaction.interaction[i].get("role")
                    ) or (
                        existing_messages[i].content
                        != updated_memories_and_interaction.interaction[i].get(
                            "content"
                        )
                    ):
                        truncate_from = i
                        break

                # If no differences found in prefix messages, but updated interaction is shorter
                if (
                    truncate_from == -1
                    and updated_interaction_length < existing_interaction_length
                ):
                    truncate_from = updated_interaction_length

                # Handle different cases based on where the difference was found
                if truncate_from == -1:
                    # Append the new messages at the bottom.
                    self.logger.info(
                        f"Appending new messages to interaction {interaction_id}"
                    )
                    await self._append_messages_to_interaction(
                        tx,
                        org_id,
                        user_id,
                        interaction_id,
                        updated_memories_and_interaction.interaction,
                    )

                elif truncate_from == 0:
                    # Complete replacement needed
                    self.logger.info(
                        f"Storing latest interaction {interaction_id} messages"
                    )
                    await self._truncate_interaction_message_below_point(
                        tx,
                        org_id,
                        user_id,
                        interaction_id,
                        truncation_point_inclusive=0,
                    )
                    await self._add_messages_to_interaction_from_top(
                        tx,
                        org_id,
                        user_id,
                        interaction_id,
                        updated_memories_and_interaction.interaction,
                    )

                elif truncate_from > 0:
                    # Partial replacement needed
                    self.logger.info(
                        f"Updating messages in interaction {interaction_id} from position {truncate_from}"
                    )
                    await self._truncate_interaction_message_below_point(
                        tx, org_id, user_id, interaction_id, truncate_from
                    )
                    await self._append_messages_to_interaction(
                        tx,
                        org_id,
                        user_id,
                        interaction_id,
                        updated_memories_and_interaction.interaction,
                    )

            if new_memory_ids or new_contrary_memory_ids:
                self.logger.info("Adding memories and linking to their source messages")
                await self._add_memories_with_their_source_links(
                    tx,
                    org_id,
                    user_id,
                    agent_id,
                    interaction_id,
                    updated_memories_and_interaction,
                    new_memory_ids,
                    new_contrary_memory_ids,
                )

            if new_contrary_memory_ids:
                self.logger.info(
                    "Linking contrary memories to existing memories they contradicted"
                )
                await self._link_update_contrary_memories_to_existing_memories(
                    tx,
                    org_id,
                    user_id,
                    new_contrary_memory_ids,
                    updated_memories_and_interaction,
                )

            # Update the interaction agent, updated_at datetime, and connect occurance to the particular date.
            await tx.run(
                """
                MATCH (i:Interaction {
                    org_id: $org_id,
                    user_id: $user_id,
                    interaction_id: $interaction_id
                })
                SET i.updated_at = datetime($updated_date), i.agent_id = $agent_id
                MERGE (d:Date {
                    org_id: $org_id,
                    user_id: $user_id,
                    date: date(datetime($updated_date))
                })
                MERGE (i)-[:HAS_OCCURRENCE_ON]->(d)
            """,
                org_id=org_id,
                user_id=user_id,
                agent_id=agent_id,
                interaction_id=interaction_id,
                updated_date=updated_memories_and_interaction.interaction_date.isoformat(),
            )

            if new_memory_ids or new_contrary_memory_ids:
                if self.associated_vector_db:
                    # If the graph database is associated with a vector database
                    # Add memories to vector DB within this transcation function to ensure data consistency (They succeed or fail together).
                    await self.associated_vector_db.add_memories(
                        org_id=org_id,
                        user_id=user_id,
                        agent_id=agent_id,
                        memory_ids=(
                            new_memory_ids + new_contrary_memory_ids
                        ),  # All memory ids
                        memories=[
                            memory_obj.memory
                            for memory_obj in (
                                updated_memories_and_interaction.memories
                                + updated_memories_and_interaction.contrary_memories
                            )
                        ],  # All memories
                        obtained_at=updated_memories_and_interaction.interaction_date.isoformat(),
                    )

            return (
                interaction_id,
                updated_memories_and_interaction.interaction_date,
            )

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            result = await session.execute_write(update_tx)
            self.logger.info(f"Successfully updated interaction {interaction_id}")
            return result

    @override
    async def get_interaction(
        self,
        org_id: str,
        user_id: str,
        interaction_id: str,
        with_messages: bool = True,
        with_memories: bool = True,
    ) -> models.Interaction:
        """
        Retrieves all messages associated with a specific interaction.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user.
            interaction_id (str): Short UUID string identifying the interaction.
            with_messages (bool): Whether to retrieve messages along with the interaction.
            with_memories (bool): Whether to also retrieve memories gotten across all occurrences of this interaction.

        Returns:
            Interaction containing:

                + org_id: Short UUID string identifying the organization.
                + user_id: Short UUID string identifying the user.
                + agent_id: Short UUID string identifying the agent.
                + interaction_id: Short UUID string identifying the interaction.
                + created_at: DateTime object of when the interaction was created.
                + updated_at: DateTime object of when the interaction was last updated.
                + messages (if `with_messages` = True): List of messages in the interaction.
                + memories (if `with_memories` = True): List of memories gotten from all occurrences of this interaction.

        Note:
            A memory won't have a message source, if its interaction was updated with a conflicting conversation thread that lead to truncation of the former thread. See `graph.update_interaction_and_memories`
        """

        if not all(
            param and isinstance(param, str)
            for param in (org_id, user_id, interaction_id)
        ):
            raise ValueError(
                "`org_id`, `user_id` and `interaction_id` must be strings and have a value."
            )

        self.logger.info(
            f"Retrieving interaction {interaction_id} for user {user_id} with messages={with_messages} and memories={with_memories}"
        )

        async def get_interaction_tx(tx):

            query = """
                MATCH (interaction: Interaction {
                    org_id: $org_id, 
                    user_id: $user_id, 
                    interaction_id: $interaction_id
                })

                // Initialize messages/memories upfront
                WITH interaction, [] AS messages, [] AS memories
            """

            if with_messages:
                query += """
                OPTIONAL MATCH (interaction)-[:FIRST_MESSAGE|IS_NEXT*]->(m:MessageBlock)
                WITH interaction, collect(m{.*}) as messages, memories
                """

            if with_memories:
                query += """
                OPTIONAL MATCH (interaction)<-[:INTERACTION_SOURCE]-(mem:Memory)
                OPTIONAL MATCH (mem)-[:MESSAGE_SOURCE]->(msg)

                WITH interaction, messages, mem, collect(msg{.*}) AS msg_sources

                OPTIONAL MATCH (user:User {org_id: mem.org_id, user_id: mem.user_id})              
                OPTIONAL MATCH (agent:Agent {org_id: mem.org_id, agent_id: mem.agent_id})

                WITH interaction, messages, collect(mem{
                                                        .*, 
                                                        memory: apoc.text.replace(
                                                            apoc.text.replace(mem.memory, '(?i)user_[a-z0-9\\-]+(?:\\'s)?', user.user_name), 
                                                            '(?i)agent_[a-z0-9\\-]+(?:\\'s)?',  agent.agent_label
                                                        ),
                                                        message_sources: msg_sources
                                                        }) as memories
                """

            query += """
                RETURN interaction{
                    .org_id,
                    .user_id,
                    .agent_id,
                    .interaction_id,
                    .created_at,
                    .updated_at,
                    messages: messages,
                    memories: memories
                } as interaction
            """

            result = await tx.run(
                query,
                org_id=org_id,
                user_id=user_id,
                interaction_id=interaction_id,
            )

            record = await result.single()
            return record["interaction"] if record else None

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            interaction_data = await session.execute_read(get_interaction_tx)

            if interaction_data is None:
                self.logger.info(
                    f"Interaction {interaction_id} not found for user {user_id}"
                )
                raise neo4j.exceptions.Neo4jError(
                    "Interaction (`org_id`, `user_id`, `interaction_id`) does not exist."
                )

            return models.Interaction(
                org_id=interaction_data["org_id"],
                user_id=interaction_data["user_id"],
                agent_id=interaction_data["agent_id"],
                interaction_id=interaction_data["interaction_id"],
                created_at=(interaction_data["created_at"]).to_native(),
                updated_at=(interaction_data["updated_at"]).to_native(),
                messages=[
                    models.MessageBlock(
                        role=message.get("role"),
                        content=message.get("content"),
                        msg_position=message["msg_position"],
                    )
                    for message in (interaction_data.get("messages") or [])
                ],
                memories=[
                    models.Memory(
                        org_id=memory["org_id"],
                        agent_id=memory["agent_id"],
                        user_id=memory["user_id"],
                        interaction_id=memory["interaction_id"],
                        memory_id=memory["memory_id"],
                        memory=memory["memory"],
                        obtained_at=(memory["obtained_at"]).to_native(),
                        message_sources=[
                            models.MessageBlock(
                                role=msg.get("role"),
                                content=msg.get("content"),
                                msg_position=msg["msg_position"],
                            )
                            for msg in (memory.get("message_sources") or [])
                        ],
                    )
                    for memory in (interaction_data.get("memories") or [])
                ],
            )

    @override
    async def get_all_user_interactions(
        self,
        org_id: str,
        user_id: str,
        with_their_messages: bool = True,
        with_their_memories: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> List[models.Interaction]:
        """
        Retrieves all interactions for a specific user in an organization.

        Note:
            Interactions are sorted in descending order by their updated at datetime. (So most recent interactions are first).

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user.
            with_their_messages (bool): Whether to also retrieve messages of an interaction.
            with_their_memories (bool): Whether to also retrieve memories gotten across all occurrences of an interaction.
            skip (int): Number of interactions to skip. (Useful for pagination)
            limit (int): Maximum number of interactions to retrieve. (Useful for pagination)

        Returns:
            List[Interaction], each containing an Interaction with:

                + org_id: Short UUID string identifying the organization.
                + user_id: Short UUID string identifying the user.
                + agent_id: Short UUID string identifying the agent.
                + interaction_id: Short UUID string identifying the interaction.
                + created_at: DateTime object of when the interaction was created.
                + updated_at: DateTime object of when the interaction was last updated.
                + messages (if `with_their_messages` = True): List of messages in the interaction.
                + memories (if `with_their_memories` = True): List of memories gotten from all occurrences of this interaction.

        Note:
            A memory won't have a message source, if its interaction was updated with a conflicting conversation thread that lead to truncation of the former thread. See `graph.update_interaction_and_memories`
        """

        if not all(param and isinstance(param, str) for param in (org_id, user_id)):
            raise ValueError("`org_id` and `user_id` must be strings and have a value.")

        if not all(isinstance(param, int) for param in (skip, limit)):
            raise ValueError("`skip` and `limit` must be integers.")

        self.logger.info(
            f"Retrieving all interactions for user {user_id} with messages={with_their_messages} and memories={with_their_memories}"
        )

        async def get_interactions_tx(tx):

            query = """
                // Cleverly transverse through dates to get interactions sorted, avoiding having to sort all user interaction nodes.
                MATCH (d:Date {org_id: $org_id, user_id: $user_id})
                WITH d ORDER BY d.date DESC
                CALL (d) {
                    MATCH (d)<-[:HAS_OCCURRENCE_ON]-(interaction)
                    RETURN interaction ORDER BY interaction.updated_at DESC
                }
                WITH DISTINCT interaction SKIP $skip LIMIT $limit

                // Initialize messages/memories upfront
                WITH interaction, [] AS messages, [] AS memories 
            """

            if with_their_messages:
                query += """
                OPTIONAL MATCH (interaction)-[:FIRST_MESSAGE|IS_NEXT*]->(m:MessageBlock)
                WITH interaction, collect(m{.*}) as messages, memories
                """

            if with_their_memories:
                query += """
                OPTIONAL MATCH (interaction)<-[:INTERACTION_SOURCE]-(mem:Memory)
                OPTIONAL MATCH (mem)-[:MESSAGE_SOURCE]->(msg)

                WITH interaction, messages, mem, collect(msg{.*}) AS msg_sources
                
                OPTIONAL MATCH (user:User {org_id: mem.org_id, user_id: mem.user_id})              
                OPTIONAL MATCH (agent:Agent {org_id: mem.org_id, agent_id: mem.agent_id})

                WITH interaction, messages, collect(mem{
                                                        .*, 
                                                        memory: apoc.text.replace(
                                                            apoc.text.replace(mem.memory, '(?i)user_[a-z0-9\\-]+(?:\\'s)?', user.user_name), 
                                                            '(?i)agent_[a-z0-9\\-]+(?:\\'s)?',  agent.agent_label
                                                        ),
                                                        message_sources: msg_sources
                                                        }) as memories
                """

            query += """
                RETURN interaction{
                    .org_id,
                    .user_id,
                    .agent_id,
                    .interaction_id,
                    .created_at,
                    .updated_at,
                    messages: messages,
                    memories: memories
                } as interaction
            """

            result = await tx.run(
                query, org_id=org_id, user_id=user_id, skip=skip, limit=limit
            )

            records = await result.value("interaction", [])
            return records

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            all_interactions_data = await session.execute_read(get_interactions_tx)

            return [
                models.Interaction(
                    org_id=interaction_data["org_id"],
                    user_id=interaction_data["user_id"],
                    agent_id=interaction_data["agent_id"],
                    interaction_id=interaction_data["interaction_id"],
                    created_at=(interaction_data["created_at"]).to_native(),
                    updated_at=(interaction_data["updated_at"]).to_native(),
                    messages=[
                        models.MessageBlock(
                            role=message.get("role"),
                            content=message.get("content"),
                            msg_position=message["msg_position"],
                        )
                        for message in (interaction_data.get("messages") or [])
                    ],
                    memories=[
                        models.Memory(
                            org_id=memory["org_id"],
                            agent_id=memory["agent_id"],
                            user_id=memory["user_id"],
                            interaction_id=memory["interaction_id"],
                            memory_id=memory["memory_id"],
                            memory=memory["memory"],
                            obtained_at=(memory["obtained_at"]).to_native(),
                            message_sources=[
                                models.MessageBlock(
                                    role=msg.get("role"),
                                    content=msg.get("content"),
                                    msg_position=msg["msg_position"],
                                )
                                for msg in (memory.get("message_sources") or [])
                            ],
                        )
                        for memory in (interaction_data.get("memories") or [])
                    ],
                )
                for interaction_data in all_interactions_data
            ]

    @override
    async def delete_user_interaction_and_its_memories(
        self,
        org_id: str,
        user_id: str,
        interaction_id: str,
    ) -> None:
        """
        Deletes an interaction record and its associated memories.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user.
            interaction_id (str): Short UUID string identifying the interaction to delete.

        Note:
            If the graph database is associated with a vector database, the memories are also deleted there for data consistency.
        """

        if not all(
            param and isinstance(param, str)
            for param in (org_id, user_id, interaction_id)
        ):
            raise ValueError(
                "`org_id`, `user_id` and `interaction_id` must be strings and have a value."
            )

        self.logger.info(
            f"Deleting interaction {interaction_id} and its memories for user {user_id}"
        )

        interaction_memories = (
            await self.get_interaction(
                org_id, user_id, interaction_id, with_messages=False, with_memories=True
            )
        ).memories

        interaction_memories_ids = [memory.memory_id for memory in interaction_memories]

        async def delete_tx(tx):
            # Delete the interaction, its messages and memories.
            await tx.run(
                """
                MATCH (interaction: Interaction {
                    org_id: $org_id, 
                    user_id: $user_id, 
                    interaction_id: $interaction_id
                    })-[r:FIRST_MESSAGE|IS_NEXT*]->(message:MessageBlock)

                OPTIONAL MATCH (interaction)<-[:INTERACTION_SOURCE]-(memory)
                OPTIONAL MATCH (interaction)-[:HAS_OCCURRENCE_ON]->(date:Date) WHERE NOT (date)<-[:HAS_OCCURRENCE_ON]-()

                DETACH DELETE interaction, message, memory, date
            """,
                org_id=org_id,
                user_id=user_id,
                interaction_id=interaction_id,
            )

            if (
                self.associated_vector_db and interaction_memories_ids
            ):  # If the graph database is associated with a vector database
                # Delete memories from vector DB.
                await self.associated_vector_db.delete_memories(
                    interaction_memories_ids
                )

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            await session.execute_write(delete_tx)

    @override
    async def delete_all_user_interactions_and_their_memories(
        self,
        org_id: str,
        user_id: str,
    ) -> None:
        """
        Deletes all interactions and their associated memories for a specific user in an organization.

        Args:
            org_id (str): Short UUID string identifying the organization
            user_id (str): Short UUID string identifying the user whose interactions should be deleted

        Note:
            If the graph database is associated with a vector database, the memories are also deleted there for data consistency.
        """

        if not all(param and isinstance(param, str) for param in (org_id, user_id)):
            raise ValueError("`org_id` and `user_id` must be strings and have a value.")

        self.logger.info(f"Deleting all interactions and memories for user {user_id}")

        async def delete_all_tx(tx):
            await tx.run(
                """
                MATCH (u:User {org_id: $org_id, user_id: $user_id})-[:INTERACTIONS_IN]->(ic)-[:HAD_INTERACTION]->(interaction:Interaction)
                
                OPTIONAL MATCH (interaction)<-[:INTERACTION_SOURCE]-(memory:Memory)
                OPTIONAL MATCH (interaction)-[:HAS_OCCURRENCE_ON]->(date:Date)
                OPTIONAL MATCH (interaction)-[:FIRST_MESSAGE|IS_NEXT*]->(messages:MessageBlock)

                DETACH DELETE interaction, memory, date, messages
            """,
                org_id=org_id,
                user_id=user_id,
            )

            if (
                self.associated_vector_db
            ):  # If the graph database is associated with a vector database
                self.logger.info(
                    f"Deleting all memories from vector database for user {user_id}"
                )
                await self.associated_vector_db.delete_all_user_memories(
                    org_id, user_id
                )

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            await session.execute_write(delete_all_tx)
            self.logger.info(
                f"Successfully deleted all interactions and memories for user {user_id}"
            )
