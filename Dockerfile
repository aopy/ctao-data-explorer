# Dockerfile (backend)
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# copy the app
COPY . .

EXPOSE 8000
# (compose overrides this with your 'bash -lc "alembic ... && uvicorn ..."')
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
