from datetime import datetime
import re
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

from memora.graph_db.base import BaseGraphDB
from memora.llm_backends.azure_openai_backend_llm import AzureOpenAIBackendLLM
from memora.llm_backends.base import BaseBackendLLM
from memora.llm_backends.together_backend_llm import TogetherBackendLLM
from memora.prompts.filter_retrieved_memories import FILTER_RETRIEVED_MEMORIES_SYSTEM_PROMPT
from memora.prompts.memory_extraction import (
    COMPARE_EXISTING_AND_NEW_MEMORIES_INPUT_TEMPLATE,
    COMPARE_EXISTING_AND_NEW_MEMORIES_SYSTEM_PROMPT,
    MEMORY_EXTRACTION_SYSTEM_PROMPT,
    MEMORY_EXTRACTION_UPDATE_SYSTEM_PROMPT
)
from memora.prompts.memory_search_from_msg import MSG_MEMORY_SEARCH_PROMPT, MSG_MEMORY_SEARCH_TEMPLATE
from memora.schema.extraction_schema import EXTRACTION_MSG_BLOCK_FORMAT, MemoryExtractionResponse, MemoryComparisonResponse
from memora.schema.save_memory_schema import ContraryMemory, MemoriesAndInteraction, MemoryToStore
from memora.vector_db.base import BaseVectorDB, MemorySearchScope

# Load environment variables
load_dotenv()

class Memora:
    """
    Memora: A memory agent for AI systems.

    This class is designed to emulate human memory capabilities, allowing AI to recall
    and connect the dot with context from past interactions to give personalized responses.

    Future Scope:
        Expand capabilities to include audio, video, and emotional memories.
    """

    def __init__(
            self,
            vector_db: BaseVectorDB,
            graph_db: BaseGraphDB,
            memory_search_model: BaseBackendLLM = TogetherBackendLLM(
                model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", max_tokens=512, max_retries=0),
            extraction_model: BaseBackendLLM = AzureOpenAIBackendLLM(
                model="gpt-4o-standard", max_tokens=8000, max_retries=0),
            ):
        """
        Initialize the Memora instance.

        Args:
            vector_db (BaseVectorDB): Vector database for efficient memory storage and retrieval.
            graph (BaseGraphDB): Graph database for storing relationships between memories.
            memory_search_model (BaseBackendLLM): Model for memory search queries and Optional final filtering. (default: TogetherBackendLLM).
            extraction_model (BaseBackendLLM): Model for memory extraction operations. (default: AzureOpenAIBackendLLM). 
        """
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

    async def generate_memory_search_queries(self,
                                    message: Dict[str, str], 
                                    preceding_messages_for_context: Optional[List[Dict[str, str]]] = [],
                                    current_datetime: datetime = datetime.now()
                                   ) -> List[str]:
        """
        Generate memory search queries based on the given message and context.

        Args:
            message (Dict[str, str]): The current message.
            preceding_messages_for_context (Optional[List[Dict[str, str]]]): Preceding messages for context.
            current_datetime (datetime): Current datetime.

        Returns:
            List[str]: List of generated memory search queries.
        """
        current_day_of_week = current_datetime.strftime('%A')
        response = await self.memory_search_model(
            messages=[
                { "role": "system", "content": MSG_MEMORY_SEARCH_PROMPT },
                {
                    "role": "user",
                    "content": MSG_MEMORY_SEARCH_TEMPLATE.format(
                        day_of_week=current_day_of_week,
                        current_datetime_str=current_datetime.isoformat(),
                        message_of_user=str(message),
                        preceding_messages=str(preceding_messages_for_context)
                    )
                },
                { "role": "assistant", "content": "&& MEMORY_SEARCH &&" } # For Guided Response.
            ])
            
        arguments_pattern = re.compile(r'<<(.*?)>>', re.DOTALL)
        arguments_passed = arguments_pattern.findall(response)

        return [arg.strip() for arg in arguments_passed] if arguments_passed else []

    async def filter_retrieved_memories_with_model(self,
                                    message: Dict[str, str], 
                                    search_queries_used: List[str],
                                    retrieved_memories: List[Dict[str, str]],
                                    current_datetime: datetime = datetime.now(),
                                   ) -> Optional[List[str]]:
        """
        Filter retrieved memories using the memory search model.

        Args:
            message (Dict[str, str]): The current message.
            search_queries_used (List[str]): List of search queries used.
            retrieved_memories (List[Dict[str, str]]): List of retrieved memories.
            current_datetime (datetime): Current datetime.

        Returns:
            Optional[List[str]]: List of selected memory IDs (that passed the filter), or None if unable to analyze.
        """
        current_day_of_week = current_datetime.strftime('%A')
        response = await self.memory_search_model(
            messages=[
                {
                    "role": "system",
                    "content": FILTER_RETRIEVED_MEMORIES_SYSTEM_PROMPT.format(
                        day_of_week=current_day_of_week,
                        current_datetime_str=current_datetime.isoformat(),
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
        
        return [str(selection).strip() for selection in selected_memories_ids if str(selection).strip().lower() != "none"]

    async def search_memories_as_one(self, org_id: str, user_id: str, search_queries: List[str], agent_id: Optional[str] = None, memories_across_agents: bool = True) -> List[Dict[str, str]]:
        """
        Retrieve memories corresponding to the search queries for a message.

        Args:
            org_id (str): Organization ID.
            user_id (str): User ID.
            search_queries (List[str]): List of search queries.
            agent_id (Optional[str]): Agent ID.
            memories_across_agents (bool): Whether to search memories across all agents.

        Returns:
            List[Dict[str, str]]: List of retrieved memories.
        """
        batch_results = await self.vector_db.search_memories(
            queries=search_queries,
            memory_search_scope=MemorySearchScope.USER,
            org_id=org_id,
            user_id=user_id,
            agent_id=agent_id if not memories_across_agents else None
        )

        memory_ids = [memory['memory_id'] for result in batch_results for memory in result]

        if not memory_ids:
            return []
        
        return await self.graph.fetch_user_memories_resolved(org_id, user_id, memory_ids)
    
    async def search_memories_as_batch(self, org_id: str, search_queries: List[str], user_id: Optional[str] = None, agent_id: Optional[str] = None, memory_search_scope: MemorySearchScope = MemorySearchScope.USER, memories_across_agents: bool = True) -> List[List[Dict[str, str]]]:
        """
        Retrieve memories corresponding to a list of search queries.

        Args:
            org_id (str): Organization ID.
            search_queries (List[str]): List of search queries.
            user_id (Optional[str]): User ID.
            agent_id (Optional[str]): Agent ID.
            memory_search_scope (MemorySearchScope): Scope of memory search.
            memories_across_agents (bool): Whether to search memories across all agents.

        Returns:
            List[List[Dict[str, str]]]: Batch results of retrieved memories.
        """
        batch_results = await self.vector_db.search_memories(
            queries=search_queries,
            memory_search_scope=memory_search_scope,
            org_id=org_id,
            user_id=user_id,
            agent_id=agent_id if not memories_across_agents else None
        )

        batch_memory_ids = [[memory['memory_id'] for memory in result] for result in batch_results]

        if not any(batch_memory_ids):
            return []
        
        return await self.graph.fetch_user_memories_resolved_batch(org_id, user_id, batch_memory_ids)
    
    async def save_or_update_interaction_and_memories(
        self,
        org_id: str,
        user_id: str,
        agent_id: str,
        interaction: List[Dict[str, str]],
        interaction_id: Optional[str] = None,
        current_datetime: datetime = datetime.now(),
        extract_agent_memories: bool = False,
        update_across_agents: bool = True,
        max_retries: int = 3
    ) -> Tuple[str, str]:
        """
        Save a new interaction or update an existing one, and the extracted memories.

        Args:
            org_id (str): Organization ID.
            user_id (str): User ID.
            agent_id (str): Agent ID.
            interaction (List[Dict[str, str]]): List of interaction messages.
            interaction_id (Optional[str]): Interaction ID for updates.
            current_datetime (datetime): Current datetime.
            extract_agent_memories (bool): Whether to extract agent memories.
            update_across_agents (bool): Whether to update memories across all agents.
            max_retries (int): Maximum number of retries.

        Returns:
            Tuple[str, str]: Interaction ID and (created_at or updated_at) ISO timestamp.

        Raises:
            Exception: If saving interaction memories fails after max retries.
        """

        for retry in range(max_retries + 1):
            try:
                user, agent = await self._get_user_and_agent(org_id, user_id, agent_id)

                if interaction_id:
                    previously_extracted_memories: List[Dict[str, str]] = await self.graph.get_all_interaction_memories(org_id, user_id, interaction_id)

                    system_content = MEMORY_EXTRACTION_UPDATE_SYSTEM_PROMPT.format(
                        day_of_week=current_datetime.strftime('%A'),
                        current_datetime_str=current_datetime.isoformat(),
                        agent_label=agent['agent_label'],
                        user_name=user['user_name'],
                        extract_for_agent=f'and {agent['agent_label']}' if extract_agent_memories else '',
                        previous_memories=str(previously_extracted_memories),
                        schema=MemoryExtractionResponse.model_json_schema()
                    )
                else:

                    system_content = MEMORY_EXTRACTION_SYSTEM_PROMPT.format(
                        day_of_week=current_datetime.strftime('%A'),
                        current_datetime_str=current_datetime.isoformat(),
                        agent_label=agent['agent_label'],
                        user_name=user['user_name'],
                        extract_for_agent=f'and {agent['agent_label']}' if extract_agent_memories else '',
                        schema=MemoryExtractionResponse.model_json_schema()
                    )

                messages = [{"role": "system", "content": system_content}]
                messages += [
                    {
                        'role': msg['role'], 
                        'content': EXTRACTION_MSG_BLOCK_FORMAT.format(message_id=i, content=msg['content'])
                    } for i, msg in enumerate(interaction)
                ]

                response: MemoryExtractionResponse = await self.extraction_model(messages=messages, output_schema_model=MemoryExtractionResponse)

                candidate_memories, candidate_memories_msg_sources = self._process_extracted_memories(response, user, agent)

                if not candidate_memories: # No useful info for memories was extracted.
                    
                    if interaction_id:
                        return await self.graph.update_interaction_and_memories(
                            org_id,
                            agent_id,
                            user_id,
                            interaction_id,
                            updated_memories_and_interaction=MemoriesAndInteraction(
                                interaction=interaction, 
                                interaction_date=current_datetime,
                                memories=[],
                                contrary_memories=[]
                                ),
                            vector_db_add_memories_fn=None # No need to add memories since there are none.
                        )
                    else:
                        return await self.graph.save_interaction_with_memories(
                            org_id, 
                            agent_id, 
                            user_id,
                            memories_and_interaction=MemoriesAndInteraction(
                                interaction=interaction, 
                                interaction_date=current_datetime,
                                memories=[],
                                contrary_memories=[]
                            ),
                            vector_db_add_memories_fn=None # No need to add memories since there are none.
                        )


                existing_memories = await self.search_memories_as_one(
                    org_id=org_id,
                    user_id=user_id,
                    search_queries=candidate_memories,
                    agent_id=agent_id,
                    memories_across_agents=update_across_agents
                )

                if not existing_memories: # No related existing memories were found.

                    if interaction_id:
                        return await self.graph.update_interaction_and_memories(
                            org_id,
                            agent_id,
                            user_id,
                            interaction_id,
                            updated_memories_and_interaction=MemoriesAndInteraction(
                                interaction=interaction, 
                                interaction_date=current_datetime,
                                memories=[MemoryToStore(memory=memory, source_msg_block_pos=source_msgs) for memory, source_msgs in zip(candidate_memories, candidate_memories_msg_sources)]
                                ),
                            vector_db_add_memories_fn=self.vector_db.add_memories
                        )
                    else:
                        return await self.graph.save_interaction_with_memories(
                            org_id,
                            agent_id,
                            user_id,
                            memories_and_interaction=MemoriesAndInteraction(
                                interaction=interaction, 
                                interaction_date=current_datetime,
                            memories=[MemoryToStore(memory=memory, source_msg_block_pos=source_msgs) for memory, source_msgs in zip(candidate_memories, candidate_memories_msg_sources)]
                            ),
                            vector_db_add_memories_fn=self.vector_db.add_memories
                        )

                candidate_memories = [{'memory': memory, 'POS_ID': i} for i, memory in enumerate(candidate_memories)]
                messages = [
                    {
                        "role": "system", 
                        "content": COMPARE_EXISTING_AND_NEW_MEMORIES_SYSTEM_PROMPT.format(
                        day_of_week=current_datetime.strftime('%A'),
                        current_datetime_str=current_datetime.isoformat(),
                        agent_placeholder=f"agent_{agent['agent_id']}",
                        user_placeholder=f"user_{user['user_id']}",
                        schema=MemoryComparisonResponse.model_json_schema()
                    )},
                    {
                        'role': "user", 
                        'content': COMPARE_EXISTING_AND_NEW_MEMORIES_INPUT_TEMPLATE.format(
                            existing_memories_string = str(existing_memories),
                            new_memories_string = str(candidate_memories)
                        )
                    }
                ]

                response : MemoryComparisonResponse = await self.extraction_model(messages=messages, output_schema_model=MemoryComparisonResponse)

                new_memories = []
                for memory in response.new_memories:
                    try:
                        new_memories.append((memory.memory, candidate_memories_msg_sources[memory.source_candidate_pos_id]))
                    except: continue

                new_contrary_memories = []
                for memory in response.contrary_memories:
                    try:
                        new_contrary_memories.append((memory.memory, candidate_memories_msg_sources[memory.source_candidate_pos_id], memory.contradicted_memory_id))
                    except: continue

                if interaction_id:
                    return await self.graph.update_interaction_and_memories(
                            org_id, agent_id, user_id, interaction_id,
                            updated_memories_and_interaction=MemoriesAndInteraction(
                                interaction=interaction, 
                                interaction_date=current_datetime,
                                memories=[MemoryToStore(memory=memory_tuple[0], source_msg_block_pos=memory_tuple[1]) for memory_tuple in new_memories],
                                contrary_memories=[ContraryMemory(memory=memory_tuple[0], source_msg_block_pos=memory_tuple[1], existing_contrary_memory_id=memory_tuple[2]) for memory_tuple in new_contrary_memories]
                                ),
                            vector_db_add_memories_fn=self.vector_db.add_memories
                        )
                else:
                    return await self.graph.save_interaction_with_memories(
                        org_id, agent_id, user_id,
                        memories_and_interaction=MemoriesAndInteraction(
                            interaction=interaction, 
                            interaction_date=current_datetime,
                            memories=[MemoryToStore(memory=memory_tuple[0], source_msg_block_pos=memory_tuple[1]) for memory_tuple in new_memories],
                            contrary_memories=[ContraryMemory(memory=memory_tuple[0], source_msg_block_pos=memory_tuple[1], existing_contrary_memory_id=memory_tuple[2]) for memory_tuple in new_contrary_memories]
                        ),
                        vector_db_add_memories_fn=self.vector_db.add_memories
                    )

            except Exception as e:
                if retry == max_retries:
                    raise Exception(f"Failed to save/update interaction memories: {e}")
                else:
                    continue
    
    async def _get_user_and_agent(self, org_id: str, user_id: str, agent_id: str) -> Tuple[Dict, Dict]:
        """Fetch user and agent data."""

        user = await self.graph.get_user(org_id, user_id)
        agent = await self.graph.get_agent(org_id, agent_id)
        
        if not user or not agent:
            raise ValueError(f"User or Agent not found: user_id={user_id}, agent_id={agent_id}")
        
        return user, agent
    
    def _process_extracted_memories(self, response: MemoryExtractionResponse, user: Dict, agent: Dict) -> Tuple[List[str], List[List[int]]]:
        """
        Get every memory extracted, their source messages and insert placeholders for user and agent.
        
        Args:
            response (MemoryExtractionResponse): Response from the memory extraction model.
            user (Dict): User data.
            agent (Dict): Agent data.

        Returns:
            Tuple[List[str], List[List[int]]]: Extracted memories and their source messages.
        """
        
        candidate_memories: List[str] = []
        candidate_memories_msg_sources: List[List[int]] = []

        for memory_list in (response.memories_first_pass or [],
                                response.memories_second_pass or [],
                                response.memories_third_pass or []):
            for memory in memory_list:
                memory_text = memory.memory.replace('#user_#id#', f"user_{user['user_id']}").replace('#agent_#id#', f"agent_{agent['agent_id']}")
                candidate_memories.append(memory_text)
                candidate_memories_msg_sources.append(memory.msg_source_ids)

        return candidate_memories, candidate_memories_msg_sources
    
    async def get_memories_for_message(
        self, 
        org_id: str,
        user_id: str,  
        latest_msg: Dict[str, str], 
        agent_id: Optional[str] = None,
        preceding_msg_for_context: Optional[List[Dict[str, str]]] = [], 
        current_datetime: datetime = datetime.now(),
        search_memories_across_agents: bool = True,
        enable_final_model_based_memory_filter: bool = True,
    ) -> Optional[List[Dict[str, str]]]:
        """
        Retrieve and filter memories relevant to the given message.

        Args:
            org_id (str): Organization ID.
            user_id (str): User ID.
            latest_msg (Dict[str, str]): The latest message to find memories for.
            agent_id (Optional[str]): Agent ID.
            preceding_msg_for_context (Optional[List[Dict[str, str]]]): Preceding messages for context.
            current_datetime (datetime): Current datetime.
            search_memories_across_agents (bool): Whether to search memories across all agents.
            enable_final_model_based_memory_filter (bool): Whether to use the memory model to filter retrieved memories before returning.

        Returns:
            Optional[List[Dict[str, str]]]: Retrieved and filtered memories, or None if no relevant memories found.
        """
        memory_search_queries = await self.generate_memory_search_queries(latest_msg, preceding_msg_for_context, current_datetime)
        
        if not memory_search_queries:
            return None
        
        retrieved_memories = await self.search_memories_as_one(
            org_id, user_id, memory_search_queries, agent_id, search_memories_across_agents
        )
        
        if not enable_final_model_based_memory_filter:
            return retrieved_memories
        
        # Filter retrieved memories using the memory model.
        filtered_memory_ids = await self.filter_retrieved_memories_with_model(
            latest_msg, memory_search_queries, retrieved_memories, current_datetime
        )
        
        if filtered_memory_ids is None: # The LLM was unable to filter just needed memories.
            return retrieved_memories
        
        if len(filtered_memory_ids) == 0: # The LLM filtered out all memories (deemed none are needed to be recalled).
            return None
        
        memory_dict = {memory["memory_id"]: memory for memory in retrieved_memories}
        selected_memories = [memoryObj for memory_id in filtered_memory_ids if (memoryObj := memory_dict.get(memory_id)) is not None]
        
        return selected_memories

