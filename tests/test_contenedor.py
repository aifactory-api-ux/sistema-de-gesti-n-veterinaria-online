"""Pruebas de la configuración por variables de entorno de la imagen y del stack.

Verifican el contrato de la entrega containerizada: la imagen toma su
configuración (cadena de conexión, secreto de firma y puerto) del entorno, la
orquestación se la proporciona al servicio de la API, el repositorio no
contiene secretos de producción y la imagen de la API incluye únicamente lo
necesario para ejecutar la aplicación, sin el entorno de desarrollo.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from app.config import Settings

RAIZ = Path(__file__).resolve().parents[1]

DOCKERFILE = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
TEXTO_COMPOSE = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
COMPOSE = yaml.safe_load(TEXTO_COMPOSE)
ENV_EXAMPLE = (RAIZ / ".env.example").read_text(encoding="utf-8")
GITIGNORE = (RAIZ / ".gitignore").read_text(encoding="utf-8")
DOCKERIGNORE = (RAIZ / ".dockerignore").read_text(encoding="utf-8")
RUN_SH = (RAIZ / "run.sh").read_text(encoding="utf-8")

SERVICIO_API = COMPOSE["services"]["api"]
SERVICIO_TESTS = COMPOSE["services"]["tests"]
ENTORNO_API = SERVICIO_API["environment"]
PATRON_VARIABLE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)")
PATRON_ETAPA = re.compile(
    r"^FROM\s+(?P<imagen>\S+)(?:\s+AS\s+(?P<alias>\S+))?\s*$", re.IGNORECASE
)


def etapas_del_dockerfile() -> dict[str, str]:
    """Devuelve el cuerpo de cada etapa del `Dockerfile`, indexada por su alias."""
    etapas: dict[str, str] = {}
    alias_actual = ""
    cuerpo: list[str] = []

    for linea in DOCKERFILE.splitlines():
        coincidencia = PATRON_ETAPA.match(linea.strip())
        if coincidencia:
            if alias_actual:
                etapas[alias_actual] = "\n".join(cuerpo)
            alias_actual = coincidencia.group("alias") or coincidencia.group("imagen")
            cuerpo = []
        elif alias_actual:
            cuerpo.append(linea)

    if alias_actual:
        etapas[alias_actual] = "\n".join(cuerpo)

    return etapas


def claves_del_ejemplo_de_entorno() -> set[str]:
    """Devuelve las variables declaradas en `.env.example`."""
    claves = set()
    for linea in ENV_EXAMPLE.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        claves.add(linea.split("=", 1)[0].strip())
    return claves


def test_el_dockerfile_toma_el_puerto_del_entorno():
    assert 'CMD ["sh", "-c"' in DOCKERFILE
    assert "${PORT:-8000}" in DOCKERFILE
    assert "PORT=8000" in DOCKERFILE


def test_el_dockerfile_no_incrusta_configuracion_sensible():
    assert "JWT_SECRET" not in DOCKERFILE
    assert "postgresql" not in DOCKERFILE.lower()
    assert "password" not in DOCKERFILE.lower()


def test_compose_proporciona_la_configuracion_al_servicio_de_la_api():
    for variable in ("DATABASE_URL", "JWT_SECRET", "PORT"):
        assert variable in ENTORNO_API

    assert ENTORNO_API["PORT"] == "${PORT:-8000}"


def test_el_secreto_de_firma_llega_desde_el_entorno():
    assert ENTORNO_API["JWT_SECRET"].startswith("${JWT_SECRET:-")


def test_la_api_alcanza_a_postgres_por_el_nombre_del_servicio():
    cadena_de_conexion = ENTORNO_API["DATABASE_URL"]

    assert "@db:5432/" in cadena_de_conexion
    assert "localhost" not in cadena_de_conexion


def test_el_puerto_publicado_acompana_al_puerto_del_contenedor():
    assert SERVICIO_API["ports"] == ["${PORT:-8000}:${PORT:-8000}"]


def test_la_comprobacion_de_salud_consulta_el_puerto_del_contenedor():
    prueba = SERVICIO_API["healthcheck"]["test"]
    comando = " ".join(str(parte) for parte in prueba)

    assert "os.environ" in comando
    assert "PORT" in comando
    assert "/health" in comando


def test_la_imagen_se_construye_desde_la_raiz_del_repositorio():
    assert SERVICIO_API["build"]["context"] == "."
    assert (RAIZ / "Dockerfile").is_file()


def test_el_ejemplo_de_entorno_documenta_las_variables_de_la_orquestacion():
    declaradas = claves_del_ejemplo_de_entorno()
    usadas = set(PATRON_VARIABLE.findall(TEXTO_COMPOSE))

    assert usadas
    assert usadas <= declaradas


def test_el_archivo_de_configuracion_local_no_se_versiona_ni_se_imagen():
    assert ".env" in {linea.strip() for linea in GITIGNORE.splitlines()}
    assert ".env" in {linea.strip() for linea in DOCKERIGNORE.splitlines()}


def test_el_guion_crea_el_archivo_de_configuracion_en_el_primer_arranque():
    assert "cp .env.example .env" in RUN_SH


def test_la_aplicacion_expone_la_misma_variable_de_puerto_que_el_contenedor():
    assert "PORT" in Settings.model_fields
    assert Settings.model_fields["PORT"].default == 8000


def test_la_imagen_de_ejecucion_no_incluye_el_entorno_de_desarrollo():
    etapas = etapas_del_dockerfile()

    assert "runtime" in etapas
    assert "requirements-dev.txt" not in etapas["runtime"]
    assert "pytest" not in etapas["runtime"]
    assert "COPY tests/" not in etapas["runtime"]


def test_la_imagen_de_ejecucion_solo_copia_el_codigo_de_la_aplicacion():
    etapas = etapas_del_dockerfile()

    assert "COPY app/ ./app/" in etapas["runtime"]
    assert "COPY tests/" not in etapas["runtime"]
    assert "COPY pyproject.toml" not in etapas["runtime"]


def test_la_etapa_de_ejecucion_es_la_ultima_del_dockerfile():
    """La etapa final es la que construye `docker build` sin `--target`."""
    etapas = etapas_del_dockerfile()

    assert list(etapas)[-1] == "runtime"


def test_la_etapa_de_ejecucion_expone_el_puerto_de_la_aplicacion():
    etapas = etapas_del_dockerfile()

    assert "EXPOSE 8000" in etapas["runtime"]
    assert "ENV PORT=8000" in etapas["runtime"] or "PORT=8000" in etapas["runtime"]


def test_la_etapa_de_pruebas_incluye_las_dependencias_de_desarrollo():
    etapas = etapas_del_dockerfile()

    assert "test" in etapas
    assert "requirements-dev.txt" in etapas["test"]
    assert "pytest" in etapas["test"]
    assert "COPY tests/ ./tests/" in etapas["test"]


def test_el_servicio_de_la_api_construye_la_etapa_de_ejecucion():
    assert SERVICIO_API["build"]["context"] == "."
    assert SERVICIO_API["build"]["target"] == "runtime"


def test_el_servicio_de_pruebas_construye_la_etapa_de_pruebas():
    assert SERVICIO_TESTS["build"]["context"] == "."
    assert SERVICIO_TESTS["build"]["target"] == "test"


def test_las_imagenes_de_la_api_y_de_las_pruebas_son_distintas():
    assert SERVICIO_API["image"] != SERVICIO_TESTS["image"]
