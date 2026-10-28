"""Pruebas unitarias del andamiaje: configuración y esquema de la base de datos."""

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.config import Settings
from app.database import Base
from app.models import Appointment, Pet, User

VARIABLES_ENTORNO = (
    "DATABASE_URL",
    "JWT_SECRET",
    "JWT_ALGORITHM",
    "JWT_EXPIRE_MINUTES",
    "TEST_DATABASE_URL",
    "PORT",
)

DIALECTO = postgresql.dialect()


def indice_por_nombre(tabla, nombre):
    """Devuelve el índice de la tabla indicado por su nombre."""
    return next(indice for indice in tabla.indexes if indice.name == nombre)


def test_settings_declara_las_variables_de_entorno():
    for variable in VARIABLES_ENTORNO:
        assert variable in Settings.model_fields


def test_settings_usa_valores_por_defecto(monkeypatch):
    for variable in VARIABLES_ENTORNO:
        monkeypatch.delenv(variable, raising=False)

    settings = Settings(_env_file=None)

    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.JWT_EXPIRE_MINUTES == 60
    assert settings.PORT == 8000
    assert settings.DATABASE_URL.startswith("postgresql+psycopg://")
    assert settings.TEST_DATABASE_URL.startswith("postgresql+psycopg://")


def test_settings_prioriza_las_variables_del_entorno(monkeypatch):
    monkeypatch.setenv("JWT_ALGORITHM", "HS512")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "15")
    monkeypatch.setenv("PORT", "9001")

    settings = Settings(_env_file=None)

    assert settings.JWT_ALGORITHM == "HS512"
    assert settings.JWT_EXPIRE_MINUTES == 15
    assert settings.PORT == 9001


def test_settings_genera_un_secreto_efimero_sin_configuracion(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)

    settings = Settings(_env_file=None)

    assert len(settings.JWT_SECRET) >= 32


def test_modelos_declaran_las_tablas_del_esquema():
    assert User.__tablename__ == "users"
    assert Pet.__tablename__ == "pets"
    assert Appointment.__tablename__ == "appointments"
    assert set(Base.metadata.tables) == {"users", "pets", "appointments"}


def test_appointments_declara_el_indice_unico_parcial():
    indice = indice_por_nombre(
        Appointment.__table__, "uq_appointments_vet_start_scheduled"
    )

    ddl = str(CreateIndex(indice).compile(dialect=DIALECTO))

    assert indice.unique
    assert "(vet_id, start_at)" in ddl
    assert "WHERE" in ddl
    assert "scheduled" in ddl


def test_ddl_de_las_tablas_usa_restricciones_explicitas():
    ddl_appointments = str(CreateTable(Appointment.__table__).compile(dialect=DIALECTO))
    ddl_pets = str(CreateTable(Pet.__table__).compile(dialect=DIALECTO))
    ddl_users = str(CreateTable(User.__table__).compile(dialect=DIALECTO))

    assert "CREATE TABLE appointments" in ddl_appointments
    assert "start_at TIMESTAMP WITH TIME ZONE NOT NULL" in ddl_appointments
    assert "FOREIGN KEY(pet_id) REFERENCES pets (id) ON DELETE CASCADE" in ddl_appointments
    assert "FOREIGN KEY(vet_id) REFERENCES users (id) ON DELETE CASCADE" in ddl_appointments
    assert "FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE" in ddl_pets
    assert "birth_date DATE NOT NULL" in ddl_pets
    assert "password_hash VARCHAR(255) NOT NULL" in ddl_users
    assert "CHECK (role IN ('client', 'vet'))" in ddl_users
