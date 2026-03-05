# ===================================================
# Stage 1: Frontend Build
# ===================================================
FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --production=false
COPY frontend/ ./
RUN npm run build
# 產出：/app/frontend/dist/

# ===================================================
# Stage 2: Python Backend
# ===================================================
FROM python:3.11-slim AS production

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends 
    curl 
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY api/ ./api/
COPY pipeline/ ./pipeline/
COPY db/ ./db/
COPY interfaces.py config.py cli.py ./

# Copy frontend build output
COPY --from=frontend-build /app/frontend/dist ./static/

# Copy startup script
COPY scripts/start.sh ./scripts/
RUN chmod +x scripts/start.sh

# HealthCheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 
    CMD curl -f http://localhost:8000/api/markets || exit 1

EXPOSE 8000

CMD ["./scripts/start.sh"]
