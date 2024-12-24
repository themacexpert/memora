MSG_MEMORY_SEARCH_PROMPT ="""
You are {agent_label}'s memory agent. Your task is to generate memory search queries based on the latest message from {user_name}.

Input:
- Latest message from {user_name}
- Previous conversation messages (if provided, and is useful for context)

Instructions:
1. Generate at least 2 search queries to retrieve relevant memories for responding
2. Use 'agent' / 'user' instead of {agent_label} or {user_name} in the query
3. Focus only on memory needs for the latest message
4. No explanations or responses - just search queries

Response Format:
&& MEMORY_SEARCH &&
    << Detailed memory search query >>
    << ... >>

Random Example (JUST EXAMPLE DO NOT USE ANY INFO HERE):
&& MEMORY_SEARCH &&
    << user vacation in San Francisco with Sarah >>
    << user and Sarah's visit to the Golden Gate Bridge >>
    << Sarah planning a trip with user >>
"""

MSG_MEMORY_SEARCH_TEMPLATE = """
# Preceding Messages
```
{preceding_messages}
```

# Latest Message For Retrieval Decision (DateTime: {day_of_week}, {current_datetime_str})
```
{message_of_user}
```
""" 
