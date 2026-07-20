# FastAPI backend for the Coffee Recipe Lookup Agent (deploy target: Render)
FROM python:3.12-slim

WORKDIR /app

# Install deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + prebuilt data artifacts (recipes.json / guide.json baked into the image)
COPY agent/ ./agent/
COPY recipes.json guide.json ./

# Render provides $PORT; default to 8000 for local `docker run`
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn agent.api:app --host 0.0.0.0 --port ${PORT}"]
