# Pinned to the minor version the app is developed and tested against.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so a code change does not reinstall the world.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

# Drop root. Nothing here needs it, and a container that does not run as root
# limits what a compromised dependency can reach.
RUN useradd --create-home --uid 10001 hangry && chown -R hangry:hangry /app
USER hangry

# Hosts inject the port. 8080 is the default on both Fly and Render.
ENV PORT=8080
EXPOSE 8080

CMD ["./entrypoint.sh"]
