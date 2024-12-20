import os
from typing_extensions import override
import uuid
import shortuuid
import neo4j
from neo4j import AsyncDriver
from datetime import datetime
from typing import Dict, List, Tuple, Callable, Awaitable

from memora.schema.save_memory_schema import MemoriesAndInteraction

from ..base import BaseGraphDB


class Neo4jInteraction(BaseGraphDB):

    @override
    async def save_interaction_with_memories(
        self,
        org_id: str,
        agent_id: str, 
        user_id: str,
        memories_and_interaction: MemoriesAndInteraction,
        vector_db_add_memories_fn: Callable[..., Awaitable[None]]
    ) -> str:
        
        interaction_id = shortuuid.uuid()
        new_memory_ids = [str(uuid.uuid4()) for _ in len(memories_and_interaction.memories)]
        new_contrary_memory_ids = [str(uuid.uuid4()) for _ in len(memories_and_interaction.contrary_memories)]

        async def save_tx(tx):

            # Create interaction with its messages.
            await tx.run("""
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

                CREATE (msg1:MessageBlock {org_id: $org_id, user_id: $user_id, msg_position: 0, role: $messages[0].role, content: $messages[0].content})
                CREATE (interaction)-[:FIRST_MESSAGE]->(msg1)

                // Step 1: Create the remaining message nodes and collect them in a list.
                WITH msg1
                UNWIND RANGE(1, SIZE($messages) - 1) AS idx
                CREATE (msg:MessageBlock {org_id: $org_id, user_id: $user_id, msg_position: idx, role: $messages[idx].role, content: $messages[idx].content})

                // Step 2: Create a chain with the messages all connected via IS_NEXT from the first message.
                WITH msg1, COLLECT(msg) AS nodeList
                WITH [msg1] + nodeList AS nodeList

                UNWIND RANGE(1, SIZE(nodeList) - 1) AS idx
                WITH nodeList[idx] AS currentNode, nodeList[idx - 1] AS previousNode
                CREATE (previousNode)-[:IS_NEXT]->(currentNode)

            """, org_id=org_id, user_id=user_id, agent_id=agent_id,
            interaction_id=interaction_id, 
            interaction_date=memories_and_interaction.interaction_date.isoformat(),
            messages=memories_and_interaction.interaction)


            # Add the all memories (new & new contrary) and connect to their interaction message source.
            await tx.run("""
                // Retrieve all messages in the interaction.
                MATCH (interaction: Interaction {org_id: $org_id, user_id: $user_id, interaction_id: $interaction_id})-[r:FIRST_MESSAGE|IS_NEXT*]->(m:Message_Block)
                WITH collect(m) as messages, interaction

                // Create the memory nodes.
                UNWIND $memories_and_source as memory_tuple
                CREATE (memory:Memory {
                    org_id: $org_id, 
                    user_id: $user_id, 
                    agent_id: $agent_id,
                    interaction_id: $interaction_id, 
                    memory_id: memory_tuple[0],  
                    memory: memory_tuple[1], 
                    obtained_at: datetime($interaction_date), 
                    has_contrary_update: false
                })
                
                // Link to interaction
                CREATE (interaction)<-[:INTERACTION_SOURCE]-(memory)

                // For each memory, Link to it's source message in the interaction.
                WITH memory, memory_tuple[2] as all_memory_source_msg_pos, messages
                UNWIND all_memory_source_msg_pos as source_msg_pos

                WITH messages[source_msg_pos] as message_node, memory
                CREATE (message_node)<-[:MESSAGE_SOURCE]-(memory)

            """, org_id=org_id, user_id=user_id, agent_id=agent_id,
            interaction_id=interaction_id,
            interaction_date=memories_and_interaction.interaction_date.isoformat(),
            memories_and_source=[
                    (memory_id, memory_obj.memory, memory_obj.source_message_block_pos) 
                    for memory_id, memory_obj in 
                    zip(
                        (new_memory_ids + new_contrary_memory_ids), # All memory ids
                        (memories_and_interaction.memories + memories_and_interaction.contrary_memories) # All memories
                    )
                ]
            )


            # Link the new contary memories as updates to the old memory they contradicted.
            await tx.run("""
                UNWIND $contrary_and_existing_ids as contrary_and_existing_id_tuple
                MATCH (new_contrary_memory:Memory {org_id: $org_id, user_id: $user_id, memory_id: contrary_and_existing_id_tuple[0]})
                MATCH (old_memory:Memory {org_id: $org_id, user_id: $user_id, memory_id: contrary_and_existing_id_tuple[1]})
                
                SET old_memory.has_contrary_update = true
                CREATE (new_contrary_memory)<-[:CONTRARY_UPDATE]-(old_memory)

            """, org_id=org_id, user_id=user_id,
                contrary_and_existing_ids=[
                        (contrary_memory_id, contrary_memory_obj.existing_contradicted_memory_id) 
                        for contrary_memory_id, contrary_memory_obj in 
                        zip(new_contrary_memory_ids, memories_and_interaction.contrary_memories)
                    ]
            )
            
            return interaction_id

        async with self.driver.session(database=self.database, default_access_mode=neo4j.WRITE_ACCESS) as session:
            return await session.execute_write(save_tx)

