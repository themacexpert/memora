from typing import Optional
from pydantic import BaseModel, Field


class ExtractedMemory(BaseModel):
    memory: str = Field(
        description="The memory, max 25 words, self-contained, remember use of #user_#id# or #agent_#id#."
    )
    msg_source_ids: list[int] = Field(
        description="List with id or ids indicating which message blocks this memory was extracted from."
    )


class MemoryExtractionResponse(BaseModel):
    memories_first_pass: Optional[list[ExtractedMemory]] = Field(
        default_factory=list,
        description="First pass of useful info written for memory with their source message ids.",
    )
    memories_second_pass: Optional[list[ExtractedMemory]] = Field(
        default_factory=list,
        description="Second pass containing info missed in first pass with their source message ids, if any.",
    )
    memories_third_pass: Optional[list[ExtractedMemory]] = Field(
        default_factory=list,
        description="Third pass containing info missed in first and second passes with their source message ids, if any.",
    )


class NewGleanedMemory(BaseModel):
    memory: str = Field(
        description="A new gleaned memory, max 25 words, self-contained."
    )
    source_candidate_pos_id: int = Field(
        description="The POS_ID of the candidate memory from which this new memory was gleaned."
    )


class ContraryMemory(BaseModel):
    memory: str = Field(
        description="The candidate memory that directly contradicting an existing memory, max 25 words, self-contained."
    )
    source_candidate_pos_id: int = Field(
        description="The POS_ID of the candidate memory from which this contrary memory was sourced."
    )
    contradicted_memory_id: str = Field(
        description="The ID of the existing memory that was contradicted."
    )


class MemoryComparisonResponse(BaseModel):
    new_memories: list[NewGleanedMemory] = Field(
        description="List of newly gleaned memories."
    )
    contrary_memories: list[ContraryMemory] = Field(
        description="List of candidate memories that contradict existing ones, if any."
    )
