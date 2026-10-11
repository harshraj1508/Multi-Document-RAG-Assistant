"""Split raw document text into overlapping chunks.

Why chunk? Embeddings and LLMs work best on small pieces of text. Overlap keeps
sentences that straddle a boundary from losing their context.
"""


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += step
    return chunks
