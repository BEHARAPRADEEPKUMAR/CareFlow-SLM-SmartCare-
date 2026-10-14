
from django.urls import path

from .views import RAGQueryView

app_name = "rag_api"

urlpatterns = [
    path(
        "query/",
        RAGQueryView.as_view(),
        name="rag-query",
    ),
]
