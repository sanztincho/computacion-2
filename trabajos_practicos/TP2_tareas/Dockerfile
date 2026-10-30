FROM python:3.11-slim

WORKDIR /app

# Primero las dependencias y después el código: así Docker reutiliza la capa
# de pip mientras no cambie requirements (clase 1-2, cache de capas).
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY app ./app
COPY sitios_prueba ./sitios_prueba
COPY mediciones ./mediciones
COPY tests ./tests
COPY pytest.ini ./

ENV PYTHONUNBUFFERED=1 \
    DIR_VOLCADOS=/app/volcados

EXPOSE 8000

# Forma "exec" (lista JSON), no "shell": así Python es el PID 1 y recibe el
# SIGTERM de `docker stop` directamente. Con la forma shell, el PID 1 sería
# /bin/sh, que no reenvía la señal, y Docker terminaría con un SIGKILL.
CMD ["python", "-m", "app"]
