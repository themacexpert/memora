MEMORY_EXTRACTION_SYSTEM_PROMPT = """
The Current Date & Time is {day_of_week}, {current_datetime_str}.
Given an interaction between ({agent_label}) and ({user_name}).

# OBJECTIVE: 
- Extract details about {user_name} {extract_for_agent} from the interaction to be stored in memory used to personalize future interactions.
- Ignore insignificant details that you are very certain will be unhelpful in future personalized responses.
- Never fabricate any detail not present or strongly implied in the interaction.

# MEMORY GUIDELINES:  
- Keep each memory descriptive, self-contained, not exceed 25 words.  
- Use proper tense (past, present, continuous) as appropriate.  
- Always use #user_#id# instead of ({user_name}) and #agent_#id# instead of ({agent_label}) in the memories. 
- Output must be JSON format using the schema:
{schema}


>>>>>>> ENTIRE INTERACTION IS BELOW <<<<<<<
"""