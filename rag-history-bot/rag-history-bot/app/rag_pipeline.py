"""
rag_pipeline.py — Pipeline RAG completo
Embedding → Qdrant → Ollama LLM
"""

import logging
import os
from typing import Optional

import requests
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

logger = logging.getLogger(__name__)

QDRANT_URL      = os.getenv("QDRANT_URL", "http://qdrant:6333")
OLLAMA_URL      = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL     = os.getenv("EMBED_MODEL", "nomic-embed-text")
LLM_MODEL       = os.getenv("LLM_MODEL", "llama3.2:3b")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "historia_cultura")
VECTOR_SIZE     = int(os.getenv("VECTOR_SIZE", "768"))
TOP_K           = int(os.getenv("TOP_K", "4"))
MAX_TOKENS      = int(os.getenv("MAX_TOKENS", "512"))
CHUNK_SIZE      = int(os.getenv("CHUNK_SIZE", "400"))
CHUNK_OVERLAP   = int(os.getenv("CHUNK_OVERLAP", "50"))

SYSTEM_PROMPT = (
    "Eres un asistente experto. "
    "Responde ÚNICAMENTE basándote en el contexto proporcionado. "
    "Si la información no está en el contexto, di que no tienes datos suficientes. "
    "Responde en español, de forma clara y educativa. "
    "Usa formato Markdown cuando sea útil."
)


class RAGPipeline:

    def __init__(self) -> None:
        self.qdrant = QdrantClient(url=QDRANT_URL)
        self._next_id = 0
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        existing = [c.name for c in self.qdrant.get_collections().collections]
        if COLLECTION_NAME not in existing:
            self.qdrant.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info("Colección '%s' creada.", COLLECTION_NAME)
        else:
            # Calcular el próximo ID basado en los documentos existentes
            count = self.qdrant.count(collection_name=COLLECTION_NAME).count
            self._next_id = count
            logger.info("Colección '%s' ya existe. Chunks existentes: %d", COLLECTION_NAME, count)

    def embed(self, text: str) -> list[float]:
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["embedding"]

    def chunk_text(self, text: str) -> list[str]:
        """Divide el texto en chunks con solapamiento."""
        words = text.split()
        chunks = []
        start = 0
        while start < len(words):
            end = start + CHUNK_SIZE
            chunks.append(" ".join(words[start:end]))
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    def index_text(self, text: str, source: str = "manual") -> int:
        """
        Divide el texto en chunks, los embeddea y los sube a Qdrant.
        Retorna el número de chunks indexados.
        """
        chunks = self.chunk_text(text)
        points = []
        for i, chunk in enumerate(chunks):
            vector = self.embed(chunk)
            points.append(
                PointStruct(
                    id=self._next_id + i,
                    vector=vector,
                    payload={"text": chunk, "source": source, "chunk_index": i},
                )
            )
        self.qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
        self._next_id += len(points)
        logger.info("Indexados %d chunks desde '%s'.", len(points), source)
        return len(points)

    def index_documents(self, chunks: list[dict]) -> None:
        """Compatibilidad con el script ingest.py."""
        points = []
        for chunk in chunks:
            vector = self.embed(chunk["text"])
            points.append(
                PointStruct(
                    id=chunk["id"],
                    vector=vector,
                    payload={"text": chunk["text"], **chunk.get("metadata", {})},
                )
            )
        self.qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
        logger.info("%d documentos indexados.", len(points))

    def retrieve(self, query: str) -> list[str]:
        query_vector = self.embed(query)
        results = self.qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=TOP_K,
            with_payload=True,
        )
        return [hit.payload["text"] for hit in results]

    def generate(self, question: str, context_chunks: list[str]) -> str:
        context = "\n\n---\n\n".join(context_chunks)
        user_prompt = (
            f"Contexto:\n{context}\n\n"
            f"Pregunta: {question}\n\n"
            "Responde en español basándote SOLO en el contexto anterior."
        )
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": LLM_MODEL,
                "stream": False,
                "options": {"num_predict": MAX_TOKENS, "temperature": 0.2},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
            },
            timeout=300,
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()

    def query(self, question: str) -> str:
        chunks = self.retrieve(question)
        if not chunks:
            return (
                "⚠️ No encontré información relevante en los documentos indexados. "
                "Sube un PDF primero o reformula tu pregunta."
            )
        return self.generate(question, chunks)

    def count_documents(self) -> int:
        return self.qdrant.count(collection_name=COLLECTION_NAME).count

    def clear_collection(self) -> None:
        self.qdrant.delete_collection(COLLECTION_NAME)
        self._ensure_collection()
        self._next_id = 0
        logger.info("Colección '%s' reiniciada.", COLLECTION_NAME)

    def health_check(self) -> dict[str, bool]:
        status = {"Qdrant": False, "Ollama": False}
        try:
            self.qdrant.get_collections()
            status["Qdrant"] = True
        except Exception:
            pass
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            status["Ollama"] = r.ok
        except Exception:
            pass
        return status
