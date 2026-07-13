"""
ChromaDB vector store for RAG pipeline.
Stores text chunks as embeddings and provides similarity search.
"""
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
import django
import os

# ChromaDB persistent storage path
CHROMA_PATH = Path(__file__).resolve().parent.parent / 'media' / 'chromadb'


def get_chroma_client():
    """Return a persistent ChromaDB client."""
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_PATH))


def get_embedding_function():
    """Return sentence-transformers embedding function."""
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )


def get_collection(textbook_id: str):
    """Get or create a ChromaDB collection for a specific textbook."""
    client = get_chroma_client()
    ef = get_embedding_function()
    collection_name = f"textbook_{str(textbook_id).replace('-', '_')}"
    return client.get_or_create_collection(
        name=collection_name,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def index_chunks(textbook_id: str, chapter_number: int, chunks: list[dict]):
    """
    Index text chunks into ChromaDB.

    Args:
        textbook_id: UUID of the textbook.
        chapter_number: Chapter number.
        chunks: List of chunk dicts from chunker.py
    """
    collection = get_collection(textbook_id)

    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        chunk_id = f"ch{chapter_number}_p{chunk.get('page', 0)}_c{chunk['chunk_id']}"
        ids.append(chunk_id)
        documents.append(chunk['text'])
        metadatas.append({
            'chapter': chapter_number,
            'page': chunk.get('page', 0),
            'chunk_id': chunk['chunk_id'],
        })

    if ids:
        # ChromaDB upsert handles duplicates gracefully
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)


def query_collection(textbook_id: str, query: str, n_results: int = 5,
                     chapter_number: int = None) -> list[dict]:
    """
    Query the ChromaDB collection for relevant chunks.

    Returns:
        List of dicts: [{'text': '...', 'page': 5, 'chapter': 3, 'distance': 0.2}, ...]
    """
    collection = get_collection(textbook_id)

    where = None
    if chapter_number is not None:
        where = {"chapter": chapter_number}

    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count() or 1),
            where=where,
        )
    except Exception:
        return []

    output = []
    if results and results['documents']:
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i] if results['metadatas'] else {}
            dist = results['distances'][0][i] if results['distances'] else 1.0
            output.append({
                'text': doc,
                'page': meta.get('page', 0),
                'chapter': meta.get('chapter', 0),
                'distance': dist,
            })

    return output


def delete_collection(textbook_id: str):
    """Delete the ChromaDB collection for a textbook."""
    client = get_chroma_client()
    collection_name = f"textbook_{str(textbook_id).replace('-', '_')}"
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
