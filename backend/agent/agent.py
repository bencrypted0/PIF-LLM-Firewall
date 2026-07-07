"""
Core LangGraph AI Agent using a local Ollama LLM.

This agent uses the default LangGraph ReAct pattern with no additional
security layers or guardrails — it behaves exactly as a stock LangGraph agent.
"""

import os
from typing import Annotated

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

load_dotenv()

def resolve_model_name(base_url: str, default_model: str) -> str:
    """Check available models from Ollama and find the best match for the configured model name."""
    try:
        import urllib.request
        import json
        
        # Query local Ollama API
        url = f"{base_url}/api/tags"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                available_models = [m["name"] for m in data.get("models", [])]
                if not available_models:
                    return default_model
                
                # 1. Exact match
                if default_model in available_models:
                    return default_model
                
                # 2. Tag prefix/suffix match (e.g. "qwen3.5" -> "qwen3.5:0.8b")
                for m in available_models:
                    if m.startswith(f"{default_model}:"):
                        return m
                
                # 3. Clean and match (e.g. "llama3.2:latest" -> "llama3.2" or vice-versa)
                clean_default = default_model.split(":")[0]
                for m in available_models:
                    if m.split(":")[0] == clean_default:
                        return m
                
                # 4. Fallback to first available model
                return available_models[0]
    except Exception:
        # Fallback to default if Ollama is unreachable or any exception occurs
        pass
    return default_model


# ── Configuration ─────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL_CONFIG = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_MODEL = resolve_model_name(OLLAMA_BASE_URL, OLLAMA_MODEL_CONFIG)


# ── State Definition ──────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# ── Tools ─────────────────────────────────────────────────────────────────────
@tool
def calculator(expression: str) -> str:
    """Evaluate a basic math expression. Input should be a valid Python math expression.
    Example: '2 + 2', '10 * 5 / 2', '(3 + 4) ** 2'
    """
    try:
        # Restrict to safe math evaluation
        allowed = set("0123456789+-*/().% ")
        if not all(c in allowed for c in expression):
            return "Error: Only basic math operators are allowed."
        result = eval(expression, {"__builtins__": {}})  # noqa: S307
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {e}"


@tool
def get_current_time() -> str:
    """Returns the current date and time."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def word_count(text: str) -> str:
    """Count the number of words in a given text."""
    words = text.split()
    return f"The text contains {len(words)} words."


@tool
def search_documents(query: str) -> str:
    """Semantic search tool to query local documents and PDF contents.
    Use this tool whenever the user asks questions about uploaded documents, PDFs,
    internal projects, corporate reports, or information that requires search in the files.
    """
    try:
        from langchain_ollama import OllamaEmbeddings
        from langchain_qdrant import Qdrant
        from qdrant_client import QdrantClient

        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        embedding_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
        collection_name = "pif_documents"

        # Check if collection exists
        client = QdrantClient(url=qdrant_url)
        collections = client.get_collections().collections
        if not any(c.name == collection_name for c in collections):
            return "No documents have been indexed yet. Please add PDF files to the documents folder and restart the system."

        # Connect to existing Qdrant store
        embeddings = OllamaEmbeddings(
            model=embedding_model,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )
        
        db = Qdrant(
            client=client,
            collection_name=collection_name,
            embeddings=embeddings
        )

        # Retrieve top 4 most relevant chunks
        results = db.similarity_search(query, k=4)
        if not results:
            return "No matching information found in the documents."

        # Format matches
        formatted_results = []
        for i, doc in enumerate(results):
            source = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "Unknown")
            formatted_results.append(f"[Source: {source}, Page: {page}]\n{doc.page_content}")

        return "\n\n---\n\n".join(formatted_results)
    except Exception as e:
        return f"Error searching documents: {e}"


# ── LLM + Tools Setup ─────────────────────────────────────────────────────────
tools = [calculator, get_current_time, word_count, search_documents]

llm = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.7,
)

llm_with_tools = llm.bind_tools(tools)


def load_system_prompt() -> str:
    """Load the system prompt instructions from system_prompt.md."""
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "system_prompt.md")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"WARNING: Could not load system_prompt.md: {e}. Using fallback prompt.")
        return """You are a helpful AI assistant powered by a local Ollama model.
                    You have access to the following tools:
                    - calculator: evaluate math expressions
                    - get_current_time: get the current date and time
                    - word_count: count words in text
                    - search_documents: semantically search the text and information inside local uploaded PDF documents and reports

                    Use tools when they are helpful. If the user asks questions about uploaded documents, projects, or local files, 
                    always search them using search_documents before answering. Be concise and accurate in your responses."""

SYSTEM_PROMPT = load_system_prompt()


def chatbot(state: AgentState) -> AgentState:
    """Main chatbot node that calls the LLM."""
    messages = state["messages"]

    # Prepend system message if not already present
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


# ── Graph Construction ────────────────────────────────────────────────────────
def build_graph() -> StateGraph:
    graph_builder = StateGraph(AgentState)

    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("tools", ToolNode(tools))

    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition,
    )
    graph_builder.add_edge("tools", "chatbot")

    return graph_builder.compile()


# Singleton compiled graph
graph = build_graph()


# ── Public API ────────────────────────────────────────────────────────────────
def chat(user_message: str, conversation_history: list[dict] | None = None) -> dict:
    """
    Send a message to the agent and get a response.

    Args:
        user_message: The user's input message.
        conversation_history: Optional list of previous messages in the format
                              [{"role": "user"|"assistant", "content": "..."}]

    Returns:
        dict with keys: "response" (str), "messages" (list)
    """
    messages = []

    # Reconstruct history
    if conversation_history:
        for msg in conversation_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

    # Add current user message
    messages.append(HumanMessage(content=user_message))

    result = graph.invoke({"messages": messages})

    # Extract the final AI response
    final_message = result["messages"][-1]
    response_text = final_message.content if hasattr(final_message, "content") else str(final_message)

    return {
        "response": response_text,
        "messages": result["messages"],
    }


def get_active_model() -> str:
    """Get the active Ollama model name."""
    return llm.model


def set_active_model(model_name: str) -> None:
    """Set the active Ollama model name."""
    global llm
    llm.model = model_name
