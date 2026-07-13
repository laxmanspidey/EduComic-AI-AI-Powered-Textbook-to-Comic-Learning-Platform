"""
Text chunking for RAG pipeline.
Splits long chapter text into overlapping chunks suitable for embedding.
"""
import re


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[dict]:
    """
    Split text into overlapping chunks.

    Args:
        text: Raw text to chunk.
        chunk_size: Target number of words per chunk.
        overlap: Number of overlapping words between adjacent chunks.

    Returns:
        List of dicts: [{'chunk_id': 0, 'text': '...', 'word_count': 500}, ...]
    """
    # Clean text
    text = re.sub(r'\s+', ' ', text).strip()
    words = text.split()

    if not words:
        return []

    chunks = []
    start = 0
    chunk_id = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunk_text_str = ' '.join(chunk_words)

        chunks.append({
            'chunk_id': chunk_id,
            'text': chunk_text_str,
            'word_count': len(chunk_words),
        })

        chunk_id += 1
        start += chunk_size - overlap

        if start >= len(words):
            break

    return chunks


def chunk_pages(pages: list[dict], page_start: int, page_end: int) -> list[dict]:
    """
    Chunk text from specific pages, preserving page reference.
    """
    all_chunks = []
    for page in pages:
        if page_start <= page['page'] <= page_end and page['text']:
            page_chunks = chunk_text(page['text'], chunk_size=400, overlap=80)
            for chunk in page_chunks:
                chunk['page'] = page['page']
                all_chunks.append(chunk)
    return all_chunks
