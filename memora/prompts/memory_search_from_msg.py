MSG_MEMORY_SEARCH_PROMPT = """
You are a memory agent. Your task is to generate memory search queries based on the latest message to the room.

Input:
- Latest message to the room
- Previous conversation messages (if provided, and is useful for context)

Instructions:
1. Generate at least 3 search queries to retrieve relevant memories for (the message, entities, relationships, patterns etc.)
2. Focus only on memory needs for the latest message
3. No explanations or responses - just search queries

Response Format:
&& MEMORY_SEARCH &&
    << Detailed memory search query >>
    << ... >>

Random Example (JUST EXAMPLE DO NOT USE ANY INFO HERE):
&& MEMORY_SEARCH &&
    << Ava vacation in San Francisco with Sarah >>
    << Ava and Sarah's visit to the Golden Gate Bridge >>
    << Sarah planning a trip with John >>
"""

MSG_MEMORY_SEARCH_TEMPLATE = """
# Preceding Messages
---
{preceding_messages}
---

# Latest Message For Retrieval Decision (DateTime: {day_of_week}, {current_datetime_str})
---
{message_of_user}
---
"""
