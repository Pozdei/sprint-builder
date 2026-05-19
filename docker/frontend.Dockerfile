# syntax=docker/dockerfile:1.6
#
# Frontend Dockerfile.
#
# 1) builder — node:24 собирает фронт в /app/dist.
# 2) runtime — caddy:2, отдаёт статику из /srv. /api/* проксирует на backend.

# ------------- Stage 1: builder -------------
FROM node:24-slim AS builder

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./

# Фронт ходит к API через относительные пути (/api/...) — Caddy внутри своего
# конфига роутит на backend:8000. Поэтому VITE_API_URL пустой.
ENV VITE_API_URL=""
RUN npm run build


# ------------- Stage 2: runtime (Caddy) -------------
FROM caddy:2-alpine AS runtime

COPY --from=builder /app/dist /srv
COPY docker/Caddyfile /etc/caddy/Caddyfile

EXPOSE 80 443
