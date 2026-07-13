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

def get_signature_category(reason: str) -> str:
    reason_lower = reason.lower()
    if "delimiter" in reason_lower:
        return "delimiter"
    elif "role-play" in reason_lower or "persona" in reason_lower:
        return "roleplay"
    elif "injection" in reason_lower:
        return "injection"
    elif "base64" in reason_lower:
        if "delimiter" in reason_lower:
            return "base64_delimiter"
        elif "role-play" in reason_lower or "persona" in reason_lower:
            return "base64_roleplay"
        elif "injection" in reason_lower:
            return "base64_injection"
        return "base64"
    return "signature"

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
            "action": "blocked",
            "layer": "signature",
            "detection_type": get_signature_category(signature_reason),
            "matched_pattern": signature_reason,
            "user_id": user_id,
            "message": request.message
        })
        return {
            "response": GENERIC_REFUSAL,
            "model": "firewall"
        }
        
    # 2. Fall back to classifier-based detection if signature check is clean
    is_blocked, classifier_reason = detect_classifier(request.message)
    if is_blocked:
        logger.warning({
            "action": "blocked",
            "layer": "classifier",
            "matched_pattern": classifier_reason,
            "user_id": user_id,
            "message": request.message
        })
        return {
            "response": GENERIC_REFUSAL,
            "model": "firewall"
        }
        
    logger.info({
        "action": "allowed",
        "user_id": user_id,
        "message": request.message
    })
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000)
