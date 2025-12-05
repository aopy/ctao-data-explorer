# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VENV=/opt/venv

# System deps for psycopg2 build, trim after
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

# Isolated venv
RUN python -m venv $VENV
ENV PATH="$VENV/bin:$PATH"

# Non-root user
RUN addgroup --system app && adduser --system --ingroup app --home /app app
WORKDIR /app

# Install Python deps first
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip setuptools wheel \
 && pip install -r /tmp/requirements.txt

# Copy only what runtime needs
COPY --chown=app:app api/ /app/api/
COPY --chown=app:app alembic/ /app/alembic/
COPY --chown=app:app alembic.ini /app/
# serve the React build via FastAPI:
# COPY --chown=app:app js/build/ /app/js/build/

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s \
  CMD curl -fsS http://127.0.0.1:8000/health/ready || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]