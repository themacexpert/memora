from typing import Optional
from pydantic import BaseModel, Field

MSG_BLOCK_FORMAT = """
# MESSAGE BLOCK ID: {message_id}
-------------
{content}
"""

class Memory(BaseModel):
    memory: str = Field(description="The memory, max 25 words, self-contained, remember use of #user_#id# or #agent_#id#")
    message_ids: list[int] = Field(description="List with id or ids indicating which message blocks this memory was extracted from")

class ExtractionMemoryResponse(BaseModel):
    memories_first_pass: Optional[list[Memory]] = Field(default_factory=list, description="First pass of useful info written for memory with their source message ids")
    memories_second_pass: Optional[list[Memory]] = Field(default_factory=list, description="Second pass containing info missed in first pass with their source message ids, if any") 
    memories_third_pass: Optional[list[Memory]] = Field(default_factory=list, description="Third pass containing info missed in first and second passes with their source message ids, if any")






class NewGleanedMemory(BaseModel):
    memory: str = Field(..., description="A new gleaned memory, max 25 words, self-contained.")
    source_candidate_pos_id: int = Field(description="The POS_ID of the candidate memory from which this new memory was gleaned.")

class ContradictoryMemory(BaseModel):
    memory: str = Field(..., description="The candidate memory that directly contradicting an existing memory, max 25 words, self-contained.")
    source_candidate_pos_id: int = Field(description="The POS_ID of the candidate memory from which this new memory was gleaned.")
    contradicted_memory_id: str = Field(..., description="The ID of the existing memory that was contradicted.")

class UpdateToMemoryStore(BaseModel):
    new_memories: list[NewGleanedMemory] = Field(..., description="A list of newly gleaned memories.")
    contradictory_memories: list[ContradictoryMemory] = Field(..., description="A list of candidate memories that contradict existing ones, if any.")
