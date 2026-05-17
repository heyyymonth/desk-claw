FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EVAL_DB_PATH=/data/evals.db \
    AI_BACKEND_URL=http://ai-backend:9000

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app && mkdir -p /data

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

RUN chown -R app:app /app /data
USER app

EXPOSE 9300

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9300"]
