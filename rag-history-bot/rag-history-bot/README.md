# 🏛️ HistoriaBot — Chatbot RAG de Historia y Cultura Mundial

Bot de Telegram completamente local que utiliza arquitectura **RAG (Retrieval-Augmented Generation)** para responder preguntas sobre Historia y Cultura Mundial, sin depender de APIs externas de pago.

---

## 📐 Arquitectura

```
Usuario (Telegram)
        │
        ▼
  [Bot de Telegram]  ←── python-telegram-bot (polling)
        │
        ▼
  [RAG Pipeline]
   ┌────┴────────────────────────────┐
   │                                 │
   ▼                                 ▼
[Embedding]                    [Generación]
Ollama → nomic-embed-text      Ollama → llama3.2:3b
        │                            ▲
        ▼                            │
[Vector Search]              [Contexto recuperado]
Qdrant (cosine similarity)  ─────────┘
```

### Flujo de una pregunta (RAG)

1. **Embed** — La pregunta del usuario se convierte en un vector de 768 dimensiones usando `nomic-embed-text`.
2. **Retrieve** — Qdrant busca los 4 fragmentos de texto más similares en la colección vectorial usando similitud coseno.
3. **Generate** — Los fragmentos se envían como contexto a `llama3.2:3b` junto con la pregunta. El LLM genera una respuesta basada **únicamente** en ese contexto.
4. **Respond** — La respuesta se envía al usuario en Telegram.

---

## 🧰 Stack tecnológico

| Componente | Tecnología | Rol |
|------------|-----------|-----|
| Bot | `python-telegram-bot 21` | Interfaz con Telegram via polling |
| LLM | `Ollama + llama3.2:3b` | Generación de respuestas en lenguaje natural |
| Embeddings | `Ollama + nomic-embed-text` | Conversión de texto a vectores |
| Vector Store | `Qdrant` | Almacenamiento y búsqueda vectorial |
| Contenedores | `Docker + Docker Compose` | Orquestación de servicios |

---

## 📁 Estructura del proyecto

```
rag-history-bot/
├── app/
│   ├── bot.py            # Entry point: handlers de Telegram
│   └── rag_pipeline.py   # Lógica RAG: embed → retrieve → generate
├── scripts/
│   └── ingest.py         # Carga documentos .txt → chunks → Qdrant
├── data/
│   └── documents/
│       └── historia_universal.txt   # Base de conocimiento
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Instalación y ejecución

### Prerrequisitos

- [Docker Desktop](https://docs.docker.com/get-docker/) (incluye Docker Compose)
- Una cuenta de Telegram y un token de bot (ver abajo)

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/rag-history-bot.git
cd rag-history-bot
```

### 2. Crear tu bot en Telegram

1. Abre Telegram y busca **@BotFather**
2. Escribe `/newbot` y sigue las instrucciones
3. Copia el token que te da (formato: `123456789:ABC-DEF...`)

### 3. Configurar variables de entorno

```bash
cp .env.example .env
# Edita .env y pega tu token:
# TELEGRAM_TOKEN=123456789:ABC-DEF...
```

### 4. Descargar los modelos de IA

> Este paso descarga ~2 GB de modelos. Solo es necesario la primera vez.

```bash
# Inicia solo Ollama
docker compose up ollama -d

# Descarga el modelo de embedding (768d, ~274 MB)
docker exec ollama ollama pull nomic-embed-text

# Descarga el LLM (llama3.2 3B, ~2 GB)
docker exec ollama ollama pull llama3.2:3b
```

### 5. Levantar todos los servicios

```bash
docker compose up -d
```

Esto levanta en orden:
1. **Qdrant** — vector store en `localhost:6333`
2. **Ollama** — servidor de modelos en `localhost:11434`
3. **ingest** — carga los documentos históricos (corre una vez y termina)
4. **bot** — el bot de Telegram (corre permanentemente)

### 6. Verificar que todo funciona

```bash
# Ver logs del bot
docker compose logs -f bot

# Ver logs de la ingesta
docker compose logs ingest
```

Abre Telegram, busca tu bot y escribe `/start`. ✅

---

## 💬 Comandos del bot

| Comando | Descripción |
|---------|-------------|
| `/start` | Mensaje de bienvenida |
| `/help` | Instrucciones de uso |
| `/status` | Verifica conectividad con Qdrant y Ollama |
| `[cualquier texto]` | Pregunta respondida con RAG |

### Ejemplos de preguntas

- ¿Cuándo cayó el Imperio Romano?
- ¿Qué fue la Revolución Francesa?
- Háblame sobre la cultura Maya
- ¿Quién fue Alejandro Magno?
- ¿Cómo funcionaba el feudalismo?

---

## ⚙️ Configuración avanzada

Todas las variables de entorno del servicio `bot` y `ingest` en `docker-compose.yml`:

| Variable | Default | Descripción |
|----------|---------|-------------|
| `TELEGRAM_TOKEN` | — | **Requerido**. Token de @BotFather |
| `QDRANT_URL` | `http://qdrant:6333` | URL del vector store |
| `OLLAMA_URL` | `http://ollama:11434` | URL del servidor Ollama |
| `EMBED_MODEL` | `nomic-embed-text` | Modelo de embedding |
| `LLM_MODEL` | `llama3.2:3b` | Modelo generativo |
| `COLLECTION_NAME` | `historia_cultura` | Nombre de la colección Qdrant |
| `VECTOR_SIZE` | `768` | Dimensión del vector (debe coincidir con el modelo) |
| `TOP_K` | `4` | Número de fragmentos a recuperar |
| `MAX_TOKENS` | `512` | Máximo de tokens en la respuesta |

---

## 📚 Agregar más conocimiento

1. Crea un archivo `.txt` en `data/documents/`
2. Re-ejecuta la ingesta:

```bash
docker compose run --rm ingest
```

Los nuevos documentos se agregan a la colección existente (upsert).

---

## 🔍 Por qué polling y no webhook + ngrok

El bot usa **long-polling**: Telegram es quien envía actualizaciones al bot periódicamente, sin necesidad de una URL pública. Esto simplifica el desarrollo local y no requiere ngrok. Si deseas usar webhooks (por ejemplo, en producción), necesitarías ngrok o un servidor con IP pública para que Telegram pueda hacer POST a tu endpoint.

---

## 🛑 Detener el proyecto

```bash
docker compose down        # Detiene contenedores (preserva volúmenes)
docker compose down -v     # Detiene y borra volúmenes (reinicia todo)
```

---

## 👥 Equipo

- Estudiante 1 — @usuario_github
- Estudiante 2 — @usuario_github

Proyecto final — Curso de Programación — 2025
