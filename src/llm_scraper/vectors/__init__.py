"""
This __init__.py file makes the vector_store directory a Python package
and exposes the main `VectorStoreEngine` and schema classes for easy access.
"""
from .abc import EmbeddingAdapter, VectorDBAdapter
from .engine import VectorStoreEngine
from .schema import Document, SearchRequest, UpsertRequest, VectorStoreRequest

__all__ = [
    "VectorStoreEngine",
    "EmbeddingAdapter",
    "VectorDBAdapter",
    "Document",
    "SearchRequest",
    "UpsertRequest",
    "VectorStoreRequest",
]
