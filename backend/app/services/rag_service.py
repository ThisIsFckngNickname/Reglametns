"""
RAG (Retrieval-Augmented Generation) service.

Handles:
1. Document chunking — splitting documents into manageable pieces
2. Embedding — converting chunks to vector embeddings via Ollama
3. Storage — storing/retrieving vectors in ChromaDB
4. Search — finding relevant chunks for a given query
"""

import hashlib
import logging
from typing import Any, Optional

import chromadb
import chromadb.errors
from chromadb.config import Settings as ChromaSettings

from app.config import settings

logger = logging.getLogger(__name__)


class RagService:
    """Service for RAG operations using ChromaDB and Ollama embeddings."""

    def __init__(self):
        self._client: Optional[chromadb.Client] = None
        self._collection_cache: dict[str, Any] = {}

    def _get_client(self) -> chromadb.Client:
        """Get or create the ChromaDB client."""
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=settings.chroma_persist_directory,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return self._client

    def _get_collection(self, company_id: int):
        """Get or create a collection for a specific company."""
        collection_name = f"company_{company_id}"
        cache_key = str(company_id)

        if cache_key in self._collection_cache:
            return self._collection_cache[cache_key]

        client = self._get_client()
        try:
            collection = client.get_collection(collection_name)
        except (ValueError, chromadb.errors.NotFoundError):
            collection = client.create_collection(
                name=collection_name,
                metadata={"company_id": company_id},
            )

        self._collection_cache[cache_key] = collection
        return collection

    async def _get_embedding(self, text: str) -> list[float]:
        """Get embedding vector from Ollama."""
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/embeddings",
                json={
                    "model": settings.ollama_embedding_model,
                    "prompt": text,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("embedding", [])

    def _chunk_text(self, text: str, title: str = "") -> list[dict[str, Any]]:
        """Split text into chunks of approximately chunk_size tokens."""
        if not text:
            return []

        chunks = []
        words = text.split()
        chunk_size_words = settings.rag_chunk_size // 2  # ~2 chars per token for Russian
        overlap_words = settings.rag_chunk_overlap // 2

        for i in range(0, len(words), chunk_size_words - overlap_words):
            chunk_words = words[i:i + chunk_size_words]
            if not chunk_words:
                continue
            chunk_text = " ".join(chunk_words)
            if len(chunk_text) < settings.rag_min_chunk_length:
                continue
            chunk_id = hashlib.md5(f"{title}:{i}".encode()).hexdigest()[:16]

            chunks.append({
                "id": chunk_id,
                "text": chunk_text,
                "title": title,
                "chunk_index": i // (chunk_size_words - overlap_words) if chunk_size_words > overlap_words else 0,
                "metadata": {
                    "source_title": title,
                    "chunk_index": i // (chunk_size_words - overlap_words) if chunk_size_words > overlap_words else 0,
                },
            })

        return chunks

    async def index_document(
        self,
        document_id: int,
        company_id: int,
        title: str,
        full_text: str,
    ) -> int:
        """Index a document: chunk, embed, store in ChromaDB.

        Returns:
            Number of chunks indexed.
        """
        chunks = self._chunk_text(full_text, title)
        if not chunks:
            logger.warning(f"No chunks generated for document {document_id}")
            return 0

        collection = self._get_collection(company_id)

        for chunk in chunks:
            try:
                embedding = await self._get_embedding(chunk["text"])
                if not embedding:
                    continue

                collection.add(
                    ids=[f"doc_{document_id}_{chunk['id']}"],
                    embeddings=[embedding],
                    documents=[chunk["text"]],
                    metadatas=[{
                        "document_id": document_id,
                        "title": title,
                        "chunk_index": chunk["chunk_index"],
                    }],
                )
            except Exception as e:
                logger.error(f"Failed to index chunk {chunk['id']}: {e}")
                continue

        logger.info(f"Indexed {len(chunks)} chunks for document {document_id}")
        return len(chunks)

    async def search(
        self,
        query: str,
        company_id: int,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search for relevant document chunks.

        Args:
            query: Search query text.
            company_id: Company ID.
            top_k: Number of results to return.

        Returns:
            List of dicts with 'text', 'title', 'document_id', 'chunk_index'.
        """
        try:
            collection = self._get_collection(company_id)
            query_embedding = await self._get_embedding(query)

            if not query_embedding:
                return []

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, settings.rag_max_chunks),
            )

            formatted = []
            if results and results.get("ids") and len(results["ids"]) > 0:
                for i, doc_id in enumerate(results["ids"][0]):
                    metadata = {}
                    if results.get("metadatas") and len(results["metadatas"]) > 0:
                        metadata = results["metadatas"][0][i] or {}

                    doc_text = ""
                    if results.get("documents") and len(results["documents"]) > 0:
                        doc_text = results["documents"][0][i] or ""

                    formatted.append({
                        "text": doc_text,
                        "title": metadata.get("title", "Неизвестный документ"),
                        "document_id": metadata.get("document_id", 0),
                        "chunk_index": metadata.get("chunk_index", 0),
                        "source": metadata.get("title", "Утверждённый документ"),
                    })

            return formatted

        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            return []

    async def delete_document_chunks(
        self,
        document_id: int,
        company_id: int,
    ) -> bool:
        """Delete all chunks for a specific document."""
        try:
            collection = self._get_collection(company_id)
            # ChromaDB doesn't support prefix deletion, so we get all and filter
            all_data = collection.get()
            if not all_data or not all_data.get("ids"):
                return True

            to_delete = [
                id for id in all_data["ids"]
                if id.startswith(f"doc_{document_id}_")
            ]

            if to_delete:
                collection.delete(ids=to_delete)
                logger.info(f"Deleted {len(to_delete)} chunks for document {document_id}")

            return True
        except Exception as e:
            logger.error(f"Failed to delete chunks for document {document_id}: {e}")
            return False

    async def get_document_chunks_count(
        self,
        document_id: int,
        company_id: int,
    ) -> int:
        """Count chunks stored in ChromaDB for a specific document.

        Args:
            document_id: ID of the document.
            company_id: ID of the company.

        Returns:
            Number of chunks found, or 0 if none or error.
        """
        try:
            collection = self._get_collection(company_id)
            all_data = collection.get()
            if not all_data or not all_data.get("ids"):
                return 0

            doc_chunks = [
                id for id in all_data["ids"]
                if id.startswith(f"doc_{document_id}_")
            ]
            return len(doc_chunks)
        except Exception as e:
            logger.warning(f"Failed to count chunks for document {document_id}: {e}")
            return 0


# Singleton
rag_service = RagService()
