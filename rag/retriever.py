"""
Hybrid retriever: combines ChromaDB similarity search with keyword search.
"""
from .embedder import query_collection


def retrieve(textbook_id: str, query: str, n_results: int = 5,
             chapter_number: int = None) -> list[dict]:
    """
    Retrieve relevant chunks using ChromaDB similarity search.

    Returns:
        Sorted list of relevant text chunks.
    """
    results = query_collection(
        textbook_id=textbook_id,
        query=query,
        n_results=n_results,
        chapter_number=chapter_number,
    )

    # Filter out low-relevance chunks (high cosine distance)
    filtered = [r for r in results if r['distance'] < 0.85]

    # Sort by relevance (distance ascending = more relevant)
    filtered.sort(key=lambda x: x['distance'])

    return filtered


def build_context(chunks: list[dict], max_words: int = 600) -> str:
    """
    Build a context string from retrieved chunks.
    Respects max_words limit.
    """
    context_parts = []
    total_words = 0

    for chunk in chunks:
        words = chunk['text'].split()
        if total_words + len(words) > max_words:
            remaining = max_words - total_words
            if remaining > 20:
                context_parts.append(' '.join(words[:remaining]))
            break
        context_parts.append(chunk['text'])
        total_words += len(words)

    return '\n\n'.join(context_parts)
