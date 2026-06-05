"""
ingest.py — Carga y divide los documentos de texto en chunks,
luego los indexa en Qdrant a través del RAGPipeline.

Uso:
    python ingest.py                      # Carga todos los .txt de /data/documents
    python ingest.py --chunk-size 500     # Tamaño de chunk personalizado
"""

import argparse
import logging
import sys
from pathlib import Path

# Asegura que el módulo de la app sea importable
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
from rag_pipeline import RAGPipeline  # noqa: E402

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).parent.parent / "data" / "documents"


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """
    Divide el texto en fragmentos de `chunk_size` palabras con
    `overlap` palabras de solapamiento entre chunks consecutivos.
    El solapamiento preserva el contexto en los límites de los chunks.
    """
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap
    return chunks


def load_and_index(chunk_size: int = 400) -> None:
    """Lee todos los archivos .txt de DOCS_DIR e indexa sus chunks."""
    txt_files = list(DOCS_DIR.glob("*.txt"))
    if not txt_files:
        logger.warning("No se encontraron archivos .txt en %s", DOCS_DIR)
        return

    rag = RAGPipeline()
    global_id = 0

    for filepath in txt_files:
        logger.info("Procesando: %s", filepath.name)
        text = filepath.read_text(encoding="utf-8")
        chunks = chunk_text(text, chunk_size=chunk_size)

        docs = [
            {
                "id": global_id + i,
                "text": chunk,
                "metadata": {"source": filepath.name, "chunk_index": i},
            }
            for i, chunk in enumerate(chunks)
        ]
        rag.index_documents(docs)
        global_id += len(docs)
        logger.info("  → %d chunks indexados desde '%s'.", len(docs), filepath.name)

    logger.info("✅ Ingesta completada. Total: %d chunks.", global_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestión de documentos al vector store")
    parser.add_argument(
        "--chunk-size", type=int, default=400,
        help="Número de palabras por chunk (default: 400)"
    )
    args = parser.parse_args()
    load_and_index(chunk_size=args.chunk_size)
