# API Reference

> :information_source: This is the API Reference. For most users, the [Getting Started](getting_started.md) or [Advanced Usage](advanced_usage.md) guides are the go-to resources for effectively using the library. However, if you need a deeper understanding of Memora's components, you're in the right place.

## Components

### [:material-brain: Agent](agent/memora.md)
The `Memora` class orchestrates all necessary memory operations and offers a unified interface for utilizing the Memory Agent.

### [:octicons-ai-model-24: Graph Database](graph_db/base.md)
Currently, our graph database implementation focuses on storing organizations, agents, users, their interactions with the agent (messages), and the memories derived from these interactions, all with date and time etc.

### [:octicons-database-24: Vector Database](vector_db/base.md)
Enables semantic search across memories using dense vector embeddings for semantic similarity, combined with sparse text embeddings (like SPLADE) for hybrid search.

### [:octicons-dependabot-24: LLM Backends](llm_backends/base.md)
An interface for LLM providers, along with some implementations, that Memora can use in the backend for memory operations, such as understanding context, determining what to store and recall, linking memories to source messages and more.

### [:octicons-file-code-24: Schemas](schema/extraction.md)
Pydantic data models that are used for structured memory extraction, storage, and retrieval to ensure consistency and model structured output.

### [:octicons-comment-discussion-24: Prompts](prompts/extraction.md)
System prompts and input templates used by the LLM in various memory operations.