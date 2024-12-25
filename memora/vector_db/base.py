from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import uuid
from enum import Enum

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
    async def close(self):
        """Closes the database connection."""
        pass

    @abstractmethod
    async def setup(self, *args, **kwargs) -> None:
        """Setup the vector database by initializing collections, indices, etc."""
        pass

    @abstractmethod
    async def add_memories(self,
                        org_id: str,
                        user_id: str,
                        agent_id: str,
                        memory_ids: List[uuid.UUID],
                        memories: List[str],
                        obtained_at: str
                        ) -> None:
        """Add memories to collection with their org_id, user_id, agent_id, and obtained_at datetime as metadata.
        
        Args:
            org_id: Organization ID for the memories
            user_id: User ID for the memories
            agent_id: Agent ID for the memories
            memory_ids: List of UUIDs for each memory
            memories: List of memory strings to add
            obtained_at: ISO format datetime string when the memories were obtained
            
        Raises:
            ValueError: If the lengths of memory_ids and memories don't match
        """
        pass
    
    @abstractmethod
    async def search_memory(self,
                         query: str,
                         memory_search_scope: MemorySearchScope,
                         org_id: str,
                         user_id: Optional[str] = None,
                         agent_id: Optional[str] = None,
                         ) -> List[Dict[str, Any]]:
        """Memory search with optional org/user filtering.
        
        Args:
            query: Search query string
            memory_search_scope: Memory search scope (organization or user)
            org_id: Organization ID for filtering
            user_id: Optional user ID for filtering
            agent_id: Optional agent ID for filtering
            
        Returns:
            List of Dicts containing search results with at least 'memory', 'score', 'memory_id', and 'obtained_at' keys
        """
        pass

    @abstractmethod
    async def search_memories(self,
                          queries: List[str],
                          memory_search_scope: MemorySearchScope,
                          org_id: str,
                          user_id: Optional[str] = None,
                          agent_id: Optional[str] = None,
                          ) -> List[List[Dict[str, Any]]]:
        """Batch memory search with optional org/user filtering.
        
        Args:
            queries: List of search query strings
            memory_search_scope: Memory search scope (organization or user)
            org_id: Organization ID for filtering
            user_id: Optional user ID for filtering
            agent_id: Optional agent ID for filtering
            
        Returns:
            List of search results for each query, where each result is a list of dictionaries. Each dictionary contains at least 'memory', 'score', 'memory_id', and 'obtained_at' keys.
        """
        pass

    @abstractmethod
    async def delete_memory(self, memory_id: str) -> None:
        """Delete a memory by its ID with optional org/user filtering.
        
        Args:
            memory_id: ID of the memory to delete
        """
        pass

    @abstractmethod
    async def delete_memories(self, memory_ids: List[str]) -> None:
        """Delete multiple memories by their IDs.
        
        Args:
            memory_ids: List of memory IDs to delete
        """
        pass

    @abstractmethod
    async def delete_all_user_memories(self, org_id: str, user_id: str) -> None:
        """Delete all memories associated with a specific user.
        
        Args:
            org_id: Organization ID the user belongs to
            user_id: ID of the user whose memories should be deleted
        """
        pass

    @abstractmethod
    async def delete_all_organization_memories(self, org_id: str) -> None:
        """Delete all memories associated with an organization.
        
        Args:
            org_id: ID of the organization whose memories should be deleted
        """
        pass