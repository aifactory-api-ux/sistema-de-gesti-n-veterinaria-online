# Imagen de la API de la clínica veterinaria.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/app

# Las dependencias se instalan aparte para aprovechar la caché de capas.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Solo el paquete de la aplicación entra en la imagen.
COPY app/ ./app/

# La API no necesita escribir en el sistema de archivos: corre sin privilegios.
RUN useradd --create-home --uid 10001 clinic
USER clinic

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
