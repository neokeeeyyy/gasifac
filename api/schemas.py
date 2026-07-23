from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class MunicipioOut(BaseModel):
    id: int
    estado: str
    municipio: str
    region_numero: Optional[int] = None

    model_config = {"from_attributes": True}


class PrecioOut(BaseModel):
    id: int
    municipio_id: int
    municipio_nombre: Optional[str] = None
    estado: Optional[str] = None
    precio_kg: float
    precio_litro: float
    fecha_inicio: date
    fecha_fin: date

    model_config = {"from_attributes": True}


class PeriodoOut(BaseModel):
    fecha_inicio: date
    fecha_fin: date


class EstadisticasOut(BaseModel):
    precio_nacional_max: float
    precio_nacional_min: float
    precio_nacional_promedio: float
    total_municipios: int


class CheckoutRequest(BaseModel):
    email: EmailStr
    machine_id: str
    success_url: str = "https://neokey.dev/gasifac/comprar?success=true"
    cancel_url: str = "https://neokey.dev/gasifac/comprar?cancelled=true"


class CheckoutResponse(BaseModel):
    checkout_url: str


class SugerenciaRequest(BaseModel):
    name: str
    email: EmailStr
    category: str
    message: str


class UsuarioOut(BaseModel):
    email: str
    plan: str
    created_at: Optional[str] = None
    subscription_status: Optional[str] = None
    payments_count: int = 0


class HealthOut(BaseModel):
    status: str
    version: str
