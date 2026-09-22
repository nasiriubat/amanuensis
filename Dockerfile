# ---------- frontend build ----------
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- python runtime ----------
FROM python:3.12-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    FRONTEND_DIST=/app/frontend/dist \
    HF_HOME=/models \
    DOCLING_ARTIFACTS_PATH=/models/docling

# System tools: git for project history, pandoc for exports, curl to fetch tectonic.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git pandoc curl ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Tectonic: self-contained LaTeX engine, single binary.
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) t="x86_64-unknown-linux-musl" ;; \
      arm64) t="aarch64-unknown-linux-musl" ;; \
      *) echo "unsupported arch $arch" && exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.15.0/tectonic-0.15.0-${t}.tar.gz" \
      | tar -xz -C /usr/local/bin tectonic; \
    tectonic --version

WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/seed ./seed

# CPU-only PyTorch keeps the image far smaller than the default CUDA wheels.
RUN pip install --timeout 600 --retries 5 --extra-index-url https://download.pytorch.org/whl/cpu torch \
    && pip install --timeout 600 --retries 5 ".[extract]"

# Bake Docling's layout and table models into the image so first use is offline.
RUN mkdir -p /models/docling && docling-tools models download -o /models/docling || true

COPY --from=web /web/dist /app/frontend/dist

RUN useradd -m -u 1000 paper && mkdir -p /data && chown -R paper:paper /data /app /models
USER paper

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
