# Étape 1 : compilation de l'interface React
FROM node:24-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

# Étape 2 : API FastAPI qui sert aussi l'interface compilée
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 COMMERCEOPS_DB=/data/catalog.db
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY demo ./demo
COPY --from=frontend /build/dist ./frontend/dist
# Utilisateur sans privilèges ; seule /data est accessible en écriture.
RUN useradd --system --uid 10001 commerceops && mkdir /data && chown commerceops /data
USER commerceops
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
