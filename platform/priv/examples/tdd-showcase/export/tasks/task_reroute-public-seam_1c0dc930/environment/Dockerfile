FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9
RUN mkdir -p /app/parcelbox /app/tests
COPY pyproject.toml /app/pyproject.toml
COPY FEATURE.md /app/FEATURE.md
COPY parcelbox_init.py /app/parcelbox/__init__.py
COPY routing.py /app/parcelbox/_routing.py
COPY persistence.py /app/parcelbox/_persistence.py
COPY test_existing.py /app/tests/test_existing.py
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
