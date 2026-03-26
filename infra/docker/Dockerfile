FROM python:3.11-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /tmp/build

COPY pyproject.toml README.md ./
COPY traveltom ./traveltom

RUN pip install --upgrade pip && pip install .

WORKDIR /workspace
