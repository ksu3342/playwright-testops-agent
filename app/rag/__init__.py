"""Local retrieval utilities for the TestOps agent."""

from app.rag.ingest import ingest_document
from app.rag.retriever import retrieve_testing_context

__all__ = ["ingest_document", "retrieve_testing_context"]
