FROM python:3.13-slim

# git is required at install time for the paprika-recipes git+https dependency.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

# HOME points at the Fly volume mount so paprika-recipes' recipe cache
# (~/.paprika-mcp/cache) and the OAuth SQLite store (~/.paprika-mcp/oauth.db,
# see http/config.py's default) both land on persistent storage without
# needing extra env vars wired through the app.
ENV HOME=/data \
    PORT=8000

EXPOSE 8000

CMD ["paprika-mcp", "serve"]
