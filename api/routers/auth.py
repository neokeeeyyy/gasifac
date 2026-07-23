from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import get_db
from api.models import Pago, Suscripcion, Usuario
from api.schemas import UsuarioOut

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.get("/config")
async def get_public_config():
    return {
        "supabase_url": settings.SUPABASE_URL,
        "supabase_anon_key": settings.SUPABASE_ANON_KEY,
    }


@router.get("/usuario")
async def get_usuario(email: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Usuario).where(Usuario.email == email))
    usuario = result.scalar_one_or_none()

    if not usuario:
        return {
            "email": email,
            "plan": None,
            "created_at": None,
            "subscription_status": None,
            "payments_count": 0,
        }

    sub_result = await db.execute(
        select(Suscripcion)
        .where(Suscripcion.usuario_id == usuario.id)
        .order_by(Suscripcion.created_at.desc())
        .limit(1)
    )
    sub = sub_result.scalar_one_or_none()

    payments_result = await db.execute(
        select(func.count(Pago.id)).where(Pago.usuario_id == usuario.id)
    )
    payments_count = payments_result.scalar() or 0

    return {
        "email": usuario.email,
        "plan": usuario.plan,
        "created_at": usuario.created_at.isoformat() if usuario.created_at else None,
        "subscription_status": sub.status if sub else None,
        "payments_count": payments_count,
    }
