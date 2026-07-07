#!/usr/bin/env python3
"""
Startup script for the PIF Agent.
Validates Ollama connectivity before launching the server.
"""

import sys
import os
import subprocess

def check_ollama():
    """Verify Ollama is reachable before starting."""
    import urllib.request
    import urllib.error

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        req = urllib.request.urlopen(f"{base_url}/api/tags", timeout=5)
        return True
    except urllib.error.URLError:
        print(f"\nWARNING: Ollama not reachable at {base_url}")
        print("   Make sure your Ollama container is running:")
        print("   cd ollama && docker compose up -d")
        print("   Starting server anyway...\n")
        return False


if __name__ == "__main__":
    # Load .env
    from dotenv import load_dotenv
    load_dotenv()

    check_ollama()

    # Trigger document ingestion sync
    try:
        from agent.ingest import ingest_documents
        ingest_documents()
    except Exception as e:
        print(f"\nWARNING: Document ingestion sync failed: {e}")
        print("Starting server anyway...\n")

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    print(f"Starting PIF Agent on http://{host}:{port}")
    print(f"Model: {os.getenv('OLLAMA_MODEL', 'llama3.2')}")
    print(f"Ollama: {os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}")
    print(f"Open http://localhost:{port} in your browser\n")

    import uvicorn
    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )
