from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Dict, List, Tuple, Optional
from ..schema.save_memory_schema import MemoriesAndInteraction

class BaseGraphDB(ABC):
    """
    Abstract base class defining a common interface for different Graph DB implementations.
    
    This class provides a standardized interface for graph database operations, including
    creating, retrieving, and deleting memory nodes and relationships.
    """

    @abstractmethod
    async def close(self):
        """Closes the database connection."""
        pass

    # Setup method
    @abstractmethod
    async def setup(self, *args, **kwargs) -> None:
        """Sets up the database, e.g., creates indexes, constraints, etc."""
        pass

    # Organization methods
    @abstractmethod
    async def create_organization(
        self, 
        org_name: str
    ) -> Dict[str, str]:
        """Creates a new organization in the graph database.
        
        Returns:
            Dict containing:
            - org_id: UUID string
            - org_name: Organization name
            - created_at: ISO format timestamp
        """
        pass

    @abstractmethod
    async def delete_organization(
        self,
        org_id: str
    ) -> None:
        """Deletes an organization from the graph database.
        
        Args:
            org_id: UUID string identifying the organization
        """
        pass

    # Agent methods
    @abstractmethod
    async def create_agent(
        self,
        org_id: str,
        agent_label: str,
        user_id: Optional[str] = None
    ) -> Dict[str, str]:
        """Creates a new agent in the graph database.
        
        Args:
            org_id: UUID string identifying the organization
            agent_label: Label/name for the agent
            user_id: Optional UUID of the user. This is used when the agent is created specifically for a user, 
                     indicating that both the organization and the user will have this agent.

        Returns:
            Dict containing:
            - org_id: UUID string
            - user_id: Optional UUID string
            - agent_id: UUID string 
            - agent_label: Agent label/name
            - created_at: ISO format timestamp
        """
        pass

    @abstractmethod
    async def delete_agent(
        self,
        org_id: str,
        agent_id: str
    ) -> None:
        """Deletes an agent from the graph database.
        
        Args:
            org_id: UUID string identifying the organization
            agent_id: UUID string identifying the agent
        """
        pass

    @abstractmethod
    async def get_agent(
        self,
        org_id: str,
        agent_id: str
    ) -> Dict[str, str]:
        """Gets a specific agent belonging to the specified organization from the graph database.
        
        Args:
            org_id: UUID string identifying the organization
            agent_id: UUID string identifying the agent

        Returns:
            Dict containing:
            - org_id: UUID string
            - user_id: Optional UUID string if agent is associated with a user [:HAS_AGENT].
            - agent_id: UUID string
            - agent_label: Agent label/name
            - created_at: ISO format timestamp
        """
        pass

    @abstractmethod
    async def get_all_org_agents(
        self,
        org_id: str
    ) -> List[Dict[str, str]]:
        """Gets all agents belonging to the specified organization from the graph database.
        
        Args:
            org_id: UUID string identifying the organization

        Returns:
            List of dicts containing:
            - org_id: UUID string 
            - agent_id: UUID string
            - agent_label: Agent label/name
            - created_at: ISO format timestamp

            for all agents belonging to the specified organization
        """
        pass

    @abstractmethod
    async def get_all_user_agents(
        self,
        org_id: str,
        user_id: str
    ) -> List[Dict[str, str]]:
        """Gets all agents for a user within an organization from the graph database.
        
        Args:
            org_id: UUID string identifying the organization
            user_id: UUID string identifying the user

        Returns:
            List of dicts containing:
            - org_id: UUID string 
            - user_id: UUID string
            - agent_id: UUID string
            - agent_label: Agent label/name
            - created_at: ISO format timestamp

            for all agents belonging to the specified user within the organization
        """
        pass

    # User methods
    @abstractmethod
    async def create_user(
        self,
        org_id: str,
        user_name: str
    ) -> Dict[str, str]:
        """Creates a new user in the graph database.
        
        Args:
            org_id: UUID string identifying the organization
            user_name: Name for the user

        Returns:
            Dict containing:
            - org_id: UUID string
            - user_id: UUID string
            - user_name: User's name
            - created_at: ISO format timestamp
        """
        pass

    @abstractmethod
    async def delete_user(
        self,
        org_id: str,
        user_id: str
    ) -> None:
        """Deletes a user from the graph database.
        
        Args:
            org_id: UUID string identifying the organization
            user_id: UUID string identifying the user
        """
        pass

    @abstractmethod
    async def get_user(
        self,
        org_id: str,
        user_id: str
    ) -> Dict[str, str]:
        """Gets a specific user belonging to the specified organization from the graph database.
        
        Args:
            org_id: UUID string identifying the organization
            user_id: UUID string identifying the user

        Returns:
            Dict containing:
            - org_id: UUID string
            - user_id: UUID string
            - user_name: User's name
            - created_at: ISO format timestamp
        """
        pass

    @abstractmethod 
    async def get_all_users(
        self,
        org_id: str
    ) -> List[Dict[str, str]]:
        """Gets all users belonging to the specified organization from the graph database.
        
        Args:
            org_id: UUID string identifying the organization

        Returns:
            List of dicts containing:
            - org_id: UUID string
            - user_id: UUID string 
            - user_name: User's name
            - created_at: ISO format timestamp

            for all users belonging to the specified organization
        """
        pass

    # Interaction methods
    @abstractmethod
    async def save_interaction_with_memories(
        self,
        org_id: str,
        agent_id: str, 
        user_id: str,
        memories_and_interaction: MemoriesAndInteraction,
        vector_db_add_memories_fn: Callable[..., Awaitable[None]]
    ) -> str:
        """Creates a new interaction record with associated memories.
        
        Args:
            org_id: UUID string identifying the organization
            agent_id: UUID string identifying the agent
            user_id: UUID string identifying the user
            memories_and_interaction: Contains both the interaction and the associated memories.
            vector_db_add_memories_fn: Coroutine (`BaseVectorDB.add_memories`),
                called in the graph transaction block to ensure data consistency.
        
        Returns:
            - interaction_id: UUID string identifying the created interaction
        """
        pass

    @abstractmethod
    async def update_interaction_and_memories(
        self,
        org_id: str,
        agent_id: str,
        user_id: str,
        interaction_id: str,
        updated_memories_and_interaction: MemoriesAndInteraction,
        vector_db_add_memories_fn: Callable[..., Awaitable[None]]
    ) -> Tuple[str, str]:
        """
        Update an existing interaction record and add new memories.
        
        Compares updated interaction with existing one:

        - If differences found, truncates existing record from that point and
          replaces with updated version. Old memories from truncated message(s)
          remain but become standalone (no longer linked to truncated messages).

        - If no differences, appends new messages from the update.
        
        New memories are always added, regardless of interaction changes.
        
        Args:
            org_id: UUID string identifying the organization
            agent_id: UUID string identifying the agent in the updated interaction
            user_id: UUID string identifying the user
            interaction_id: UUID string identifying the interaction to update
            updated_memories_and_interaction: Contains both the updated interaction and the associated new memories.
            vector_db_add_memories_fn: Coroutine (`BaseVectorDB.add_memories`),
                called in the graph transaction block to ensure data consistency.

            
        Returns:
            Tuple containing:
            - interaction_id: UUID string identifying the updated interaction
            - updated_at: ISO format timestamp of when the update occurred
        """
        pass

    @abstractmethod
    async def get_interaction_messages(
        self,
        org_id: str,
        user_id: str,
        interaction_id: str
    ) -> List[Dict[str, str]]:
        """Retrieves all messages associated with a specific interaction.
        
        Args:
            org_id: UUID string identifying the organization
            user_id: UUID string identifying the user
            interaction_id: UUID string identifying the interaction
            
        Returns:
            List of dictionaries containing message details:
            - role: Role of the message sender (user or agent)
            - content: String content of the message
            - msg_position: Position of the message in the interaction
        """
        pass

    @abstractmethod
    async def get_all_interaction_memories(
        self,
        org_id: str,
        user_id: str,
        interaction_id: str
    ) -> List[Dict[str, str]]:
        """Retrieves all memories associated with a specific interaction.
        
        Args:
            org_id: UUID string identifying the organization
            user_id: UUID string identifying the user
            interaction_id: UUID string identifying the interaction
            
        Returns:
            List of dictionaries containing memory details:
            - memory_id: UUID string identifying the memory
            - memory: String content of the memory
            - obtained_at: ISO format timestamp of when the memory was obtained
        """
        pass

    @abstractmethod
    async def delete_user_interaction_and_its_memories(
        self,
        org_id: str,
        user_id: str,
        interaction_id: str,
        vector_db_delete_memories_by_id_fn: Callable[..., Awaitable[None]]
    ) -> None:
        """Deletes an interaction record and its associated memories.
        
        Args:
            org_id: UUID string identifying the organization
            user_id: UUID string identifying the user
            interaction_id: UUID string identifying the interaction to delete
            vector_db_delete_memories_by_id_fn: Coroutine (`BaseVectorDB.delete_memories`),
                called in the graph transaction block to ensure data consistency.
        """
        pass

    @abstractmethod
    async def delete_all_user_interactions_and_their_memories(
        self,
        org_id: str,
        user_id: str,
        vector_db_delete_all_user_memories_fn: Callable[..., Awaitable[None]]
    ) -> None:
        """Deletes all interactions and their associated memories for a specific user in an organization.
        
        Args:
            org_id: UUID string identifying the organization
            user_id: UUID string identifying the user whose interactions should be deleted
            vector_db_delete_all_user_memories_fn: Coroutine (`BaseVectorDB.delete_all_user_memories`), 
                called in the graph transaction block to ensure data consistency.
        """
        pass


    # Memory methods
    def fetch_user_memories_resolved(self, org_id: str, user_id: str, memory_ids: List[str]) -> List[Dict[str, str]]:
        """
        Fetches memories from the GraphDB by their IDs, resolves any contrary updates, and replaces user/agent placeholders with actual names.

        This method performs several operations:
        1. Retrieves memories using (org_id, user_id, memory_ids)
        2. If a memory has a CONTRARY_UPDATE relationship, uses the newer memory version
        3. Replaces user_id & agent_id placeholders (e.g 'user_abc123' or 'agent_xyz789') in memories with actual user names / agent labels

        Args:
            org_id: UUID string identifying the organization
            user_id: UUID string identifying the user
            memory_ids: List of memory IDs to fetch and process

        Returns:
            List of dictionaries containing memory details:
            - memory_id: UUID string identifying the memory
            - memory: String content of the resolved memory 
            - obtained_at: ISO format timestamp of when the memory was obtained

        Example:
            >>> memory_ids = ["413ac3a8-fe87-49a4-93d2-05d3eb58ddeb", "376d0e7a-97f7-4380-a673-4f85b1e53625"]
            >>> memories = graphInstance.fetch_memories_resolved(org_id, user_id, memory_ids)
            >>> print([memoryObj['memory'] for memoryObj in memories])
            ["John asked for help with a wedding ring", "Sarah is allergic to peanuts"]

        Note:
            Memory IDs are typically retrieved from a vector database before being passed to this method.
        """
        pass

    def fetch_user_memories_resolved_batch(self, org_id: str, user_id: str, batch_memory_ids: List[List[str]]) -> List[List[Dict[str, str]]]:
        """
        Fetches memories from the GraphDB by their IDs, resolves any contrary updates, and replaces user/agent placeholders with actual names.

        This method performs several operations:
        1. Retrieves memories using (org_id, user_id, memory_ids)
        2. If a memory has a CONTRARY_UPDATE relationship, uses the newer memory version
        3. Replaces user_id & agent_id placeholders (e.g 'user_abc123' or 'agent_xyz789') in memories with actual user names / agent labels

        Args:
            org_id: UUID string identifying the organization
            user_id: UUID string identifying the user
            batch_memory_ids: List of Lists containing memory IDs to fetch and process

        Returns:
            List of Lists containing dictionaries with memory details:
            - memory_id: UUID string identifying the memory
            - memory: String content of the resolved memory 
            - obtained_at: ISO format timestamp of when the memory was obtained

        Example:
            >>> batch_memory_ids = [["413ac3a8-fe87-49a4-93d2-05d3eb58ddeb", "376d0e7a-97f7-4380-a673-4f85b1e53625"], ["6423b2e2-4223-43ec-aef7-69ce3ed512fb"]]
            >>> batch_memories = graphInstance.fetch_memories_resolved_batch(org_id, user_id, batch_memory_ids)
            >>> print([[memoryObj['memory'] for memoryObj in memories] for memories in batch_memories])
            [["John asked for help with a wedding ring", "Sarah is allergic to peanuts"], ["John is about to propose to Sarah"]]

        Note:
            Batch Memory IDs are typically retrieved from a vector database before being passed to this method.
        """
        pass

    @abstractmethod
    async def get_user_memory(
        self,
        org_id: str,
        user_id: str,
        memory_id: str
    ) -> Dict[str, str]:
        """Retrieves a specific memory.
        
        Args:
            org_id: UUID string identifying the organization
            user_id: UUID string identifying the user
            memory_id: UUID string identifying the memory
            
        Returns:
            Dictionary containing memory details:
            - memory_id: UUID string identifying the memory
            - memory: String content of the memory
            - obtained_at: ISO format timestamp of when the memory was obtained
        """
        pass

    @abstractmethod
    async def get_all_user_memories(
        self,
        org_id: str,
        user_id: str,
        agent_id: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Retrieves all memories associated with a specific user.
        
        Args:
            org_id: UUID string identifying the organization
            user_id: UUID string identifying the user
            agent_id: Optional UUID string identifying the agent. If provided, only memories obtained from 
                interactions with this agent are returned. 
                Otherwise, all memories associated with the user are returned.
            
        Returns:
            List of dictionaries containing memory details:
            - memory_id: UUID string identifying the memory
            - memory: String content of the memory 
            - obtained_at: ISO format timestamp of when the memory was obtained
        """
        pass

    @abstractmethod
    async def delete_user_memory(
        self,
        org_id: str,
        user_id: str,
        memory_id: str,
        vector_db_delete_memory_by_id_fn: Callable[..., Awaitable[None]]
    ) -> None:
        """Deletes a specific memory.
        
        Args:
            org_id: UUID string identifying the organization
            user_id: UUID string identifying the user
            memory_id: UUID string identifying the memory to delete
            vector_db_delete_memory_by_id_fn: Coroutine (`BaseVectorDB.delete_memory`),
                called in the graph transaction block to ensure data consistency.
        """
        pass

    @abstractmethod
    async def delete_all_user_memories(
        self,
        org_id: str,
        user_id: str,
        vector_db_delete_all_user_memories_fn: Callable[..., Awaitable[None]]
    ) -> None:
        """
        Deletes all memories of a specific user.

        Args:
            org_id: UUID string identifying the organization
            user_id: UUID string identifying the user
            vector_db_delete_all_user_memories_fn: Coroutine (`BaseVectorDB.delete_all_user_memories`), 
                called in the graph transaction block to ensure data consistency.
        """
        pass