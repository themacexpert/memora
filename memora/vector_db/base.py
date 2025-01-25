import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional, Tuple

from memora.schema import models


class MemorySearchScope(Enum):
    ORGANIZATION = "organization"  # Search across all memories in the organization
    USER = "user"  # Search across all memories of a specific user in the organization


class BaseVectorDB(ABC):
    """
    Abstract base class defining a common interface for different Vector DB implementations.

    This class provides a standardized interface for vector database operations including
    adding, searching, and deleting memories.
    """

    @abstractmethod
    async def close(self) -> None:
        """Closes the database connection."""
        pass

    @abstractmethod
    async def setup(self, *args, **kwargs) -> None:
        """Setup the vector database by initializing collections, indices, etc."""
        pass

    @abstractmethod
    async def add_memories(
        self,
        org_id: str,
        user_id: str,
        agent_id: str,
        memory_ids: List[uuid.UUID],
        memories: List[str],
        obtained_at: str,
    ) -> None:
        """
        Add memories to collection with their org_id, user_id, agent_id, and obtained_at datetime as metadata.

        Args:
            org_id (str): Organization ID for the memories
            user_id (str): User ID for the memories
            agent_id (str): Agent ID for the memories
            memory_ids (List[uuid.UUID]): List of UUIDs for each memory
            memories (List[str]): List of memory strings to add
            obtained_at (str): ISO format datetime string when the memories were obtained
        """
        pass

    @abstractmethod
    async def search_memory(
        self,
        query: str,
        memory_search_scope: MemorySearchScope,
        org_id: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> List[Tuple[models.Memory, float]]:
        """
        Memory search with optional user/agent filtering.

        Args:
            query (str): Search query string
            memory_search_scope (MemorySearchScope): Memory search scope (organization or user)
            org_id (str): Organization ID for filtering
            user_id (Optional[str]): Optional user ID for filtering
            agent_id (Optional[str]): Optional agent ID for filtering

        Returns:
            List[Tuple[Memory, float]] containing tuple of search results and score:
                Memory:

                    + org_id: str
                    + agent_id: str
                    + user_id: str
                    + memory_id: str
                    + memory: str
                    + obtained_at: datetime

                float: Score of the memory
        """
        pass

    @abstractmethod
    async def search_memories(
        self,
        queries: List[str],
        memory_search_scope: MemorySearchScope,
        org_id: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> List[List[Tuple[models.Memory, float]]]:
        """
        Batch memory search with optional user/agent filtering.

        Args:
            queries (List[str]): List of search query strings
            memory_search_scope (MemorySearchScope): Memory search scope (organization or user)
            org_id (str): Organization ID for filtering
            user_id (Optional[str]): Optional user ID for filtering
            agent_id (Optional[str]): Optional agent ID for filtering

        Returns:
            List[List[Tuple[models.Memory, float]]] of search results for each query, with a tuple containing:
                Memory:

                    + org_id: str
                    + agent_id: str
                    + user_id: str
                    + memory_id: str
                    + memory: str
                    + obtained_at: datetime

                float: Score of the memory
        """
        pass

    @abstractmethod
    async def delete_memory(self, memory_id: str) -> None:
        """
        Delete a memory by its ID with optional org/user filtering.

        Args:
            memory_id (str): ID of the memory to delete
        """
        pass

    @abstractmethod
    async def delete_memories(self, memory_ids: List[str]) -> None:
        """
        Delete multiple memories by their IDs.

        Args:
            memory_ids (List[str]): List of memory IDs to delete
        """
        pass

    @abstractmethod
    async def delete_all_user_memories(self, org_id: str, user_id: str) -> None:
        """
        Delete all memories associated with a specific user.

        Args:
            org_id (str): Organization ID the user belongs to
            user_id (str): ID of the user whose memories should be deleted
        """
        pass

    @abstractmethod
    async def delete_all_organization_memories(self, org_id: str) -> None:
        """
        Delete all memories associated with an organization.

        Args:
            org_id (str): ID of the organization whose memories should be deleted
        """
        pass
