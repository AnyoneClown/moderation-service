# ─────────────────────────────────────────────────────────────
# Dockerfile — Multi-stage optimised build for the FastAPI app
# Stage 1 (builder): installs Python deps into a virtual-env
# Stage 2 (runtime): copies only the venv + app code (smaller image)
# ─────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build-time system dependencies (for asyncpg, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Create a virtual environment so we can copy it cleanly later
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ──
FROM python:3.11-slim AS runtime

WORKDIR /app

# Only the minimal runtime libraries (libpq for asyncpg)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# Copy the pre-built virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source code
COPY . .

# Expose the default Uvicorn port
EXPOSE 8000

# Run with Uvicorn (production-ready ASGI server)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
