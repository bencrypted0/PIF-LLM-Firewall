# PIF Agent — Unfinished Features & Roadmap

This document outlines the current limitations, planned features, and incomplete components of the PIF Agent project.

---

## 1. Model Switching & Management
- **Inactive Selector**: The sidebar displays available local Ollama models (e.g., `llama3.2`), but clicking a model does not update the active model on the backend. The backend currently uses a hardcoded environment variable `OLLAMA_MODEL` set at startup.
- **Model Pulling**: There is no UI or API endpoint to download/pull new models (e.g., `ollama pull qwen2.5`) directly from the frontend.

## 2. Real-Time Streaming
- **No Streaming Implementation**: The backend and frontend are configured for standard, non-streaming request-response operations. The UI displays a typing/thinking indicator and waits for the complete response to be returned as a single payload before rendering.
- **True Token Streaming**: Real-time token-by-token streaming is not implemented. Implementing this would require refactoring the LangGraph chatbot nodes to support stream callbacks (e.g., using `astream_events` or streaming the generator output of Ollama directly) and wrapping it in an SSE or WebSocket endpoint.

## 3. Persistent History & Sessions
- **In-Memory History**: Conversations are kept purely in the frontend's JavaScript state (`state.history`). Refreshing the browser or opening a new tab completely clears the conversation.
- **Database Integration**: A local database (like SQLite) is needed to persist chats, store previous conversations, and load a conversation list in the sidebar.

## 4. Advanced Agent Capabilities & Tools
- **Static Tools**: The three default tools (`calculator`, `get_current_time`, `word_count`) are hardcoded. There is no system in place to register new tools dynamically, configure tool parameters, or toggle tools on/off from the frontend.
- **Interactive UI Document Uploads**: While the agent now automatically syncs and indexes PDFs placed in the `/app/documents` folder at startup, there is no UI file upload button to upload and embed files interactively on the fly.
- **Single-Agent System**: The architecture is a simple ReAct loop. There is no multi-agent orchestration, human-in-the-loop approvals, or complex state routing.

## 5. Security & Isolation
- **No Authentication**: The FastAPI server has no auth guards. Anyone on the local network can access the UI and prompt the agent.
- **Calculator Sandbox**: The calculator tool uses basic string validation before running Python's `eval()`. A fully secure, isolated sandbox or a formal math parser is needed for robust math evaluation.

## 6. Frontend UI/UX Enhancements
- **Basic Markdown Parser**: The frontend uses a custom regular expression parser for simple formatting (`**bold**`, `*italic*`, `code blocks`). It does not render lists, nested tables, blockquotes, or complex inline syntax cleanly.
- **Configuration Panel**: No settings modal exists to adjust agent hyperparameters (e.g., temperature, top_k, system prompts) or override the Ollama API base URL.
