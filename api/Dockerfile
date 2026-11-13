# syntax=docker/dockerfile:1.7
# The Last Safe Home — API image (SPEC §12). Build from the repo root:
#   python -m pipeline.lsh.pack --sites manpura,koyra,demo      # -> data/deploy/processed (size-checked)
#   docker build -f api/Dockerfile -t last-safe-home-api .
# or let the build download a packed data archive (hosts that build from git, where data/ is not committed):
#   docker build -f api/Dockerfile --build-arg DATA_URL=https://.../lsh-data.tar.gz -t last-safe-home-api .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/app/data SITES=manpura,koyra,demo PORT=8000
WORKDIR /app

COPY api/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates libexpat1 && rm -rf /var/lib/apt/lists/*
# libexpat1: the rasterio wheel's bundled GDAL links against the system libexpat, which python:3.12-slim lacks

COPY config/ config/
COPY pipeline/__init__.py pipeline/__init__.py
COPY pipeline/lsh/ pipeline/lsh/
COPY api/__init__.py api/__init__.py
COPY api/app/ api/app/

# data: the packed copy from the build context (.dockerignore lets only data/deploy through), or DATA_URL
# (a bind mount reads the build context without storing it in an image layer; needs BuildKit)
ARG DATA_URL=""
RUN --mount=type=bind,target=/tmp/ctx \
    mkdir -p /app/data/processed \
    && if [ -n "$DATA_URL" ]; then \
         echo "downloading data from $DATA_URL" && curl -fsSL "$DATA_URL" | tar -xz -C /app/data; \
       elif [ -d /tmp/ctx/data/deploy/processed ]; then \
         cp -r /tmp/ctx/data/deploy/processed/. /app/data/processed/; \
       else echo "no data baked in: mount it at /app/data/processed"; fi \
    && size=$(du -sb /app/data | cut -f1) && echo "data: $size bytes" \
    && if [ "$size" -gt 1500000000 ]; then echo "data over 1.5 GB (SPEC §12)"; exit 1; fi

RUN useradd --create-home --uid 10001 app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD curl -fs "http://localhost:${PORT}/api/v1/health" || exit 1
# hosts like Render set $PORT
CMD ["sh", "-c", "exec uvicorn api.app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
