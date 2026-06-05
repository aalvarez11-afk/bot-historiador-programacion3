"""
bot.py — Bot de Telegram con RAG que acepta PDFs
El usuario sube un PDF, el bot lo indexa y responde preguntas sobre él.
"""

import logging
import os
import tempfile

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from rag_pipeline import RAGPipeline

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

rag = RAGPipeline()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrae todo el texto de un PDF usando pypdf."""
    import pypdf
    text_parts = []
    with open(pdf_path, "rb") as f:
        reader = pypdf.PdfReader(f)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n\n".join(text_parts)


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🏛️ *Bienvenido al Bot de Historia y Cultura*\n\n"
        "Puedes hacer dos cosas:\n\n"
        "📄 *Subir un PDF* — Envíame cualquier documento PDF y lo procesaré. "
        "Luego podrás hacerme preguntas sobre su contenido.\n\n"
        "💬 *Hacer preguntas* — Escribe cualquier pregunta sobre los documentos "
        "que hayas subido o sobre historia y cultura en general.\n\n"
        "📚 También tengo conocimiento base sobre historia universal ya cargado.",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "ℹ️ *Comandos disponibles*\n\n"
        "• /start — Mensaje de bienvenida\n"
        "• /help — Este mensaje\n"
        "• /status — Estado del sistema\n"
        "• /clear — Borra los documentos indexados y empieza de cero\n\n"
        "Para usar el bot:\n"
        "1️⃣ Envía un archivo PDF\n"
        "2️⃣ Espera la confirmación de procesamiento\n"
        "3️⃣ Haz tus preguntas",
        parse_mode="Markdown",
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    status = rag.health_check()
    doc_count = rag.count_documents()
    lines = [f"{'✅' if v else '❌'} *{k}*" for k, v in status.items()]
    lines.append(f"\n📚 Documentos indexados: *{doc_count}* chunks")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rag.clear_collection()
    await update.message.reply_text(
        "🗑️ Colección borrada. Puedes subir nuevos PDFs."
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recibe un PDF, extrae el texto y lo indexa en Qdrant."""
    doc = update.message.document

    if not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text(
            "⚠️ Solo acepto archivos PDF. Por favor envía un archivo .pdf"
        )
        return

    await update.message.reply_text(
        f"📥 Recibí *{doc.file_name}*. Procesando...\n"
        "_Esto puede tardar unos segundos dependiendo del tamaño._",
        parse_mode="Markdown",
    )
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    # Descargar el PDF a un archivo temporal
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive(tmp_path)

        # Extraer texto
        text = extract_text_from_pdf(tmp_path)
        if not text.strip():
            await update.message.reply_text(
                "⚠️ No pude extraer texto de este PDF. "
                "Puede ser un PDF escaneado sin OCR."
            )
            return

        # Indexar en Qdrant
        chunks_indexed = rag.index_text(
            text=text,
            source=doc.file_name,
        )

        await update.message.reply_text(
            f"✅ *{doc.file_name}* procesado correctamente.\n"
            f"📊 Se indexaron *{chunks_indexed} fragmentos*.\n\n"
            "Ya puedes hacerme preguntas sobre este documento.",
            parse_mode="Markdown",
        )

    except Exception as exc:
        logger.error("Error procesando PDF: %s", exc)
        await update.message.reply_text(
            f"❌ Error al procesar el PDF: {exc}"
        )
    finally:
        os.unlink(tmp_path)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde preguntas usando el pipeline RAG."""
    question = update.message.text.strip()
    logger.info("Pregunta: %s", question)

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    try:
        answer = rag.query(question)
        await update.message.reply_text(answer, parse_mode="Markdown")
    except Exception as exc:
        logger.error("Error en RAG: %s", exc)
        await update.message.reply_text(
            "⚠️ Error al procesar tu pregunta. Intenta de nuevo."
        )


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    token = os.environ["TELEGRAM_TOKEN"]
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot iniciado. Esperando mensajes...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
