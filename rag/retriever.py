from pathlib import Path
import json

import faiss
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parent.parent

VECTOR_DIR = BASE_DIR / "rag" / "vector_store"

INDEX_PATH = VECTOR_DIR / "hospital.index"
METADATA_PATH = VECTOR_DIR / "metadata.json"

MODEL_NAME = "all-MiniLM-L6-v2"


class RAGRetriever:

    def __init__(self):

        if not INDEX_PATH.exists():
            raise FileNotFoundError(
                "FAISS index not found. Run: python rag/ingest.py"
            )

        if not METADATA_PATH.exists():
            raise FileNotFoundError(
                "Metadata file not found. Run: python rag/ingest.py"
            )

        print("Loading RAG model...")

        self.model = SentenceTransformer(MODEL_NAME)

        self.index = faiss.read_index(
            str(INDEX_PATH)
        )

        self.metadata = json.loads(
            METADATA_PATH.read_text(
                encoding="utf-8"
            )
        )

    def search(self, query, top_k=1):

        query = str(query).strip()

        if not query:
            return []

        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        scores, indices = self.index.search(
            query_embedding,
            top_k,
        )

        results = []

        for score, index in zip(
            scores[0],
            indices[0],
        ):

            if index < 0 or index >= len(self.metadata):
                continue

            item = self.metadata[index]

            results.append({
                "score": float(score),
                "source": item.get("source", "unknown"),
                "section": item.get("section", ""),
                "chunk_index": item.get("chunk_index", index),
                "text": item.get("text", "")
            })

        return results


def main():

    retriever = RAGRetriever()

    query = input(
        "Enter your question: "
    ).strip()

    if not query:
        print(
            "Please enter a question."
        )
        return

    results = retriever.search(
        query,
        top_k=1,
    )

    print("\nTop RAG Results")
    print("=" * 60)

    for index, result in enumerate(
        results,
        start=1,
    ):

        print(
            f"\nResult {index}"
        )

        print(
            f"Score  : "
            f"{result['score']:.4f}"
        )

        print(
            f"Source : "
            f"{result['source']}"
        )

        print(
            f"Text   : "
            f"{result['text']}"
        )


if __name__ == "__main__":
    main()