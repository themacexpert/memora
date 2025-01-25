from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Organization(BaseModel):
    org_id: str = Field(description="Short UUID string identifying the organization.")
    org_name: str = Field(description="Name of the organization.")
    created_at: datetime = Field(
        description="DateTime object of when the organization was created."
    )


class Agent(BaseModel):
    org_id: str = Field(description="Short UUID string identifying the organization.")
    agent_id: str = Field(description="Short UUID string identifying the agent.")
    user_id: Optional[str] = Field(
        default=None, description="Short UUID string identifying the user."
    )
    agent_label: str = Field(description="Label/name for the agent.")
    created_at: datetime = Field(
        description="DateTime object of when the agent was created."
    )


class User(BaseModel):
    org_id: str = Field(description="Short UUID string identifying the organization.")
    user_id: str = Field(description="Short UUID string identifying the user.")
    user_name: str = Field(description="Name of the user.")
    created_at: datetime = Field(
        description="DateTime object of when the user was created."
    )


class Interaction(BaseModel):
    org_id: str = Field(description="Short UUID string identifying the organization.")
    agent_id: str = Field(description="Short UUID string identifying the agent.")
    interaction_id: str = Field(
        description="Short UUID string identifying the interaction."
    )
    user_id: str = Field(description="Short UUID string identifying the user.")
    created_at: datetime = Field(
        description="DateTime object of when the interaction was created."
    )
    updated_at: datetime = Field(
        description="DateTime object of when the interaction was last updated."
    )
    messages: Optional[List[MessageBlock]] = Field(
        default=None, description="List of messages in the interaction."
    )
    memories: Optional[List[Memory]] = Field(
        default=None,
        description="List of memories gotten across all occurrences of this interaction.",
    )


class MessageBlock(BaseModel):
    role: Optional[str] = Field(
        default=None, description="e.g., user, assistant, tool."
    )
    content: Optional[str] = Field(
        default=None, description="The actual content of the message."
    )
    msg_position: int = Field(
        description="Position of this message in the interaction."
    )


class Memory(BaseModel):
    org_id: str = Field(description="Short UUID string identifying the organization.")
    agent_id: str = Field(description="Short UUID string identifying the agent.")
    user_id: str = Field(description="Short UUID string identifying the user.")
    interaction_id: Optional[str] = Field(
        default=None,
        description="Short UUID string identifying the interaction where this memory was sourced from.",
    )
    memory_id: str = Field(description="Full UUID string identifying the memory.")
    memory: str = Field(description="The memory.")
    obtained_at: datetime = Field(
        description="DateTime object of when the memory was obtained."
    )
    message_sources: Optional[List[MessageBlock]] = Field(
        default=None,
        description="List of messages in the interaction that triggered the memory. (Note: A memory won't have a message source, if its interaction was updated with a conflicting conversation thread that lead to truncation of the former thread. See `graph.update_interaction_and_memories`)",
    )

    def id_memory_and_timestamp_dict(self):
        return {
            "memory_id": self.memory_id,
            "memory": self.memory,
            "obtained_at": str(self.obtained_at),
        }

    def memory_and_timestamp_dict(self):
        return {"memory": self.memory, "obtained_at": str(self.obtained_at)}
