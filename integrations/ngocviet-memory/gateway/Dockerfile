# Pinned base image — avoid `python:3.12` (floating) in production.
FROM python:3.12.7-slim-bookworm

RUN groupadd --gid 10001 gateway \
    && useradd --uid 10001 --gid gateway --shell /usr/sbin/nologin --no-create-home gateway

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

USER gateway

EXPOSE 8077

# Binds to 0.0.0.0 *inside* the container only; docker-compose publishes it
# to the host as 127.0.0.1:${GATEWAY_BIND_PORT} — see docker/docker-compose.yml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8077"]
