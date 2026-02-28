FROM python:3.12-slim

WORKDIR /app

# System deps for asyncpg, shapely
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libgeos-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python", "-m", "sentinel"]
