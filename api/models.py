import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Municipio(Base):
    __tablename__ = "municipios"
    __table_args__ = (
        UniqueConstraint("estado", "municipio", name="uq_municipio_estado"),
        {"schema": "gas_lp"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    estado = Column(String(100), nullable=False)
    municipio = Column(String(150), nullable=False)
    region_numero = Column(Integer)
    latitud = Column(Numeric(10, 6))
    longitud = Column(Numeric(10, 6))
    created_at = Column(DateTime, default=datetime.utcnow)

    precios = relationship("Precio", back_populates="municipio", cascade="all, delete-orphan", foreign_keys="[Precio.municipio_id]")


class Precio(Base):
    __tablename__ = "precios"
    __table_args__ = (
        UniqueConstraint("municipio_id", "fecha_inicio", name="uq_precio_municipio_fecha"),
        {"schema": "gas_lp"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    municipio_id = Column(Integer, ForeignKey("gas_lp.municipios.id", ondelete="CASCADE"), nullable=False)
    precio_kg = Column(Numeric(6, 2), nullable=False)
    precio_litro = Column(Numeric(6, 2), nullable=False)
    fecha_inicio = Column(Date, nullable=False)
    fecha_fin = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    municipio = relationship("Municipio", back_populates="precios")


class Actualizacion(Base):
    __tablename__ = "actualizaciones"
    __table_args__ = {"schema": "gas_lp"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    fecha_descarga = Column(DateTime, default=datetime.utcnow, nullable=False)
    periodo_inicio = Column(Date, nullable=False)
    periodo_fin = Column(Date, nullable=False)
    registros_insertados = Column(Integer, default=0)
    exitoso = Column(Boolean, default=True)
    error_msg = Column(Text)


class ProcesamientoEstado(Base):
    __tablename__ = "procesamiento_estado"
    __table_args__ = {"schema": "gas_lp"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    pdf_url = Column(String(500), nullable=False)
    pdf_storage_path = Column(String(500))
    periodo_inicio = Column(String(20))
    periodo_fin = Column(String(20))
    total_paginas = Column(Integer, default=0)
    pagina_actual = Column(Integer, default=0)
    registros_insertados = Column(Integer, default=0)
    status = Column(String(50), default="pending")
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = {"schema": "gas_lp"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    stripe_customer_id = Column(String(255))
    plan = Column(String(50), default="free")
    widget_token = Column(String(255), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    suscripciones = relationship("Suscripcion", back_populates="usuario", cascade="all, delete-orphan", foreign_keys="[Suscripcion.usuario_id]")
    pagos = relationship("Pago", back_populates="usuario", cascade="all, delete-orphan", foreign_keys="[Pago.usuario_id]")


class Suscripcion(Base):
    __tablename__ = "suscripciones"
    __table_args__ = {"schema": "landing"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("gas_lp.usuarios.id", ondelete="CASCADE"), nullable=False)
    stripe_subscription_id = Column(String(255), unique=True)
    stripe_price_id = Column(String(255))
    status = Column(String(50), nullable=False)
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    cancel_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="suscripciones")


class Pago(Base):
    __tablename__ = "pagos"
    __table_args__ = {"schema": "landing"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("gas_lp.usuarios.id", ondelete="CASCADE"), nullable=False)
    stripe_payment_intent_id = Column(String(255), unique=True)
    stripe_invoice_id = Column(String(255))
    monto_cents = Column(Integer, nullable=False)
    moneda = Column(String(3), default="MXN")
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="pagos")
