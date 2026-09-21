FROM python:3.13-slim

# git is required at install time for the paprika-recipes git+https dependency.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

# OAuth state and the recipe cache both live in Redis (Render Key Value in
# production, via REDIS_URL -- see http/config.py and paprika_cache.py), not
# on local disk, since Render's free web-service filesystem is ephemeral.
ENV PORT=8000

EXPOSE 8000

CMD ["paprika-mcp", "serve"]
