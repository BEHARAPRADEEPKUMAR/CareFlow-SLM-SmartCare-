
import logging
import sys
from pathlib import Path
from threading import Lock

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


logger = logging.getLogger(__name__)

# Project root contains the shared rag/ directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.retriever import RAGRetriever


_retriever = None
_retriever_lock = Lock()


def get_retriever():
    """Initialize the RAG retriever once per worker process."""
    global _retriever

    if _retriever is None:
        with _retriever_lock:
            if _retriever is None:
                _retriever = RAGRetriever()

    return _retriever


class RAGQueryView(APIView):
    """Retrieve relevant hospital knowledge passages."""

    def post(self, request):
        question = request.data.get("question")

        if question is None:
            question = request.data.get("query", "")

        if not isinstance(question, str):
            return Response(
                {"error": "question must be a string."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question = question.strip()

        if not question:
            return Response(
                {"error": "question is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(question) > 2000:
            return Response(
                {"error": "question must not exceed 2000 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            retriever = get_retriever()
            results = retriever.search(question, top_k=3)

            return Response(
                {
                    "question": question,
                    "results": results,
                    "result_count": len(results),
                },
                status=status.HTTP_200_OK,
            )

        except FileNotFoundError:
            logger.warning(
                "RAG index or metadata is missing. Build the index using rag/ingest.py."
            )
            return Response(
                {
                    "error": (
                        "The hospital knowledge index is not ready. "
                        "Build the RAG index before querying."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        except Exception:
            logger.exception("CareFlow RAG query failed.")
            return Response(
                {
                    "error": (
                        "RAG query failed. Check the backend logs "
                        "for details."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
