import os
import glob
import time
from pypdf import PdfReader

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import Qdrant
from qdrant_client import QdrantClient
from qdrant_client.http import models

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
COLLECTION_NAME = "pif_documents"

# Find documents directory (fallback to local if not running in container)
DOCUMENTS_DIR = "/app/documents" if os.path.exists("/app/documents") else os.path.join(os.path.dirname(os.path.dirname(__file__)), "documents")


def load_pdf(file_path: str) -> list[Document]:
    """Load PDF text page by page into LangChain Document objects."""
    try:
        reader = PdfReader(file_path)
        documents = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                # We store just the filename in metadata for easy counting/filtering
                doc = Document(
                    page_content=text,
                    metadata={"source": os.path.basename(file_path), "page": i + 1}
                )
                documents.append(doc)
        return documents
    except Exception as e:
        print(f"Error loading PDF {file_path}: {e}")
        return []


def wait_for_services():
    """Wait until Ollama and Qdrant are reachable."""
    client = QdrantClient(url=QDRANT_URL)
    print(f"Connecting to Qdrant at {QDRANT_URL}...")
    qdrant_ok = False
    for i in range(30):
        try:
            # Simple ping
            client.get_collections()
            qdrant_ok = True
            print("Connected to Qdrant successfully.")
            break
        except Exception:
            print(f"Waiting for Qdrant service... ({i+1}/30)")
            time.sleep(2)
    
    if not qdrant_ok:
        raise ConnectionError(f"Could not connect to Qdrant at {QDRANT_URL}")

    # Check Ollama connection
    import httpx
    print(f"Connecting to Ollama at {OLLAMA_BASE_URL}...")
    ollama_ok = False
    for i in range(30):
        try:
            resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
            if resp.status_code == 200:
                ollama_ok = True
                print("Connected to Ollama successfully.")
                break
        except Exception:
            print(f"Waiting for Ollama service... ({i+1}/30)")
            time.sleep(2)
            
    if not ollama_ok:
        raise ConnectionError(f"Could not connect to Ollama at {OLLAMA_BASE_URL}")


def ingest_documents():
    """Scan documents directory and ingest new PDFs into Qdrant."""
    print("=== Starting Document Ingestion Sync ===")
    
    # Ensure directories and services are ready
    if not os.path.exists(DOCUMENTS_DIR):
        print(f"Documents directory '{DOCUMENTS_DIR}' not found. Creating it.")
        os.makedirs(DOCUMENTS_DIR, exist_ok=True)

    try:
        wait_for_services()
    except Exception as e:
        print(f"Startup check failed: {e}")
        return

    # Check for PDF files
    pdf_files = glob.glob(os.path.join(DOCUMENTS_DIR, "*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in '{DOCUMENTS_DIR}'. Ingestion sync completed (0 files).")
        return

    print(f"Found {len(pdf_files)} PDF files in '{DOCUMENTS_DIR}'. Checking index status...")

    # Initialize Qdrant client
    client = QdrantClient(url=QDRANT_URL)
    
    # Initialize embeddings
    embeddings = OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_BASE_URL
    )

    # Initialize text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        
        # Check if already ingested by counting matching metadata points in Qdrant
        try:
            collections = client.get_collections().collections
            collection_exists = any(c.name == COLLECTION_NAME for c in collections)
            
            if collection_exists:
                # Query count of points matching this source
                count_res = client.count(
                    collection_name=COLLECTION_NAME,
                    count_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="metadata.source",
                                match=models.MatchValue(value=filename)
                            )
                        ]
                    )
                )
                if count_res.count > 0:
                    print(f"-> Skipping '{filename}': already has {count_res.count} chunks indexed.")
                    continue
        except Exception as e:
            print(f"Error checking status for {filename}: {e}. Proceeding with indexing.")

        print(f"-> Indexing '{filename}'...")
        docs = load_pdf(pdf_path)
        if not docs:
            print(f"No readable content found in '{filename}'.")
            continue

        chunks = text_splitter.split_documents(docs)
        print(f"Split '{filename}' into {len(chunks)} text chunks.")

        try:
            # Upload to Qdrant
            Qdrant.from_documents(
                documents=chunks,
                embedding=embeddings,
                url=QDRANT_URL,
                collection_name=COLLECTION_NAME
            )
            print(f"Successfully indexed '{filename}' ({len(chunks)} chunks).")
        except Exception as e:
            print(f"Failed to index '{filename}': {e}")

    print("=== Document Ingestion Sync Completed ===")


if __name__ == "__main__":
    ingest_documents()
