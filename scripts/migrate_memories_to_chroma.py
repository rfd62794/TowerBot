"""Migrate existing SQLite memories to Chroma for semantic search.

Idempotent: safe to re-run. Chroma upserts replace existing documents.
"""

import os
import sys
from pathlib import Path

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))

from dotenv import load_dotenv
load_dotenv(_root / ".env")

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

from infra.db import init_db, list_memories

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"
COLLECTION_NAME = "privybot"
CHROMA_PATH = _root / "privy_chroma_db"


def main():
    print("Initializing database...")
    init_db()

    print(f"Loading Chroma client from {CHROMA_PATH}...")
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    embedding_fn = OllamaEmbeddingFunction(
        url=f"{OLLAMA_HOST}/api/embeddings",
        model_name=EMBED_MODEL,
    )
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )

    print("Fetching active memories from SQLite...")
    memories = list_memories()
    print(f"Found {len(memories)} active memories.")

    if not memories:
        print("No memories to migrate. Done.")
        return

    print("Upserting to Chroma (this may take a moment for embeddings)...")
    ids = []
    documents = []
    metadatas = []

    for mem in memories:
        key = mem["key"]
        content = mem["content"]
        layer = mem["layer"]
        ids.append(key)
        documents.append(content)
        metadatas.append({"layer": layer, "key": key})

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    print(f"Migrated {len(ids)} memories to Chroma collection '{COLLECTION_NAME}'.")
    print("Done.")


if __name__ == "__main__":
    main()
