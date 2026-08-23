# Pinned to the minor version the app is developed and tested against.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so a code change doesn't reinstall the world.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hosts inject the port; 8080 is Fly's default.
ENV PORT=8080
EXPOSE 8080

# Shell form on purpose, $PORT has to expand at runtime, not build time.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
