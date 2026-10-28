# Imagen de la API de la clínica veterinaria.
#
# La construcción tiene tres etapas:
#   builder -> resuelve e instala en un entorno virtual las dependencias de
#              ejecución declaradas en `requirements.txt`.
#   test    -> añade sobre `builder` las dependencias de desarrollo y la suite
#              de pruebas, para ejecutar los tests dentro del contenedor.
#   runtime -> imagen final de la API: solo el código de la aplicación y las
#              dependencias de ejecución, sin herramientas de desarrollo.
#
# La etapa `runtime` es la última del archivo, de modo que `docker build .`
# produce la imagen de la API y las herramientas de desarrollo (pytest) nunca
# llegan a ella. El servicio `tests` de la orquestación construye la etapa
# `test` para ejecutar la suite dentro del contenedor.
#
# Toda la configuración (cadena de conexión, secreto de firma y puerto) llega
# por variables de entorno: la imagen no incrusta secretos ni dependencias de
# un entorno concreto.

# --- Etapa de construcción ---------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

COPY requirements.txt ./

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# --- Etapa de pruebas --------------------------------------------------------
# Derivada de `builder`: comparte el entorno virtual ya instalado y le suma las
# dependencias de desarrollo y la suite. Solo la usa el servicio `tests`.
FROM builder AS test

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY requirements-dev.txt ./
COPY app/ ./app/
COPY tests/ ./tests/
COPY pyproject.toml ./

RUN /opt/venv/bin/pip install -r requirements-dev.txt

RUN useradd --create-home --shell /usr/sbin/nologin vetclinic \
    && chown -R vetclinic:vetclinic /app
USER vetclinic

CMD ["pytest", "-q"]

# --- Etapa de ejecución ------------------------------------------------------
# Imagen de la API: contiene únicamente lo necesario para ejecutar la
# aplicación. No incluye la suite de pruebas ni las dependencias de desarrollo.
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

COPY app/ ./app/

RUN useradd --create-home --shell /usr/sbin/nologin vetclinic \
    && chown -R vetclinic:vetclinic /app
USER vetclinic

EXPOSE 8000

# El puerto de escucha se toma de la variable de entorno `PORT`, que la
# orquestación puede fijar en tiempo de ejecución. `8000` es el valor por
# defecto para el arranque sin configuración externa.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
