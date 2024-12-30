# Memora Documentation

Memora is a sophisticated memory agent for AI systems, designed to emulate human memory capabilities. It enables AI systems to recall and connect information from past interactions, providing more contextual and personalized responses.

## Key Features

- **Contextual Memory**: Stores and retrieves memories based on context using both vector and graph databases
- **Multi-Modal Support**: Future-ready architecture designed to handle text, audio, and video memories
- **Flexible LLM Integration**: Supports multiple LLM backends including OpenAI, Azure OpenAI, Together AI, and Groq
- **Advanced Memory Processing**: Intelligent memory extraction and filtering capabilities
- **Cross-Agent Memory Sharing**: Ability to share and update memories across different agents

## Quick Start

```python
from memora import Memora
from memora.vector_db import YourVectorDB
from memora.graph_db import Neo4jGraphDB

# Initialize databases
vector_db = YourVectorDB(...)
graph_db = Neo4jGraphDB(...)

# Create Memora instance
memora = Memora(
    vector_db=vector_db,
    graph_db=graph_db
)

# Save an interaction and extract memories
interaction_id, memory_id = await memora.save_or_update_interaction_and_memories(
    org_id="your_org",
    user_id="user123",
    agent_id="agent456",
    interaction=[
        {"role": "user", "content": "My favorite color is blue"},
        {"role": "assistant", "content": "I'll remember that you like blue!"}
    ]
)

# Retrieve memories for context
memories = await memora.get_memories_for_message(
    org_id="your_org",
    user_id="user123",
    latest_msg="What's my favorite color?"
)
```

## Project Structure

```
memora/
├── agent/          # Core memory agent implementation
├── graph_db/       # Graph database interfaces
├── llm_backends/   # LLM provider implementations
├── prompts/        # System prompts for memory operations
├── schema/         # Data models and schemas
└── vector_db/      # Vector database interfaces
```

## Next Steps

- [Getting Started](getting_started.md) - Set up and run your first Memora instance
- [Configuration](configuration.md) - Configure Memora for your needs
- [API Reference](api_reference.md) - Detailed API documentation
- [Advanced Usage](advanced_usage.md) - Advanced features and customization
