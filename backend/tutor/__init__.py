"""Tutor agent — answers user questions over a selected skill subtree.

Public API:
    BM25Retriever, ParagraphHit, build_retriever_for_node — retrieval primitives
    build_tutor_prompt — prompt assembly for the chat completion
    stream_tutor_response — emits the AI SDK UI Message Stream protocol
"""

from .retriever import BM25Retriever, ParagraphHit, build_retriever_for_node

__all__ = ["BM25Retriever", "ParagraphHit", "build_retriever_for_node"]
