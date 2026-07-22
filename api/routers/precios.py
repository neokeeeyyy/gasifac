from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import Municipio, Precio
from api.schemas import EstadisticasOut, MunicipioOut, PeriodoOut, PrecioOut

router = APIRouter(prefix="/api/v1", tags=["gasifac"])


@router.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@router.get("/periodo", response_model=PeriodoOut)
async def periodo(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(func.min(Precio.fecha_inicio), func.max(Precio.fecha_fin))
    )
    row = result.one()
    return PeriodoOut(fecha_inicio=row[0], fecha_fin=row[1])


@router.get("/estados")
async def estados(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Municipio.estado).distinct().order_by(Municipio.estado)
    )
    return [row[0] for row in result.all()]


@router.get("/municipios", response_model=list[MunicipioOut])
async def municipios(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    search = f"%{q}%"
    result = await db.execute(
        select(Municipio)
        .where(
            Municipio.municipio.ilike(search) | Municipio.estado.ilike(search)
        )
        .order_by(Municipio.estado, Municipio.municipio)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/precios", response_model=list[PrecioOut])
async def precios(
    estado: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    subq = (
        select(
            Precio.municipio_id,
            func.max(Precio.fecha_inicio).label("max_fecha"),
        )
        .group_by(Precio.municipio_id)
        .subquery()
    )
    query = (
        select(Precio, Municipio.municipio, Municipio.estado)
        .join(Municipio, Precio.municipio_id == Municipio.id)
        .join(
            subq,
            (Precio.municipio_id == subq.c.municipio_id)
            & (Precio.fecha_inicio == subq.c.max_fecha),
        )
    )
    if estado:
        query = query.where(Municipio.estado == estado)
    result = await db.execute(query.order_by(Municipio.estado, Municipio.municipio))
    return [
        PrecioOut(
            id=p.id,
            municipio_id=p.municipio_id,
            municipio_nombre=mun,
            estado=est,
            precio_kg=float(p.precio_kg),
            precio_litro=float(p.precio_litro),
            fecha_inicio=p.fecha_inicio,
            fecha_fin=p.fecha_fin,
        )
        for p, mun, est in result.all()
    ]


@router.get("/precios/{municipio_id}", response_model=PrecioOut)
async def precio_por_municipio(municipio_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Precio, Municipio.municipio, Municipio.estado)
        .join(Municipio, Precio.municipio_id == Municipio.id)
        .where(Precio.municipio_id == municipio_id)
        .order_by(Precio.fecha_inicio.desc())
        .limit(1)
    )
    row = result.first()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Municipio no encontrado")
    p, mun, est = row
    return PrecioOut(
        id=p.id,
        municipio_id=p.municipio_id,
        municipio_nombre=mun,
        estado=est,
        precio_kg=float(p.precio_kg),
        precio_litro=float(p.precio_litro),
        fecha_inicio=p.fecha_inicio,
        fecha_fin=p.fecha_fin,
    )


@router.get("/precios-cercanos")
async def precios_cercanos(
    lat: float = Query(...),
    lng: float = Query(...),
    limit: int = Query(15, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    delta = 1.5
    bounds = (lat - delta, lat + delta, lng - delta, lng + delta)
    subq = (
        select(
            Precio.municipio_id,
            func.max(Precio.fecha_inicio).label("max_fecha"),
        )
        .group_by(Precio.municipio_id)
        .subquery()
    )
    query = (
        select(Precio, Municipio.municipio, Municipio.estado)
        .join(Municipio, Precio.municipio_id == Municipio.id)
        .join(
            subq,
            (Precio.municipio_id == subq.c.municipio_id)
            & (Precio.fecha_inicio == subq.c.max_fecha),
        )
        .where(
            Municipio.latitud.isnot(None),
            Municipio.longitud.isnot(None),
            Municipio.latitud >= bounds[0],
            Municipio.latitud <= bounds[1],
            Municipio.longitud >= bounds[2],
            Municipio.longitud <= bounds[3],
        )
        .order_by(
            func.abs(Municipio.latitud - lat) + func.abs(Municipio.longitud - lng)
        )
        .limit(limit)
    )
    result = await db.execute(query)
    return [
        PrecioOut(
            id=p.id,
            municipio_id=p.municipio_id,
            municipio_nombre=mun,
            estado=est,
            precio_kg=float(p.precio_kg),
            precio_litro=float(p.precio_litro),
            fecha_inicio=p.fecha_inicio,
            fecha_fin=p.fecha_fin,
        )
        for p, mun, est in result.all()
    ]


@router.get("/estadisticas", response_model=EstadisticasOut)
async def estadisticas(db: AsyncSession = Depends(get_db)):
    subq = (
        select(
            Precio.municipio_id,
            func.max(Precio.fecha_inicio).label("max_fecha"),
        )
        .group_by(Precio.municipio_id)
        .subquery()
    )
    result = await db.execute(
        select(
            func.max(Precio.precio_kg),
            func.min(Precio.precio_kg),
            func.avg(Precio.precio_kg),
            func.count(Municipio.id),
        )
        .join(Municipio, Precio.municipio_id == Municipio.id)
        .join(
            subq,
            (Precio.municipio_id == subq.c.municipio_id)
            & (Precio.fecha_inicio == subq.c.max_fecha),
        )
    )
    row = result.one()
    return EstadisticasOut(
        precio_nacional_max=float(row[0] or 0),
        precio_nacional_min=float(row[1] or 0),
        precio_nacional_promedio=float(row[2] or 0),
        total_municipios=row[3] or 0,
    )
