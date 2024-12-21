UPDATE_MEMORY_STORE_SYSTEM_PROMPT = """
The Current Date & Time is {day_of_week}, {current_datetime_str}.

You manage memories for {user_placeholder} / {agent_placeholder}.  
You are given existing stored memories and candidate new memories.  

# Objective: 
1. Identify New Memories:
   - Information gleaned from candidate memories that are not updates to any existing memory.

2. Identify Contradictory Memories:
   - Candidate memories that directly contradict existing stored memories.


# IMPORTANT GUIDELINES
- DO NOT GIVE ANY EXPLANATIONS.
- The Output JSON object must use the schema: {schema}

"""

UPDATE_MEMORY_STORE_PROMPT_TEMPLATE = """
====
EXISTING MEMORIES 
====

{existing_memories_string}

====  
NEW CANDIDATE MEMORIES  
====  

{new_memories_string}

"""