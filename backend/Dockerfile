FROM python:3.12-slim

WORKDIR /app

# psycopg2-binary needs libpq at runtime; build-essential covers any source
# builds needed for other wheels on less common platforms.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Raw PSI storage default path (STORAGE_LOCAL_ROOT) resolves relative to
# /app, i.e. to /storage/raw when the compose volume is mounted at /storage.
RUN mkdir -p /storage/raw

EXPOSE 8000

# Run migrations then start the API. This is a dev-friendly default (product
# spec section 20: "backend container should run migrations automatically in
# development"); see README's Production Considerations for why you would
# NOT want auto-migrate-on-boot in a real production deployment.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
