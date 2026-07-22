FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libncursesw6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY config.json .

ENV PYTHONUNBUFFERED=1
ENV TERM=xterm-256color

ENTRYPOINT ["python3", "src/main.py"]
CMD ["--config", "config.json", "--dump-dir", "/app/dumps"]
