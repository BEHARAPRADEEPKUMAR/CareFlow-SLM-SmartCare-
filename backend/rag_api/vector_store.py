import json
from pathlib import Path

import faiss
import numpy as np

from .chunker import chunk_text
from .embedding_service import EmbeddingService


BASE_DIR = Path(__file__).resolve().parent

KNOWLEDGE_FILE = (
    BASE_DIR
    / "knowledge_base"
    / "hospital_faq.txt"
)

INDEX_FILE = BASE_DIR / "careflow.index"
METADATA_FILE = BASE_DIR / "metadata.json"


class CareFlowVectorStore:

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.index = None
        self.metadata = []

    def build(self):

        text = KNOWLEDGE_FILE.read_text(
            encoding="utf-8"
        )

        chunks = chunk_text(text)

        if not chunks:
            raise ValueError(
                "No knowledge chunks found in hospital_faq.txt"
            )

        embeddings = (
            self.embedding_service
            .embed_documents(chunks)
        )

        embeddings = np.asarray(
            embeddings,
            dtype="float32"
        )

        # Normalize embeddings so Inner Product behaves
        # like cosine similarity.
        faiss.normalize_L2(embeddings)

        dimension = embeddings.shape[1]

        self.index = faiss.IndexFlatIP(
            dimension
        )

        self.index.add(embeddings)

        self.metadata = [
            {
                "id": index,
                "text": chunk,
                "source": "hospital_faq.txt",
            }
            for index, chunk in enumerate(chunks)
        ]

        faiss.write_index(
            self.index,
            str(INDEX_FILE)
        )

        METADATA_FILE.write_text(
            json.dumps(
                self.metadata,
                indent=2,
            ),
            encoding="utf-8",
        )

        return {
            "chunks": len(chunks),
            "dimension": dimension,
        }

    def load(self):

        if not INDEX_FILE.exists():
            raise FileNotFoundError(
                f"FAISS index not found: {INDEX_FILE}"
            )

        if not METADATA_FILE.exists():
            raise FileNotFoundError(
                f"Metadata file not found: {METADATA_FILE}"
            )

        self.index = faiss.read_index(
            str(INDEX_FILE)
        )

        self.metadata = json.loads(
            METADATA_FILE.read_text(
                encoding="utf-8"
            )
        )

    def search(self, query, top_k=1):

        if self.index is None:
            self.load()

        query_embedding = (
            self.embedding_service
            .embed_query(query)
        )

        query_embedding = np.asarray(
            [query_embedding],
            dtype="float32"
        )

        faiss.normalize_L2(query_embedding)

        scores, indices = self.index.search(
            query_embedding,
            top_k,
        )

        results = []

        for score, index in zip(
            scores[0],
            indices[0],
        ):

            if index == -1:
                continue

            item = self.metadata[index]

            results.append({
                "score": float(score),
                "text": item["text"],
                "source": item["source"],
            })

        return results