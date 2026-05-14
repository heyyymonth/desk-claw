FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////app/data/deskclaw.db \
    LLM_MODE=ollama \
    OLLAMA_BASE_URL=http://ollama:11434 \
    OLLAMA_MODEL=gemma4:latest \
    WARM_OLLAMA_ON_STARTUP=true

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

RUN mkdir -p /app/data && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
