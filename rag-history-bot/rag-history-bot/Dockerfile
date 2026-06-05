# ── Imagen base ligera ────────────────────────────────────────────────────────
FROM python:3.11-slim

# Evita archivos .pyc y bufferiza stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema (curl para healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY app/    ./app/
COPY scripts/ ./scripts/
COPY data/    ./data/

# El comando se sobreescribe en docker-compose.yml por servicio
CMD ["python", "app/bot.py"]
