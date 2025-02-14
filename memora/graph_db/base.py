from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from memora.schema import models

from ..schema.storage_schema import MemoriesAndInteraction
from ..vector_db.base import BaseVectorDB


class BaseGraphDB(ABC):
    """
    Abstract base class defining a common interface for different Graph DB implementations.

    This class provides a standardized interface for graph database operations, including
    creating, retrieving, and deleting memory nodes and relationships.
    """

    @abstractmethod
    def get_associated_vector_db(self) -> Optional[BaseVectorDB]:
        """
        The vector database associated with the graph database, these is used inside the graph transactional blocks
        to ensure data consistency when handling memories across both stores (e.g., saving memories to the vector
        store and creating corresponding nodes in the graph db).
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Closes the database connection."""
        pass

    # Setup method
    @abstractmethod
    async def setup(self, *args, **kwargs) -> None:
        """
        Sets up the database, e.g., creates indexes, constraints, etc.
        """
        pass

    # Organization methods
    @abstractmethod
    async def create_organization(self, org_name: str) -> models.Organization:
        """
        Creates a new organization in the graph database.

        Args:
            org_name (str): The name of the organization to create.

        Returns:
            Organization object containing:

                + org_id: Short UUID string
                + org_name: Organization name
                + created_at: DateTime object of when the organization was created
        """
        pass

    @abstractmethod
    async def update_organization(
        self, org_id: str, new_org_name: str
    ) -> models.Organization:
        """
        Updates an existing organization in the graph database.

        Args:
            org_id (str): The Short UUID of the organization to update.
            new_org_name (str): The new name for the organization.

        Returns:
            Organization object containing:

                + org_id: Short UUID string
                + org_name: Organization name
                + created_at: DateTime object of when the organization was created
        """
        pass

    @abstractmethod
    async def delete_organization(self, org_id: str) -> None:
        """
        Deletes an organization from the graph database.

        Warning:
            This operation will delete all nodes and relationships from this organization
            including users, agents, memories, interactions etc.

        Args:
            org_id (str): Short UUID string identifying the organization to delete.
        """
        pass

    @abstractmethod
    async def get_organization(self, org_id: str) -> models.Organization:
        """
        Gets a specific organization from the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization to retrieve.

        Returns:
            Organization object containing:

                + org_id: Short UUID string
                + org_name: Organization name
                + created_at: DateTime object of when the organization was created
        """
        pass

    @abstractmethod
    async def get_all_organizations(self) -> List[models.Organization]:
        """
        Gets all organizations from the graph database.

        Returns:
            List[Organization] each containing:

                + org_id: Short UUID string
                + org_name: Organization name
                + created_at: DateTime object of when the organization was created
        """
        pass

    # Agent methods
    @abstractmethod
    async def create_agent(
        self, org_id: str, agent_label: str, user_id: Optional[str] = None
    ) -> models.Agent:
        """
        Creates a new agent in the graph database.

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
        pass

    @abstractmethod
    async def update_agent(
        self, org_id: str, agent_id: str, new_agent_label: str
    ) -> models.Agent:
        """
        Updates an existing agent in the graph database.

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
        pass

    @abstractmethod
    async def delete_agent(self, org_id: str, agent_id: str) -> None:
        """
        Deletes an agent from the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_id (str): Short UUID string identifying the agent to delete.
        """
        pass

    @abstractmethod
    async def get_agent(self, org_id: str, agent_id: str) -> models.Agent:
        """
        Gets a specific agent belonging to the specified organization from the graph database.

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
        pass

    @abstractmethod
    async def get_all_org_agents(self, org_id: str) -> List[models.Agent]:
        """
        Gets all agents belonging to the specified organization from the graph database.

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
        pass

    @abstractmethod
    async def get_all_user_agents(
        self, org_id: str, user_id: str
    ) -> List[models.Agent]:
        """
        Gets all agents for a user within an organization from the graph database.

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
        pass

    # User methods
    @abstractmethod
    async def create_user(self, org_id: str, user_name: str) -> models.User:
        """
        Creates a new user in the graph database.

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
        pass

    @abstractmethod
    async def update_user(
        self, org_id: str, user_id: str, new_user_name: str
    ) -> models.User:
        """
        Updates an existing user in the graph database.

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
        pass

    @abstractmethod
    async def delete_user(self, org_id: str, user_id: str) -> None:
        """
        Deletes a user from the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user to delete.
        """
        pass

    @abstractmethod
    async def get_user(self, org_id: str, user_id: str) -> models.User:
        """
        Gets a specific user belonging to the specified organization from the graph database.

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
        pass

    @abstractmethod
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
        pass

    # Interaction methods
    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    # Memory methods
    @abstractmethod
    async def fetch_user_memories_resolved(
        self, org_user_mem_ids: List[Dict[str, str]]
    ) -> List[models.Memory]:
        """
        Fetches memories from the GraphDB by their IDs, resolves any contrary updates, and replaces user/agent placeholders with actual names.

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
        pass

    @abstractmethod
    async def fetch_user_memories_resolved_batch(
        self, batch_org_user_mem_ids: List[List[Dict[str, str]]]
    ) -> List[List[models.Memory]]:
        """
        Fetches memories from the GraphDB by their IDs, resolves any contrary updates, and replaces user/agent placeholders with actual names.

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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass
