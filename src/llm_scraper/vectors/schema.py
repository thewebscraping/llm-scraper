"""Pydantic schemas for vector store operations."""
from typing import Any, Dict, List, Literal, Set

from pydantic import BaseModel, Field


class Document(BaseModel):
    """Schema for a document to be inserted into the vector store."""

    id: str = Field(..., description="Unique identifier for the document.")
    text: str = Field(..., description="The text content of the document.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Associated metadata.")


class UpsertRequest(BaseModel):
    """Request model for upserting documents."""

    documents: List[Document]


class SearchRequest(BaseModel):
    """Request model for performing a search."""

    query: str
    limit: int = 5
    fields: Set[str] = Field(
        default={"text", "metadata"},
        description="Fields to return in search results.",
    )


class VectorStoreRequest(BaseModel):
    """
    A discriminated union for all possible vector store operations.
    The 'operation' field determines which model to use.
    """

    operation: Literal["upsert", "search"]
    params: UpsertRequest | SearchRequest
