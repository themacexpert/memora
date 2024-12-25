from datetime import datetime
import re
from typing import Dict, List, Optional
from dotenv import load_dotenv

from memora.graph_db.base import BaseGraphDB
from memora.llm_backends.azure_openai_backend_llm import AzureOpenAIBackendLLM
from memora.llm_backends.base import BaseBackendLLM
from memora.llm_backends.together_backend_llm import TogetherBackendLLM
from memora.prompts.filter_retrieved_memories import FILTER_RETRIEVED_MEMORIES_SYSTEM_PROMPT
from memora.prompts.memory_extraction import COMPARE_EXISTING_AND_NEW_MEMORIES_PROMPT_TEMPLATE, COMPARE_EXISTING_AND_NEW_MEMORIES_SYSTEM_PROMPT, MEMORY_EXTRACTION_SYSTEM_PROMPT, UPDATED_MEMORY_EXTRACTION_UPDATE_SYSTEM_PROMPT
from memora.prompts.memory_search_from_msg import MSG_MEMORY_SEARCH_PROMPT, MSG_MEMORY_SEARCH_TEMPLATE
from memora.schema.extraction_schema import EXTRACTION_MSG_BLOCK_FORMAT, ExtractionMemoryResponse, MemoryComparisonUpdateResponse
from memora.schema.save_memory_schema import ContraryMemory, MemoriesAndInteraction, MemoryToStore
from memora.vector_db.base import BaseVectorDB, MemorySearchScope

# Load the .env file
load_dotenv()

class Memora:
    """
    Memora is a memory agent for AI, designed to replicate the capabilities of human memory. 
    It enables AI to recall and connect context from past interactions, empowering it to provide 
    precise, context-aware responses in real-time. From retaining text-based context today 
    to a future of full-spectrum memory—audio, video, and emotions—Memora is the next step 
    in transforming human-AI interaction.
    """

    def __init__(
            self,
            vector_db: BaseVectorDB,
            graph_db: BaseGraphDB,
            memory_search_model: BaseBackendLLM = TogetherBackendLLM(
                model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                max_tokens=512, max_retries=0),
            extraction_model: BaseBackendLLM = AzureOpenAIBackendLLM(
                model="gpt-4o-standard",
                max_tokens=8000, max_retries=0),
            ):

        self.memory_search_model = memory_search_model
        self.extraction_model = extraction_model
        self.vector_db = vector_db
        self.graph = graph_db

    async def close(self):
        """Close and clean up resources used by Memora."""

        await self.vector_db.close()
        await self.graph.close()
        await self.memory_search_model.close()
        await self.extraction_model.close()

    async def _get_memory_search_queries(self, 
                                    user_name: str,
                                    agent_label: str,
                                    current_datetime_iso_str: str,
                                    message: Dict[str, str], 
                                    preceding_messages_for_context: Optional[List[Dict[str, str]]] = []
                                   ) -> List[str]:
        
        '''Given a message, the user's name, agent's label and preceding messages for context (optional), returns a list of needed memory
        search queries.'''

        current_day_of_week = datetime.fromisoformat(current_datetime_iso_str).strftime('%A')
        response = await self.memory_search_model(
            messages=[
                {
                    "role": "system",
                    "content": MSG_MEMORY_SEARCH_PROMPT.format(
                        agent_label=agent_label,
                        agent_placeholder=self.agent_placeholder,
                        user_placeholder=self.user_placeholder,
                        user_name=user_name
                    )
                },
                {
                    "role": "user",
                    "content": MSG_MEMORY_SEARCH_TEMPLATE.format(
                        day_of_week=current_day_of_week,
                        current_datetime_str=current_datetime_iso_str,
                        message_of_user=str(message),
                        preceding_messages="\n".join([str(msg) for msg in preceding_messages_for_context])
                    )
                },
                { "role": "assistant", "content": "&& MEMORY_SEARCH &&" } # For Guided Response.
            ])
            
        arguments_pattern = re.compile(r'<<(.*?)>>', re.DOTALL)
        arguments_passed = arguments_pattern.findall(response)

        # Initialize arguments list
        arguments_passed = [arg.strip() for arg in arguments_passed] if arguments_passed else []

        return arguments_passed

    async def _filter_retrieved_memories_with_final_model(self,
                                    current_datetime_iso_str: str,
                                    message: Dict[str, str], 
                                    search_queries_used: List[str],
                                    retrieved_memories: List[Dict[str, str]],
                                   ) -> List[str]:
        """Returns Selected memory_ids, or empty list [] if none was selected and None if the LLM was unable to analyze and extract."""
        
        current_day_of_week = datetime.fromisoformat(current_datetime_iso_str).strftime('%A')
        response = await self.memory_search_model(
            messages=[
                {
                    "role": "system",
                    "content": FILTER_RETRIEVED_MEMORIES_SYSTEM_PROMPT.format(
                        day_of_week=current_day_of_week,
                        current_datetime_str=current_datetime_iso_str,
                        latest_room_message=str(message),
                        search_queries="\n- ".join(search_queries_used)
                    )
                },
                {"role": "user", "content": str(retrieved_memories)},
                { "role": "assistant", "content": "REASONS AND JUST memory_id enclosed in (<< >>):\n- Reason: " } # For Guided Response.
            ])
            
        selected_id_pattern = re.compile(r'<<(.*?)>>', re.DOTALL)
        selected_memories_ids = selected_id_pattern.findall(response)

        if not selected_memories_ids: # The LLM misbehaved not extracting any ids or << NONE >>.
            return None
        else:
            selected_memories_ids = [str(selection).strip() for selection in selected_memories_ids if str(selection).strip().lower() is not "none"]
            return selected_memories_ids

    async def search_memories_as_one(self, org_id: str, user_id: str, search_queries: List[str], agent_id: Optional[str] = None, memories_across_agents: bool = True)-> List[Dict[str, str]]:
        """Retrieves memories corresponding to the search queries for a message."""

        batch_results = await self.vector_db.search_memories(
            queries=search_queries,
            memory_search_scope=MemorySearchScope.USER,
            org_id=org_id,
            user_id=user_id,
            agent_id=agent_id if not memories_across_agents else None
        )

        memory_ids: List[str] = [memory['memory_id'] for result in batch_results for memory in result]

        if not memory_ids:
            return []
        
        resolved_memories: List[Dict[str, str]] = await self.graph.fetch_user_memories_resolved(
            org_id, 
            user_id, 
            memory_ids)

        return resolved_memories
    
    async def search_memories_as_batch(self, org_id: str, search_queries: List[str], user_id: Optional[str] = None, agent_id: Optional[str] = None, memory_search_scope: MemorySearchScope = MemorySearchScope.USER, memories_across_agents: bool = True)-> List[List[Dict[str, str]]]:
        """Retrieves memories corresponding to a list of search queries."""

        batch_results = await self.vector_db.search_memories(
            queries=search_queries,
            memory_search_scope=memory_search_scope,
            org_id=org_id,
            user_id=user_id,
            agent_id=agent_id if not memories_across_agents else None
        )

        batch_memory_ids: List[List[str]] = [[memory['memory_id'] for memory in result] for result in batch_results]

        if not any(batch_memory_ids):
            return []
        
        resolved_memories: List[List[Dict[str, str]]] = await self.graph.fetch_user_memories_resolved_batch(
            org_id, 
            user_id, 
            batch_memory_ids)

        return resolved_memories
    
    async def save_interaction_and_memories(
        self,
        org_id: str,
        user_id: str,
        agent_id: str,
        interaction: List[Dict[str, str]],
        current_datetime_str: str = datetime.now().isoformat(),
        extract_agent_memories: bool = False,
        update_across_agents: bool = True,
        max_retries: int = 0
    ):

        for retry in range(max_retries+1):
            try:
                current_day_of_week = datetime.fromisoformat(current_datetime_str).strftime('%A')

                user = await self.graph.get_user(org_id, user_id)
                agent = await self.graph.get_agent(org_id, agent_id)

                if not user:
                    raise Exception(f"User with ID {user_id} not found in the database.")
                if not agent:
                    raise Exception(f"Agent with ID {agent_id} not found in the database.")
                
                # We will store memories using placeholder so it is unaffected by future changes of a user's name or agent's label.
                user_placeholder = f"user_{user['user_id']}"
                agent_placeholder = f"agent_{agent['agent_id']}"

                system_content = MEMORY_EXTRACTION_SYSTEM_PROMPT.format(
                    day_of_week=current_day_of_week,
                    current_datetime_str=current_datetime_str,
                    agent_label=agent['agent_label'],
                    user_name=user['user_name'],
                    extract_for_agent=f'and {agent['agent_label']}' if extract_agent_memories else '',
                    schema=ExtractionMemoryResponse.model_json_schema()
                )

                messages = [{"role": "system", "content": system_content}]

                messages += [
                    {
                        'role': msg['role'], 
                        'content': EXTRACTION_MSG_BLOCK_FORMAT.format(message_id=i, content=msg['content'])
                    }
                    for i, msg in enumerate(interaction)
                ]

                response : ExtractionMemoryResponse = await self.extraction_model(messages=messages, output_schema_model=ExtractionMemoryResponse)

                # Get every memory extracted, their source messages and insert placeholders for user and agent.
                candidate_memories: List[str] = []
                candidate_memories_msg_ids: List[List[int]] = []

                for memory_list in (response.memories_first_pass or [],
                                        response.memories_second_pass or [],
                                        response.memories_third_pass or []):
                    for memory in memory_list:
                        memory_text = memory.memory.replace('#user_#id#', user_placeholder).replace('#agent_#id#', agent_placeholder)
                        candidate_memories.append(memory_text)
                        candidate_memories_msg_ids.append(memory.message_ids)



                if candidate_memories:
                    existing_memories = await self.search_memories_as_one(
                        org_id=org_id,
                        user_id=user_id,
                        search_queries=candidate_memories,
                        agent_id=agent_id,
                        memories_across_agents=update_across_agents
                    )

                    if not existing_memories:
                        interaction_id = await self.graph.save_interaction_with_memories(
                            org_id,
                            agent_id,
                            user_id,
                            memories_and_interaction=MemoriesAndInteraction(
                                interaction=interaction, 
                                interaction_date=datetime.fromisoformat(current_datetime_str),
                                memories=[MemoryToStore(memory=memory, source_message_block_pos=source_msgs) for memory, source_msgs in zip(candidate_memories, candidate_memories_msg_ids)]
                                ),
                            vector_db_add_memories_fn=self.vector_db.add_memories
                        )
                        return interaction_id
                    else:

                        candidate_memories = [{'memory': memory, 'POS_ID': i} for i, memory in enumerate(candidate_memories)]
                        messages = [
                            {
                                "role": "system", 
                                "content": COMPARE_EXISTING_AND_NEW_MEMORIES_SYSTEM_PROMPT.format(
                                day_of_week=current_day_of_week,
                                current_datetime_str=current_datetime_str,
                                agent_placeholder=agent_placeholder,
                                user_placeholder=user_placeholder,
                                schema=MemoryComparisonUpdateResponse.model_json_schema()
                            )},
                            {
                                'role': "user", 
                                'content': COMPARE_EXISTING_AND_NEW_MEMORIES_PROMPT_TEMPLATE.format(
                                    existing_memories_string = str(existing_memories),
                                    new_memories_string = str(candidate_memories)
                                )
                            }
                        ]
                        response : MemoryComparisonUpdateResponse = await self.extraction_model(messages=messages, output_schema_model=MemoryComparisonUpdateResponse)

                        new_memories = []
                        for memory in response.new_memories:
                            try:
                                new_memories.append((memory.memory, candidate_memories_msg_ids[memory.source_candidate_pos_id]))
                            except: continue

                        new_contradictory_memories = []
                        for memory in response.contradictory_memories:
                            try:
                                new_contradictory_memories.append((memory.memory, candidate_memories_msg_ids[memory.source_candidate_pos_id], memory.contradicted_memory_id))
                            except: continue

                        interaction_id = await self.graph.save_interaction_with_memories(
                            org_id,
                            agent_id,
                            user_id,
                            memories_and_interaction=MemoriesAndInteraction(
                                interaction=interaction, 
                                interaction_date=datetime.fromisoformat(current_datetime_str),
                                memories=[MemoryToStore(memory=memory_tuple[0], source_message_block_pos=memory_tuple[1]) for memory_tuple in new_memories],
                                contrary_memories=[ContraryMemory(memory=memory_tuple[0], source_message_block_pos=memory_tuple[1], existing_contradicted_memory_id=memory_tuple[2]) for memory_tuple in new_contradictory_memories]
                                ),
                            vector_db_add_memories_fn=self.vector_db.add_memories
                        )

                        return interaction_id
                        
            except Exception as e:
                if retry == max_retries:
                    raise Exception(f"Failed to save interaction memories: {e}")
                else:
                    continue

    
    async def update_interaction_and_memories(
        self,
        org_id: str,
        user_id: str,
        agent_id: str,
        interaction_id: str,
        updated_interaction: List[Dict[str, str]],
        current_datetime_str: str = datetime.now().isoformat(),
        extract_agent_memories: bool = False,
        update_across_agents: bool = True,
        max_retries: int = 0
    ):

        for retry in range(max_retries+1):
            try:
                current_day_of_week = datetime.fromisoformat(current_datetime_str).strftime('%A')

                user = await self.graph.get_user(org_id, user_id)
                agent = await self.graph.get_agent(org_id, agent_id)
                previously_extracted_memories: List[Dict[str, str]] = await self.graph.get_all_interaction_memories(org_id, user_id, interaction_id)

                if not user:
                    raise Exception(f"User with ID {user_id} not found in the database.")
                if not agent:
                    raise Exception(f"Agent with ID {agent_id} not found in the database.")
                
                # We will store memories using placeholder so it is unaffected by future changes of a user's name or agent's label.
                user_placeholder = f"user_{user['user_id']}"
                agent_placeholder = f"agent_{agent['agent_id']}"

                system_content = UPDATED_MEMORY_EXTRACTION_UPDATE_SYSTEM_PROMPT.format(
                    day_of_week=current_day_of_week,
                    current_datetime_str=current_datetime_str,
                    agent_label=agent['agent_label'],
                    user_name=user['user_name'],
                    extract_for_agent=f'and {agent['agent_label']}' if extract_agent_memories else '',
                    previous_memories=str(previously_extracted_memories),
                    schema=ExtractionMemoryResponse.model_json_schema()
                )

                messages = [{"role": "system", "content": system_content}]

                messages += [
                    {
                        'role': msg['role'], 
                        'content': EXTRACTION_MSG_BLOCK_FORMAT.format(message_id=i, content=msg['content'])
                    }
                    for i, msg in enumerate(updated_interaction)
                ]

                response : ExtractionMemoryResponse = await self.extraction_model(messages=messages, output_schema_model=ExtractionMemoryResponse)

                # Get every memory extracted, their source messages and insert placeholders for user and agent.
                candidate_memories: List[str] = []
                candidate_memories_msg_ids: List[List[int]] = []

                for memory_list in (response.memories_first_pass or [],
                                        response.memories_second_pass or [],
                                        response.memories_third_pass or []):
                    for memory in memory_list:
                        memory_text = memory.memory.replace('#user_#id#', user_placeholder).replace('#agent_#id#', agent_placeholder)
                        candidate_memories.append(memory_text)
                        candidate_memories_msg_ids.append(memory.message_ids)



                if candidate_memories:
                    existing_memories = await self.search_memories_as_one(
                        org_id=org_id,
                        user_id=user_id,
                        search_queries=candidate_memories,
                        agent_id=agent_id,
                        memories_across_agents=update_across_agents
                    )

                    if not existing_memories:
                        interaction_id, updated_time = await self.graph.update_interaction_and_memories(
                            org_id,
                            agent_id,
                            user_id,
                            interaction_id,
                            updated_memories_and_interaction=MemoriesAndInteraction(
                                interaction=updated_interaction, 
                                interaction_date=datetime.fromisoformat(current_datetime_str),
                                memories=[MemoryToStore(memory=memory, source_message_block_pos=source_msgs) for memory, source_msgs in zip(candidate_memories, candidate_memories_msg_ids)]
                                ),
                            vector_db_add_memories_fn=self.vector_db.add_memories
                        )
                        return interaction_id, updated_time
                    else:

                        candidate_memories = [{'memory': memory, 'POS_ID': i} for i, memory in enumerate(candidate_memories)]
                        messages = [
                            {
                                "role": "system", 
                                "content": COMPARE_EXISTING_AND_NEW_MEMORIES_SYSTEM_PROMPT.format(
                                day_of_week=current_day_of_week,
                                current_datetime_str=current_datetime_str,
                                agent_placeholder=agent_placeholder,
                                user_placeholder=user_placeholder,
                                schema=MemoryComparisonUpdateResponse.model_json_schema()
                            )},
                            {
                                'role': "user", 
                                'content': COMPARE_EXISTING_AND_NEW_MEMORIES_PROMPT_TEMPLATE.format(
                                    existing_memories_string = str(existing_memories),
                                    new_memories_string = str(candidate_memories)
                                )
                            }
                        ]
                        response : MemoryComparisonUpdateResponse = await self.extraction_model(messages=messages, output_schema_model=MemoryComparisonUpdateResponse)

                        new_memories = []
                        for memory in response.new_memories:
                            try:
                                new_memories.append((memory.memory, candidate_memories_msg_ids[memory.source_candidate_pos_id]))
                            except: continue

                        new_contradictory_memories = []
                        for memory in response.contradictory_memories:
                            try:
                                new_contradictory_memories.append((memory.memory, candidate_memories_msg_ids[memory.source_candidate_pos_id], memory.contradicted_memory_id))
                            except: continue

                        interaction_id, updated_time = await self.graph.update_interaction_and_memories(
                            org_id,
                            agent_id,
                            user_id,
                            interaction_id,
                            updated_memories_and_interaction=MemoriesAndInteraction(
                                interaction=updated_interaction, 
                                interaction_date=datetime.fromisoformat(current_datetime_str),
                                memories=[MemoryToStore(memory=memory_tuple[0], source_message_block_pos=memory_tuple[1]) for memory_tuple in new_memories],
                                contrary_memories=[ContraryMemory(memory=memory_tuple[0], source_message_block_pos=memory_tuple[1], existing_contradicted_memory_id=memory_tuple[2]) for memory_tuple in new_contradictory_memories]
                                ),
                            vector_db_add_memories_fn=self.vector_db.add_memories
                        )

                        return interaction_id, updated_time
                        
            except Exception as e:
                if retry == max_retries:
                    raise Exception(f"Failed to save interaction memories: {e}")
                else:
                    continue

    
    
    async def get_memories_for_message(
        self, 
        org_id: str,
        user_id: str,  
        latest_msg: Dict[str, str], 
        agent_id: Optional[str] = None,
        preceding_msg_for_context: Optional[List[Dict[str, str]]] = [], 
        current_datetime_str: str = datetime.now().isoformat(),
        search_memories_across_agents: bool = True,
        enable_final_model_based_memory_filter: bool = True,
        ):
        """Returns the memories needed to respond or act on message(s)."""

        memory_search_queries: List[str] = await self._get_memory_search_queries(current_datetime_str, latest_msg, preceding_msg_for_context)
        
        if memory_search_queries:
            retrieved_memories = await self.search_memories_as_one(org_id, user_id, memory_search_queries, agent_id, search_memories_across_agents)
            
            if not enable_final_model_based_memory_filter:
                return retrieved_memories
            else:
                # Filter memories based on final model's output.
                filtered_memories_ids = await self._filter_retrieved_memories_with_final_model(current_datetime_str, latest_msg, memory_search_queries, retrieved_memories)

                if filtered_memories_ids is None: # The LLM was unable to filter just needed memories.
                    return retrieved_memories
                elif len(filtered_memories_ids) == 0: # The LLM filtered out all memories (deemed none are needed to be recalled).
                    return None
                else:
                    # First put retrieved memory in a dictionary so we can picked the filtered selected ones.
                    memory_dict = {memoryObj["memory_id"]: memoryObj for memoryObj in retrieved_memories}
                    selected_memories = [memoryObj for memory_id in filtered_memories_ids if (memoryObj := memory_dict.get(memory_id)) is not None]
                    return selected_memories
        else:
            return None
        
