import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from api.config import settings
from api.models import Municipio
from api.services.geocoder import geocode_municipio

BATCH_SIZE = 50
RATE_LIMIT = 1.1


async def geocode_all():
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0} if "pooler" in settings.DATABASE_URL else {},
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        result = await db.execute(
            select(Municipio).where(Municipio.latitud.is_(None))
        )
        muns = result.scalars().all()

    total = len(muns)
    if total == 0:
        print("Todos los municipios ya tienen coordenadas.")
        await engine.dispose()
        return

    print(f"Municipios sin coordenadas: {total}")
    updated = 0
    failed = 0

    for i, mun in enumerate(muns):
        geo = await geocode_municipio(mun.municipio, mun.estado)
        if geo:
            async with session_factory() as db:
                await db.execute(
                    update(Municipio)
                    .where(Municipio.id == mun.id)
                    .values(latitud=geo["lat"], longitud=geo["lng"])
                )
                await db.commit()
            updated += 1
            print(f"[{i+1}/{total}] {mun.municipio}, {mun.estado} -> {geo['lat']}, {geo['lng']}")
        else:
            failed += 1
            print(f"[{i+1}/{total}] {mun.municipio}, {mun.estado} -> NO ENCONTRADO")

        if (i + 1) % BATCH_SIZE == 0:
            print(f"--- Progreso: {updated} actualizados, {failed} fallidos de {i+1} ---")

        await asyncio.sleep(RATE_LIMIT)

    print(f"\nFinalizado: {updated} actualizados, {failed} fallidos de {total}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(geocode_all())
