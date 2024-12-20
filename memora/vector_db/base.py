from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import uuid

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
                         org_id: Optional[str] = None,
                         user_id: Optional[str] = None,
                         agent_id: Optional[str] = None
                         ) -> List[Dict[str, Any]]:
        """Memory search with optional org/user filtering.
        
        Args:
            query: Search query string
            org_id: Optional organization ID for filtering
            user_id: Optional user ID for filtering
            agent_id: Optional agent ID for filtering
            
        Returns:
            List of Dicts containing search results with at least 'memory', 'score', 'memory_id', and 'obtained_at' keys
        """
        pass

    @abstractmethod
    async def search_memories(self,
                          queries: List[str],
                          org_id: Optional[str] = None,
                          user_id: Optional[str] = None,
                          agent_id: Optional[str] = None
                          ) -> List[List[Dict[str, Any]]]:
        """Batch memory search with optional org/user filtering.
        
        Args:
            queries: List of search query strings
            org_id: Optional organization ID for filtering
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
            
        Raises:
            KeyError: If the memory_id doesn't exist
        """
        pass

    @abstractmethod
    async def delete_memories(self, memory_ids: List[str]) -> None:
        """Delete multiple memories by their IDs.
        
        Args:
            memory_ids: List of memory IDs to delete
            
        Raises:
            KeyError: If any of the memory_ids don't exist
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

    async def select_top_p_memories_by_score(self,
                                batch_search_results: List[List[Dict[str, Any]]],
                                top_p: float = 0.8
                                ) -> List[Dict[str, Any]]:
        """Pick top-p memories across batch search results based on their scores.

        Args:
            batch_search_results: List of lists containing search results. Each result should be a
                                  dictionary containing at least a 'memory', 'score', 'memory_id', and 'obtained_at' keys
            top_p: The probability threshold for selecting memories (0 < top_p ≤ 1)

        Returns:
            List of selected memories ordered by descending score

        Raises:
            ValueError: If top_p is not between 0 and 1
        """
        if not 0 < top_p <= 1:
            raise ValueError("top_p must be between 0 and 1")
        
        if not batch_search_results:
            return []

        # Efficiently consolidate results using max score per unique memory across batch search results.
        memory_scores = {}
        memory_metadata = {}
        for batch in batch_search_results:
            for result in batch:
                memory_id = result.get('memory_id')
                if memory_id not in memory_scores or result['score'] > memory_scores[memory_id]:
                    memory_scores[memory_id] = result['score']
                    memory_metadata[memory_id] = result

        # Sort by score and get top p cumulative.
        sorted_memories = sorted(memory_scores.items(), key=lambda x: x[1], reverse=True)
        cumulative_score = 0
        total_score = sum(score for _, score in sorted_memories)
        threshold_score = top_p * total_score
        final_results = []

        for memory_id, score in sorted_memories:

            if score < 0.4: # If memories relevance is less than 0.4, do not add.
                break

            cumulative_score += score
            final_results.append(memory_metadata[memory_id])

            if cumulative_score >= threshold_score:
                break

        return final_results