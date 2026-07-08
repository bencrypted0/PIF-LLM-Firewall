import os
import logging
import httpx
from datetime import datetime, timezone
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import detection methods
from signatures import detect_signatures
from classifier import detect_classifier
from redactor import redact_sensitive_info

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("firewall")

app = FastAPI(
    title="Prompt Injection Firewall",
    description="A security proxy that filters incoming requests for prompt injections before forwarding them to the AI agent.",
    version="1.0.0",
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

GENERIC_REFUSAL = "I can't help with that request."

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    user_id: str | None = None

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """Intercepts and scans chat queries, then forwards clean prompts to the backend."""
    logger.info("Scanning incoming chat message...")
    user_id = request.user_id or "anonymous"
    
    # 1. Run signature-based detection first
    is_blocked, signature_reason = detect_signatures(request.message)
    if is_blocked:
        logger.warning({
            "event": "prompt_injection_detected",
            "layer": "signature",
            "matched_pattern": signature_reason,
            "user_id": user_id,
            "message": request.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "blocked"
        })
        return {
            "response": GENERIC_REFUSAL,
            "model": "firewall"
        }
        
    # 2. Fall back to classifier-based detection if signature check is clean
    is_blocked, classifier_reason = detect_classifier(request.message)
    if is_blocked:
        logger.warning({
            "event": "prompt_injection_detected",
            "layer": "classifier",
            "matched_pattern": classifier_reason,
            "user_id": user_id,
            "message": request.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "blocked"
        })
        return {
            "response": GENERIC_REFUSAL,
            "model": "firewall"
        }
        
    logger.info(f"CLEAN: Forwarding query to backend at {BACKEND_URL}/chat")
    
    # Forward the request to the actual backend
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{BACKEND_URL}/chat",
                json=request.model_dump(),
            )
            
            if response.status_code == 200:
                resp_json = response.json()
                if "response" in resp_json and isinstance(resp_json["response"], str):
                    redacted_text, redacted_types = redact_sensitive_info(resp_json["response"])
                    if redacted_types:
                        logger.warning({
                            "event": "sensitive_content_redacted",
                            "redacted_types": redacted_types,
                            "user_id": user_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "action": "redacted"
                        })
                        resp_json["response"] = redacted_text
                return JSONResponse(status_code=response.status_code, content=resp_json)
                
            return JSONResponse(status_code=response.status_code, content=response.json())
            
        except httpx.RequestError as exc:
            print(f"[FIREWALL /chat] Error forwarding request: {exc}")
            raise HTTPException(status_code=502, detail=f"Failed to connect to backend server: {exc}")

@app.get("/health")
async def health_proxy():
    """Proxy health check to backend."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{BACKEND_URL}/health")
            return JSONResponse(status_code=response.status_code, content=response.json())
        except Exception as exc:
            return JSONResponse(
                status_code=503,
                content={"status": "firewall_only_ok", "error": f"Backend unreachable: {exc}"}
            )

@app.get("/models")
async def models_proxy():
    """Proxy models list to backend."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{BACKEND_URL}/models")
            return JSONResponse(status_code=response.status_code, content=response.json())
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Failed to contact backend: {exc}")

class SelectModelRequest(BaseModel):
    model: str

@app.post("/models/select")
async def select_model_proxy(request: SelectModelRequest):
    """Proxy model selection to backend."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                f"{BACKEND_URL}/models/select",
                json=request.model_dump()
            )
            return JSONResponse(status_code=response.status_code, content=response.json())
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Failed to contact backend: {exc}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000)
