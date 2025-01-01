FILTER_RETRIEVED_MEMORIES_SYSTEM_PROMPT = """
The Current Date & Time is {day_of_week}, {current_datetime_str}.

This is the latest message sent to the room where an Agent and User are interacting:
Latest Message to Room: 
{latest_room_message}

These are the memory search queries based on the latest message:
Memory Search Queries: 
- {memory_search_queries}

You will receive the results of these memory search queries. Based on both the latest message and the results of the memory search queries, output the relevant memory_id (UUIDs) in the following format:

REASONS AND JUST memory_id enclosed in (<< >>):
- Reason: ... || << ... (just memory_id of a relevant memory here)>>
- Reason: ... || << ... >>

# If no relevant memory_id are found, output:
REASONS AND JUST memory_id enclosed in (<< >>):
- Reason: ... || << NONE >>
"""
