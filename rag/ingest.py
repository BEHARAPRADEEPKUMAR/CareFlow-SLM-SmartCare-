from pathlib import Path
import json
import re

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parent.parent

KNOWLEDGE_FILE = (
    BASE_DIR
    / "rag"
    / "knowledge_base"
    / "hospital_faq.txt"
)

VECTOR_DIR = BASE_DIR / "rag" / "vector_store"

INDEX_PATH = VECTOR_DIR / "hospital.index"
METADATA_PATH = VECTOR_DIR / "metadata.json"

MODEL_NAME = "all-MiniLM-L6-v2"


def load_hospital_chunks(text):
    """
    Split the CareFlow hospital document into meaningful
    section-based chunks.
    """

    text = text.strip()

    if not text:
        return []

    # Normalize line endings
    text = text.replace("\r\n", "\n")

    # Normalize excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Actual headings in hospital_faq.txt
    headings = [
        "ABOUT CAREFLOW HOSPITAL",
        "HOSPITAL SERVICES",
        "DOCTOR SPECIALIZATIONS",
        "CARDIOLOGY",
        "DERMATOLOGY",
        "ORTHOPEDICS",
        "GENERAL MEDICINE",
        "APPOINTMENT BOOKING",
        "APPOINTMENT RESCHEDULING",
        "APPOINTMENT CANCELLATION",
        "DOCTOR APPOINTMENTS",
        "EMERGENCY SAFETY",
        "MEDICAL ADVICE",
        "PATIENT COMMUNICATION",
        "APPOINTMENT REMINDERS",
        "PATIENT DATA",
        "LOCATION AND OPERATING HOURS",
        "HOSPITAL INFORMATION ACCURACY",
    ]

    # Build regex dynamically
    heading_pattern = (
        r"(?m)^\s*#{0,6}\s*("
        + "|".join(re.escape(h) for h in headings)
        + r")\s*$"
    )

    matches = list(
        re.finditer(
            heading_pattern,
            text,
            flags=re.MULTILINE,
        )
    )

    chunks = []

    # --------------------------------------------------
    # Text before first recognized heading
    # --------------------------------------------------

    if matches:

        intro = text[:matches[0].start()].strip()

        if intro:

            intro = re.sub(
                r"\s+",
                " ",
                intro,
            )

            chunks.append(
                {
                    "section": "INTRODUCTION",
                    "text": intro,
                }
            )

    # --------------------------------------------------
    # Extract each section
    # --------------------------------------------------

    for i, match in enumerate(matches):

        section_name = match.group(1).strip()

        start = match.start()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)

        section_text = text[start:end].strip()

        # Convert multiline text into clean text
        section_text = re.sub(
            r"\s+",
            " ",
            section_text,
        )

        if section_text:

            chunks.append(
                {
                    "section": section_name,
                    "text": section_text,
                }
            )

    return chunks


def main():

    print("Loading hospital knowledge...")

    # --------------------------------------------------
    # Check knowledge file
    # --------------------------------------------------

    if not KNOWLEDGE_FILE.exists():

        raise FileNotFoundError(
            f"\nKnowledge file not found:\n{KNOWLEDGE_FILE}"
        )

    print(f"Knowledge file: {KNOWLEDGE_FILE}")

    text = KNOWLEDGE_FILE.read_text(
        encoding="utf-8"
    )

    print(f"Characters loaded: {len(text)}")

    # --------------------------------------------------
    # Create chunks
    # --------------------------------------------------

    chunks = load_hospital_chunks(text)

    if not chunks:

        raise ValueError(
            "No hospital knowledge chunks were created."
        )

    print(
        f"\nCreated {len(chunks)} knowledge chunks."
    )

    # --------------------------------------------------
    # Display chunks
    # --------------------------------------------------

    for index, chunk in enumerate(chunks):

        print()
        print("=" * 70)
        print(f"CHUNK {index}")
        print(f"SECTION: {chunk['section']}")
        print("-" * 70)
        print(chunk["text"])

    # --------------------------------------------------
    # Load embedding model
    # --------------------------------------------------

    print()
    print("Loading embedding model...")

    model = SentenceTransformer(
        MODEL_NAME
    )

    chunk_texts = [
        chunk["text"]
        for chunk in chunks
    ]

    # --------------------------------------------------
    # Generate embeddings
    # --------------------------------------------------

    embeddings = model.encode(
        chunk_texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    embeddings = np.asarray(
        embeddings,
        dtype="float32",
    )

    print(
        f"Embedding shape: {embeddings.shape}"
    )

    # --------------------------------------------------
    # Create vector store directory
    # --------------------------------------------------

    VECTOR_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------
    # Create FAISS index
    # --------------------------------------------------

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(
        dimension
    )

    index.add(embeddings)

    faiss.write_index(
        index,
        str(INDEX_PATH),
    )

    # --------------------------------------------------
    # Save metadata
    # --------------------------------------------------

    metadata = []

    for chunk_index, chunk in enumerate(chunks):

        metadata.append(
            {
                "source": "hospital_faq.txt",
                "section": chunk["section"],
                "chunk_index": chunk_index,
                "text": chunk["text"],
            }
        )

    METADATA_PATH.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------
    # Completed
    # --------------------------------------------------

    print()
    print("=" * 70)
    print("RAG INGESTION COMPLETED SUCCESSFULLY")
    print("=" * 70)

    print(f"Chunks   : {len(chunks)}")
    print(f"Vectors  : {index.ntotal}")
    print(f"Index    : {INDEX_PATH}")
    print(f"Metadata : {METADATA_PATH}")


if __name__ == "__main__":
    main()