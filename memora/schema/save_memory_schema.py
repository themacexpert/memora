from pydantic import BaseModel, Field
from datetime import datetime


class MemoryToStore(BaseModel):
    memory: str
    source_msg_block_pos: list[int] = Field(
        description="The position of the message block that resulted in this memory."
    )


class ContraryMemoryToStore(MemoryToStore):
    existing_contrary_memory_id: str = Field(
        description="The memory_id of the existing memory that was contradicted."
    )


class MemoriesAndInteraction(BaseModel):
    """
    Contains both the interaction, its date and the associated memories to store in memory stores.
    """

    interaction: list[dict[str, str]] = Field(
        default=[],
        description="The messages in the interaction [{'role': 'user', 'content': 'hello'}, ...]",
    )
    interaction_date: datetime = Field(
        default=datetime.now(),
        description="The date and time the interaction occurred.",
    )
    memories: list[MemoryToStore] = Field(
        default=[],
        description="The memories extracted from the interaction with their source messages position.",
    )
    contrary_memories: list[ContraryMemoryToStore] = Field(
        default=[],
        description="The memory extracted from the interaction with the above but also the memory id of the existing memory they contradicted.",
    )
