FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9
RUN mkdir -p /app/theater_sales /app/data /app/adr /app/tests
COPY CONTEXT.md /app/CONTEXT.md
COPY WORK_ITEM.md /app/WORK_ITEM.md
COPY 0001-money-at-public-boundaries.md /app/adr/0001-money-at-public-boundaries.md
COPY seat_prices.json /app/data/seat_prices.json
COPY __init__.py /app/theater_sales/__init__.py
COPY availability.py /app/theater_sales/availability.py
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
