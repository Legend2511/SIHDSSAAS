"""
WeatherGPT — RAG (Retrieval-Augmented Generation) Service

Uses sentence-transformers (all-MiniLM-L6-v2) for embeddings and a lightweight
JSON-file-based vector store. This avoids heavy dependencies like chromadb/onnxruntime
while providing identical retrieve(query, k) interface.

When Docker is available, swap in Qdrant by changing only init_vector_db()
and retrieve() — the rest of the app doesn't know or care.
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

import numpy as np

# Lazy-loaded to avoid slow import at startup
_model = None
_collection = None  # {"ids": [], "documents": [], "metadatas": [], "embeddings": []}
_STORE_PATH = None


def _get_model():
    """Lazy-load the sentence-transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _store_path() -> Path:
    """Path to the persisted vector store JSON file."""
    global _STORE_PATH
    if _STORE_PATH is None:
        from app.core.config import settings
        _STORE_PATH = Path(settings.chroma_persist_dir) / "weathergpt_kb.json"
    return _STORE_PATH


def init_vector_db():
    """Initialize the vector store — load from disk if it exists."""
    global _collection
    path = _store_path()
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            _collection = json.load(f)
        print(f"   📚 Loaded {len(_collection['ids'])} vectors from {path}")
    else:
        _collection = {"ids": [], "documents": [], "metadatas": [], "embeddings": []}
        print(f"   📚 Empty vector store initialized (run seed_vector_db.py to populate)")


def _save_store():
    """Persist the vector store to disk."""
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_collection, f, ensure_ascii=False)


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[dict]:
    """
    Split text into overlapping chunks, preserving section structure.
    Returns list of {"text": ..., "section": ...}.
    """
    chunks = []
    # Split on section headers (## or #)
    sections = re.split(r'\n(?=#+\s)', text)

    for section in sections:
        lines = section.strip().split('\n')
        if not lines:
            continue

        # Extract section title
        section_title = ""
        if lines[0].startswith('#'):
            section_title = lines[0].lstrip('#').strip()
            lines = lines[1:]

        section_text = '\n'.join(lines).strip()
        if not section_text:
            continue

        # If section is small enough, keep as one chunk
        if len(section_text) <= chunk_size:
            chunks.append({"text": section_text, "section": section_title})
        else:
            # Split into overlapping chunks by sentences
            sentences = re.split(r'(?<=[.!?])\s+', section_text)
            current_chunk = []
            current_len = 0

            for sentence in sentences:
                if current_len + len(sentence) > chunk_size and current_chunk:
                    chunks.append({
                        "text": ' '.join(current_chunk),
                        "section": section_title,
                    })
                    # Keep last sentence for overlap
                    overlap_start = max(0, len(current_chunk) - 2)
                    current_chunk = current_chunk[overlap_start:]
                    current_len = sum(len(s) for s in current_chunk)

                current_chunk.append(sentence)
                current_len += len(sentence)

            if current_chunk:
                chunks.append({
                    "text": ' '.join(current_chunk),
                    "section": section_title,
                })

    return chunks


def embed_and_index(texts: list[str], metadatas: list[dict]):
    """
    Embed text chunks and add them to the vector store.
    """
    global _collection
    if _collection is None:
        init_vector_db()

    model = _get_model()
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

    start_id = len(_collection["ids"])
    for i, (text, meta, emb) in enumerate(zip(texts, metadatas, embeddings)):
        _collection["ids"].append(f"chunk_{start_id + i}")
        _collection["documents"].append(text)
        _collection["metadatas"].append(meta)
        _collection["embeddings"].append(emb.tolist())

    _save_store()
    print(f"   📚 Indexed {len(texts)} chunks (total: {len(_collection['ids'])})")


def seed_knowledge_base():
    """
    Read all .txt files from the knowledge_base directory,
    chunk them, and index into the vector store.
    """
    global _collection
    # Clear existing data
    _collection = {"ids": [], "documents": [], "metadatas": [], "embeddings": []}

    kb_dir = Path(__file__).parent.parent / "data" / "knowledge_base"
    if not kb_dir.exists():
        print(f"   ⚠️  Knowledge base directory not found: {kb_dir}")
        return

    all_texts = []
    all_metas = []

    for filepath in sorted(kb_dir.glob("*.txt")):
        print(f"   📄 Processing: {filepath.name}")
        content = filepath.read_text(encoding="utf-8")
        source_name = filepath.stem  # e.g. "imd_alert_definitions"

        chunks = _chunk_text(content)
        for chunk in chunks:
            all_texts.append(chunk["text"])
            all_metas.append({
                "source": source_name,
                "section": chunk["section"],
                "file": filepath.name,
            })

    if all_texts:
        embed_and_index(all_texts, all_metas)
        print(f"   ✅ Knowledge base seeded: {len(all_texts)} chunks from {len(list(kb_dir.glob('*.txt')))} files")
    else:
        print("   ⚠️  No text files found in knowledge base directory")


def retrieve(query: str, k: int = 3) -> list[dict]:
    """
    Retrieve the top-k most relevant chunks for a query.
    Returns list of {"text": ..., "source": ..., "section": ..., "score": ...}.
    """
    global _collection
    if _collection is None:
        init_vector_db()

    if not _collection or not _collection["embeddings"]:
        return []

    model = _get_model()
    query_embedding = model.encode([query], normalize_embeddings=True)[0]

    # Cosine similarity (embeddings are already normalized, so dot product = cosine)
    store_embeddings = np.array(_collection["embeddings"])
    similarities = np.dot(store_embeddings, query_embedding)

    # Get top-k indices
    top_indices = np.argsort(similarities)[-k:][::-1]

    results = []
    for idx in top_indices:
        results.append({
            "text": _collection["documents"][idx],
            "source": _collection["metadatas"][idx].get("source", "unknown"),
            "section": _collection["metadatas"][idx].get("section", ""),
            "score": float(similarities[idx]),
        })

    return results
