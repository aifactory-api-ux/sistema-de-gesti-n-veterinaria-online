"""Modelos ORM de la clínica veterinaria."""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """Usuario de la plataforma, con rol `client` o `vet`."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('client', 'vet')", name="ck_users_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    pets: Mapped[list["Pet"]] = relationship(back_populates="owner")


class Pet(Base):
    """Mascota registrada a nombre de un cliente."""

    __tablename__ = "pets"
    __table_args__ = (
        CheckConstraint("species IN ('dog', 'cat', 'other')", name="ck_pets_species"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    species: Mapped[str] = mapped_column(String(16), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    owner: Mapped[User] = relationship(back_populates="pets")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="pet")


class Appointment(Base):
    """Turno de 30 minutos entre una mascota y un veterinario."""

    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("status IN ('scheduled', 'cancelled')", name="ck_appointments_status"),
        Index(
            "uq_appointments_vet_start_scheduled",
            "vet_id",
            "start_at",
            unique=True,
            postgresql_where=text("status = 'scheduled'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pet_id: Mapped[int] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    vet_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), server_default="scheduled", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    pet: Mapped[Pet] = relationship(back_populates="appointments")
    vet: Mapped[User] = relationship()
