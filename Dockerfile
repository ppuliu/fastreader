FROM node:22-alpine AS fe
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
# claude-agent-sdk ships a self-contained bundled CLI binary — no Node needed.
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY scripts ./scripts
COPY data/builtin ./data/builtin
COPY transcripts ./transcripts
COPY --from=fe /fe/dist ./static
ENV BUILTIN_DIR=/app/data/builtin STATIC_DIR=/app/static DATA_DIR=/data \
    TRANSCRIPTS_DIR=/app/transcripts
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
