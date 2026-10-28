"""Tablas de la base de datos."""

from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.database import Base


class UtcDateTime(TypeDecorator):
    """Guarda instantes como UTC naive y los devuelve con zona horaria UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect
    ) -> datetime | None:
        """Normaliza a UTC naive antes de escribir en la base."""
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(
        self, value: datetime | None, dialect
    ) -> datetime | None:
        """Devuelve el instante leído con zona horaria UTC."""
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class User(Base):
    """Cuenta de la clínica: cliente o veterinario."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('client', 'vet')", name="ck_users_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    pets: Mapped[list["Pet"]] = relationship(back_populates="owner")
    vet_appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="vet", foreign_keys="Appointment.vet_id"
    )


class Pet(Base):
    """Mascota registrada por un cliente."""

    __tablename__ = "pets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    species: Mapped[str] = mapped_column(String(20), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    owner: Mapped["User"] = relationship(back_populates="pets")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="pet")


class Appointment(Base):
    """Turno de 30 minutos entre una mascota y un veterinario."""

    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled', 'cancelled')", name="ck_appointments_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pet_id: Mapped[int] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    vet_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    start_at: Mapped[datetime] = mapped_column(UtcDateTime(), index=True, nullable=False)
    end_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")

    pet: Mapped["Pet"] = relationship(back_populates="appointments")
    vet: Mapped["User"] = relationship(
        back_populates="vet_appointments", foreign_keys=[vet_id]
    )
