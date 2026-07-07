"""
FastAPI backend server for the LangGraph AI Agent.

Provides REST endpoints for the chat interface.
"""

import asyncio

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.agent import chat, llm, OLLAMA_BASE_URL, get_active_model, set_active_model

import os

app = FastAPI(
    title="LangGraph Ollama Agent",
    description="A local AI agent powered by LangGraph and Ollama",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class ChatResponse(BaseModel):
    response: str
    model: str


class HealthResponse(BaseModel):
    status: str
    model: str
    ollama_url: str


# Routes


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check if the agent and Ollama are reachable."""
    try:
        # Quick ping to Ollama
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            ollama_ok = resp.status_code == 200
    except Exception:
        ollama_ok = False

    return HealthResponse(
        status="ok" if ollama_ok else "ollama_unreachable",
        model=get_active_model(),
        ollama_url=OLLAMA_BASE_URL,
    )


def is_conversational_model(model_name: str) -> bool:
    """Helper to exclude text embedding models from list of chat models."""
    name_lower = model_name.lower()
    embedding_indicators = ["embed", "bge-", "minilm", "colbert"]
    return not any(indicator in name_lower for indicator in embedding_indicators)


@app.get("/models")
async def list_models():
    """List available models from the Ollama instance."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [
                    m["name"] 
                    for m in data.get("models", []) 
                    if is_conversational_model(m["name"])
                ]
                return {"models": models, "current": get_active_model()}
    except Exception as e:
        return JSONResponse(status_code=503, content={"error": str(e)})


class SelectModelRequest(BaseModel):
    model: str


@app.post("/models/select")
async def select_model_endpoint(request: SelectModelRequest):
    """Dynamically switch the active model on the backend."""
    try:
        # Verify model exists in Ollama
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                models = [
                    m["name"] 
                    for m in resp.json().get("models", []) 
                    if is_conversational_model(m["name"])
                ]
                if request.model not in models:
                    return JSONResponse(
                        status_code=400,
                        content={"error": f"Model '{request.model}' is not a valid conversational model."}
                    )
        
        set_active_model(request.model)
        return {"status": "success", "model": get_active_model()}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Non-streaming chat endpoint."""
    print(f"\n[HTTP POST /chat]")
    print(f"Message: {repr(request.message)}")
    print(f"History: {request.history}\n")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, chat, request.message, request.history
    )
    return ChatResponse(response=result["response"], model=get_active_model())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
