from typing import Dict, List, Optional

import neo4j
from typing_extensions import override

from memora.schema import models

from ..base import BaseGraphDB


class Neo4jMemory(BaseGraphDB):

    @override
    async def fetch_user_memories_resolved(
        self, org_user_mem_ids: List[Dict[str, str]]
    ) -> List[models.Memory]:
        """
        Fetches memories from the Neo4j GraphDB by their IDs, resolves any contrary updates, and replaces user/agent placeholders with actual names.

        This method performs several operations:
          1. Retrieves memories using (org_id, user_id, memory_ids)
          2. If a memory has a CONTRARY_UPDATE relationship, uses the newer memory version
          3. Replaces user_id & agent_id placeholders (e.g 'user_abc123' or 'agent_xyz789') in memories with actual user names / agent labels

        Args:
            org_user_mem_ids (List[Dict[str, str]]): List of Dicts containing org, user, and memory ids of the memories to fetch and process

        Returns:
            List[Memory] containing memory details:

                + org_id: Short UUID string identifying the organization
                + agent_id: Short UUID string identifying the agent
                + user_id: Short UUID string identifying the user
                + interaction_id: Short UUID string identifying the interaction the memory was sourced from
                + memory_id: Full UUID string identifying the memory
                + memory: The resolved memory
                + obtained_at: DateTime object of when the memory was obtained
                + message_sources: List of messages in the interaction that triggered the memory

        Example:
            ```python
            >>> org_user_mem_ids = [{'memory_id': '443ac3a8-fe87-49a4-93d2-05d3eb58ddeb', 'org_id': 'gmDr4sUiWMNqbGAiV8ijbU', 'user_id': 'CcyKXxhi2skEcDpRzNZim7'}, ...]
            >>> memories = graphInstance.fetch_memories_resolved(org_user_mem_ids)
            >>> print([memoryObj.memory for memoryObj in memories])
            ["John asked for help with a wedding ring", "Sarah is allergic to peanuts"]
            ```

        Note:
            - Org, user, and memory IDs are typically retrieved from a vector database before being passed to this method.
            - A memory won't have a message source, if its interaction was updated with a conflicting conversation thread that lead to truncation of the former thread. See `graph.update_interaction_and_memories`
        """

        results = await self.fetch_user_memories_resolved_batch([org_user_mem_ids])
        return results[0]

    @override
    async def fetch_user_memories_resolved_batch(
        self, batch_org_user_mem_ids: List[List[Dict[str, str]]]
    ) -> List[List[models.Memory]]:
        """
        Fetches memories from the Neo4j GraphDB by their IDs, resolves any contrary updates, and replaces user/agent placeholders with actual names.

        This method performs several operations:
          1. Retrieves memories using (org_id, user_id, memory_ids)
          2. If a memory has a CONTRARY_UPDATE relationship, uses the newer memory version
          3. Replaces user_id & agent_id placeholders (e.g 'user_abc123' or 'agent_xyz789') in memories with actual user names / agent labels

        Args:
            batch_org_user_mem_ids (List[List[Dict[str, str]]]): List of lists containing Dicts with org, user, and memory ids of the memories to fetch and process

        Returns:
            List[List[Memory]] with memory details:

                + org_id: Short UUID string identifying the organization
                + agent_id: Short UUID string identifying the agent
                + user_id: Short UUID string identifying the user
                + interaction_id: Short UUID string identifying the interaction the memory was sourced from
                + memory_id: Full UUID string identifying the memory
                + memory: The resolved memory
                + obtained_at: DateTime object of when the memory was obtained
                + message_sources: List of messages in the interaction that triggered the memory

        Example:
            ```python
            >>> batch_org_user_mem_ids = [[{"memory_id": "413ac3a8-fe87-49a4-93d2-05d3eb58ddeb", "org_id": "gmDr4sUiWMNqbGAiV8ijbU", "user_id": "CcyKXxhi2skEcDpRzNZim7"}, ...], [{...}, ...]]
            >>> batch_memories = graphInstance.fetch_memories_resolved_batch(batch_org_user_mem_ids)
            >>> print([[memoryObj.memory for memoryObj in memories] for memories in batch_memories])
            [["John asked for help with a wedding ring", "Sarah is allergic to peanuts"], ["John is about to propose to Sarah"]]
            ```

        Note:
            - Batch org, user, and memory IDs are typically retrieved from a vector database before being passed to this method.
            - A memory won't have a message source, if its interaction was updated with a conflicting conversation thread that lead to truncation of the former thread. See `graph.update_interaction_and_memories`
        """

        async def fetch_resolved_batch_tx(tx):
            result = await tx.run(
                """
                UNWIND $batch_ids AS ids_dict_list

                CALL (ids_dict_list) {

                    UNWIND ids_dict_list AS ids_dict
                    MATCH (memory:Memory {org_id: ids_dict.org_id, user_id: ids_dict.user_id, memory_id: ids_dict.memory_id})
                                  
                    // Use the most up to date contrary update memory if it exists
                    OPTIONAL MATCH (memory)-[:CONTRARY_UPDATE*]->(contraryMemory:Memory) WHERE NOT (contraryMemory)-[:CONTRARY_UPDATE]->()
                    WITH coalesce(contraryMemory, memory) AS memoryToReturn

                    OPTIONAL MATCH (memoryToReturn)-[:MESSAGE_SOURCE]->(msgSource)
                    WITH memoryToReturn, collect(msgSource{.*}) as msgSources
                                  
                    MATCH (user:User {org_id: memoryToReturn.org_id, user_id: memoryToReturn.user_id})              
                    MATCH (agent:Agent {org_id: memoryToReturn.org_id, agent_id: memoryToReturn.agent_id})
                                  
                    // Case-insensitive 'user_' or 'agent_' followed by UUID and optional ('s) placeholders are replaced with actual names
                    RETURN collect(DISTINCT memoryToReturn{
                                                .org_id,
                                                .agent_id,
                                                .user_id,
                                                .interaction_id,
                                                .memory_id, 
                                                .obtained_at,
                                                memory: apoc.text.replace(
                                                    apoc.text.replace(memoryToReturn.memory, '(?i)user_[a-z0-9\\-]+(?:\\'s)?', user.user_name), 
                                                    '(?i)agent_[a-z0-9\\-]+(?:\\'s)?',  agent.agent_label
                                                ),
                                                message_sources: msgSources
                                            }) as resolved_memories
                }
                RETURN resolved_memories

            """,
                batch_ids=batch_org_user_mem_ids,
            )

            records = await result.value("resolved_memories", [])
            return records

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:

            all_resolved_memories = await session.execute_read(fetch_resolved_batch_tx)

            return [
                [
                    models.Memory(
                        org_id=resolved_memory["org_id"],
                        agent_id=resolved_memory["agent_id"],
                        user_id=resolved_memory["user_id"],
                        interaction_id=resolved_memory["interaction_id"],
                        memory_id=resolved_memory["memory_id"],
                        memory=resolved_memory["memory"],
                        obtained_at=(resolved_memory["obtained_at"]).to_native(),
                        message_sources=[
                            models.MessageBlock(
                                role=msg_source["role"],
                                content=msg_source["content"],
                                msg_position=msg_source["msg_position"],
                            )
                            for msg_source in (resolved_memory["message_sources"] or [])
                        ],
                    )
                    for resolved_memory in resolved_memories
                ]
                for resolved_memories in all_resolved_memories
            ]

    @override
    async def get_user_memory(
        self, org_id: str, user_id: str, memory_id: str
    ) -> models.Memory:
        """
        Retrieves a specific memory.

        Args:
            org_id (str): Short UUID string identifying the organization
            user_id (str): Short UUID string identifying the user
            memory_id (str): UUID string identifying the memory

        Returns:
            Memory containing memory details:

                + org_id: Short UUID string identifying the organization
                + agent_id: Short UUID string identifying the agent
                + user_id: Short UUID string identifying the user
                + interaction_id: Short UUID string identifying the interaction the memory was sourced from
                + memory_id: Full UUID string identifying the memory
                + memory: The resolved memory
                + obtained_at: DateTime object of when the memory was obtained
                + message_sources: List of messages in the interaction that triggered the memory

        Note:
            - The memory won't have a message source, if its interaction was updated with a conflicting conversation thread that lead to truncation of the former thread. See `graph.update_interaction_and_memories`
        """

        if not all(
            param and isinstance(param, str) for param in (org_id, user_id, memory_id)
        ):
            raise ValueError(
                "`org_id`, `user_id` and `memory_id` must be strings and have a value."
            )

        self.logger.info(f"Getting memory {memory_id} for user {user_id}")

        async def get_memory_tx(tx):
            result = await tx.run(
                """
                MATCH (m:Memory {org_id: $org_id, user_id: $user_id, memory_id: $memory_id})

                MATCH (m)-[:MESSAGE_SOURCE]->(msgSource)
                WITH m, collect(msgSource{.*}) as msgSources

                MATCH (user:User {org_id: m.org_id, user_id: m.user_id})              
                MATCH (agent:Agent {org_id: m.org_id, agent_id: m.agent_id})
                RETURN m{
                        .org_id,
                        .agent_id,
                        .user_id,
                        .interaction_id,
                        .memory_id, 
                        .obtained_at,
                        memory: apoc.text.replace(
                            apoc.text.replace(m.memory, '(?i)user_[a-z0-9\\-]+(?:\\'s)?', user.user_name), 
                            '(?i)agent_[a-z0-9\\-]+(?:\\'s)?',  agent.agent_label
                        ),
                        message_sources: msgSources
                    } as memory
            """,
                org_id=org_id,
                user_id=user_id,
                memory_id=memory_id,
            )
            record = await result.single()
            return record["memory"] if record else None

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            memory = await session.execute_read(get_memory_tx)

            if not memory:
                self.logger.info(
                    f"Failed to get memory {memory_id}: Memory does not exist"
                )
                raise neo4j.exceptions.Neo4jError(
                    "Memory (`org_id`, `user_id`, `memory_id`) does not exist."
                )

            return models.Memory(
                org_id=memory["org_id"],
                agent_id=memory["agent_id"],
                user_id=memory["user_id"],
                interaction_id=memory["interaction_id"],
                memory_id=memory["memory_id"],
                memory=memory["memory"],
                obtained_at=(memory["obtained_at"]).to_native(),
                message_sources=[
                    models.MessageBlock(
                        role=msg_source["role"],
                        content=msg_source["content"],
                        msg_position=msg_source["msg_position"],
                    )
                    for msg_source in (memory["message_sources"] or [])
                ],
            )

    @override
    async def get_user_memory_history(
        self, org_id: str, user_id: str, memory_id: str
    ) -> List[models.Memory]:
        """
        Retrieves the history of a specific memory.

        Args:
            org_id (str): Short UUID string identifying the organization
            user_id (str): Short UUID string identifying the user
            memory_id (str): UUID string identifying the memory

        Returns:
            List[Memory] containing the history of memory details in descending order (starting with the current version, to the oldest version):

                + org_id: Short UUID string identifying the organization
                + agent_id: Short UUID string identifying the agent
                + user_id: Short UUID string identifying the user
                + interaction_id: Short UUID string identifying the interaction the memory was sourced from
                + memory_id: Full UUID string identifying the memory
                + memory: The resolved memory
                + obtained_at: DateTime object of when the memory was obtained
                + message_sources: List of messages in the interaction that triggered the memory

        Note:
            - A memory won't have a message source, if its interaction was updated with a conflicting conversation thread that lead to truncation of the former thread. See `graph.update_interaction_and_memories`
        """

        if not all(
            param and isinstance(param, str) for param in (org_id, user_id, memory_id)
        ):
            raise ValueError(
                "`org_id`, `user_id` and `memory_id` must be strings and have a value."
            )

        self.logger.info(f"Getting memory history for memory {memory_id}")

        async def get_memory_history_tx(tx):
            result = await tx.run(
                """
                MATCH path=(m:Memory {org_id: $org_id, user_id: $user_id, memory_id: $memory_id})<-[:CONTRARY_UPDATE*0..]-(olderMemory:Memory)
                WHERE NOT (olderMemory)<-[:CONTRARY_UPDATE]-()
                WITH nodes(path) AS memory_history
                UNWIND memory_history AS memory

                OPTIONAL MATCH (memory)-[:MESSAGE_SOURCE]->(msgSource)
                WITH memory, collect(msgSource{.*}) as msgSources

                MATCH (user:User {org_id: memory.org_id, user_id: memory.user_id})              
                MATCH (agent:Agent {org_id: memory.org_id, agent_id: memory.agent_id})
                RETURN memory{
                        .org_id,
                        .agent_id,
                        .user_id,
                        .interaction_id,
                        .memory_id, 
                        .obtained_at,
                        memory: apoc.text.replace(
                            apoc.text.replace(memory.memory, '(?i)user_[a-z0-9\\-]+(?:\\'s)?', user.user_name), 
                            '(?i)agent_[a-z0-9\\-]+(?:\\'s)?',  agent.agent_label
                        ),
                        message_sources: msgSources
                    } as memory
            """,
                org_id=org_id,
                user_id=user_id,
                memory_id=memory_id,
            )
            records = await result.value("memory", [])
            return records

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            memory_history = await session.execute_read(get_memory_history_tx)
            return [
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
                            role=msg_source["role"],
                            content=msg_source["content"],
                            msg_position=msg_source["msg_position"],
                        )
                        for msg_source in (memory["message_sources"] or [])
                    ],
                )
                for memory in memory_history
            ]

    @override
    async def get_all_user_memories(
        self,
        org_id: str,
        user_id: str,
        agent_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 1000,
    ) -> List[models.Memory]:
        """
        Retrieves all memories associated with a specific user.

        Note:
            Memories are sorted in descending order by their obtained at datetime. (So most recent memories are first).

        Args:
            org_id (str): Short UUID string identifying the organization
            user_id (str): Short UUID string identifying the user
            agent_id (Optional[str]): Optional short UUID string identifying the agent. If provided, only memories obtained from
                interactions with this agent are returned.
                Otherwise, all memories associated with the user are returned.
            skip (int): Number of interactions to skip. (Useful for pagination)
            limit (int): Maximum number of interactions to retrieve. (Useful for pagination)

        Returns:
            List[Memory] containing memory details:

                + org_id: Short UUID string identifying the organization
                + agent_id: Short UUID string identifying the agent
                + user_id: Short UUID string identifying the user
                + interaction_id: Short UUID string identifying the interaction the memory was sourced from
                + memory_id: Full UUID string identifying the memory
                + memory: The resolved memory
                + obtained_at: DateTime object of when the memory was obtained
                + message_sources: List of messages in the interaction that triggered the memory

        Note:
            - A memory won't have a message source, if its interaction was updated with a conflicting conversation thread that lead to truncation of the former thread. See `graph.update_interaction_and_memories`
        """

        if not all(param and isinstance(param, str) for param in (org_id, user_id)):
            raise ValueError("`org_id` and `user_id` must be strings and have a value.")

        if agent_id:
            if not isinstance(agent_id, str):
                raise ValueError("`agent_id` must be a string.")

        self.logger.info(f" and agent {agent_id}" if agent_id else "")

        async def get_all_memories_tx(tx):
            query = """
                // Cleverly transverse through dates to get memories sorted, avoiding having to sort all user memory nodes.
                MATCH (d:Date {{org_id: $org_id, user_id: $user_id}})
                WITH d ORDER BY d.date DESC
                CALL (d) {{
                    MATCH (d)<-[:DATE_OBTAINED]-(memory)
                    {agent_filter}
                    RETURN memory ORDER BY memory.obtained_at DESC
                }}

                WITH memory AS m SKIP $skip LIMIT $limit

                OPTIONAL MATCH (m)-[:MESSAGE_SOURCE]->(msgSource)
                WITH m, collect(msgSource{{.*}}) as msgSources

                MATCH (user:User {{org_id: m.org_id, user_id: m.user_id}})
                MATCH (agent:Agent {{org_id: m.org_id, agent_id: m.agent_id}})

                RETURN m{{
                    .org_id,
                    .agent_id,
                    .user_id,
                    .interaction_id,
                    .memory_id, 
                    .obtained_at,
                    memory: apoc.text.replace(
                        apoc.text.replace(m.memory, '(?i)user_[a-z0-9\\-]+(?:\\'s)?', user.user_name), 
                        '(?i)agent_[a-z0-9\\-]+(?:\\'s)?',  agent.agent_label
                    ),
                    message_sources: msgSources
                }} as memory
            """
            agent_filter = "WHERE memory.agent_id = $agent_id" if agent_id else ""
            result = await tx.run(
                query.format(agent_filter=agent_filter),
                org_id=org_id,
                user_id=user_id,
                agent_id=agent_id,
                skip=skip,
                limit=limit,
            )

            records = await result.value("memory", [])
            return records

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            memories = await session.execute_read(get_all_memories_tx)
            return [
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
                            role=msg_source["role"],
                            content=msg_source["content"],
                            msg_position=msg_source["msg_position"],
                        )
                        for msg_source in (memory["message_sources"] or [])
                    ],
                )
                for memory in memories
            ]

    @override
    async def delete_user_memory(
        self,
        org_id: str,
        user_id: str,
        memory_id: str,
    ) -> None:
        """
        Deletes a specific memory.

        Args:
            org_id (str): Short UUID string identifying the organization
            user_id (str): Short UUID string identifying the user
            memory_id (str): UUID string identifying the memory to delete

        Note:
            If the graph database is associated with a vector database, the memory is also deleted there for data consistency.
        """

        if not all(
            param and isinstance(param, str) for param in (org_id, user_id, memory_id)
        ):
            raise ValueError(
                "`org_id`, `user_id` and `memory_id` must be strings and have a value."
            )

        self.logger.info(f"Deleting memory {memory_id}")

        async def delete_memory_tx(tx):
            await tx.run(
                """
                MATCH (m:Memory {org_id: $org_id, user_id: $user_id, memory_id: $memory_id})
                DETACH DELETE m
            """,
                org_id=org_id,
                user_id=user_id,
                memory_id=memory_id,
            )

            if (
                self.associated_vector_db and memory_id
            ):  # If the graph database is associated with a vector database
                # Delete memory from vector DB.
                await self.associated_vector_db.delete_memory(memory_id)

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            await session.execute_write(delete_memory_tx)
            self.logger.info(f"Successfully deleted memory {memory_id}")

    @override
    async def delete_all_user_memories(
        self,
        org_id: str,
        user_id: str,
    ) -> None:
        """
        Deletes all memories of a specific user.

        Args:
            org_id (str): Short UUID string identifying the organization
            user_id (str): Short UUID string identifying the user

        Note:
            If the graph database is associated with a vector database, the memories are also deleted there for data consistency.
        """

        if not all(param and isinstance(param, str) for param in (org_id, user_id)):
            raise ValueError("`org_id` and `user_id` must be strings and have a value.")

        self.logger.info(f"Deleting all memories for user {user_id}")

        async def delete_all_memories_tx(tx):
            await tx.run(
                """
                MATCH (u:User {org_id: $org_id, user_id: $user_id})-[:HAS_MEMORIES]->(mc:MemoryCollection)
                MATCH (mc)-[:INCLUDES]->(memory:Memory)
                DETACH DELETE memory
            """,
                org_id=org_id,
                user_id=user_id,
            )

            if (
                self.associated_vector_db
            ):  # If the graph database is associated with a vector database
                # Delete all memories from vector DB.
                await self.associated_vector_db.delete_all_user_memories(
                    org_id, user_id
                )

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            await session.execute_write(delete_all_memories_tx)
            self.logger.info(f"Successfully deleted all memories for user {user_id}")
