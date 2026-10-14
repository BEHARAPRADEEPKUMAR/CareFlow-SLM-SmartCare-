import re


def chunk_text(text, chunk_size=500, overlap=100):
    """
    Split healthcare FAQ content into question-answer chunks.

    For FAQ documents, each Q:/A: pair becomes one independent chunk.
    This allows RAG to retrieve only the relevant FAQ instead of
    returning the entire FAQ document.
    """

    text = text.strip()

    if not text:
        return []

    # Detect FAQ blocks beginning with Q:
    faq_blocks = re.split(r"\n\s*(?=Q\s*:)", text, flags=re.IGNORECASE)

    chunks = []

    for block in faq_blocks:
        block = block.strip()

        if not block:
            continue

        # Normalize excessive whitespace
        block = re.sub(r"\s+", " ", block)

        chunks.append(block)

    # Fallback for non-FAQ documents
    if len(chunks) <= 1:
        words = text.split()

        if len(words) <= chunk_size:
            return [text]

        chunks = []

        start = 0

        while start < len(words):
            end = start + chunk_size

            chunk = " ".join(words[start:end])

            if chunk.strip():
                chunks.append(chunk)

            if end >= len(words):
                break

            start = end - overlap

    return chunks