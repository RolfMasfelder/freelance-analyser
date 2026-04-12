FROM python:3.13-slim

WORKDIR /app

ENV PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd -g 1234 app && useradd -u 1234 -g 1234 -m app

COPY --chown=app:app . .

USER app

CMD ["tail", "-f", "/dev/null"]
