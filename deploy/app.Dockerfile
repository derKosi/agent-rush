# The control plane in a container.
#
# It talks to the host Docker daemon through the socket, because it spawns one sandbox
# container per task. That is a real privilege -- mounting the socket is equivalent to
# root on the host. Read the security note in the README before exposing this.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends docker.io ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir fastapi "uvicorn[standard]"

ENV PYTHONUNBUFFERED=1 \
    AR_RUNS_DIR=/app/work/runs

EXPOSE 8080
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
