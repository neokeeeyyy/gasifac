import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from api.config import settings
from api.models import Municipio
from api.services.geocoder import geocode_municipio

CONCURRENCY = 20
MAX_RETRIES = 3
RETRY_DELAY = 2
PROGRESS_INTERVAL = 50


async def geocode_one(db_factory, mun, semaphore, stats):
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                geo = await geocode_municipio(mun.municipio, mun.estado)
                if geo:
                    async with db_factory() as db:
                        await db.execute(
                            update(Municipio)
                            .where(Municipio.id == mun.id)
                            .values(latitud=geo["lat"], longitud=geo["lng"])
                        )
                        await db.commit()
                    stats["updated"] += 1
                    print(f"  [{stats['total']}] {mun.municipio}, {mun.estado} -> {geo['lat']}, {geo['lng']}")
                else:
                    stats["not_found"] += 1
                    print(f"  [{stats['total']}] {mun.municipio}, {mun.estado} -> NO ENCONTRADO")
                stats["total"] += 1
                if stats["total"] % PROGRESS_INTERVAL == 0:
                    print(f"--- Progreso: {stats['updated']} ok, {stats['not_found']} no encontrados, {stats['retries']} reintentos, {stats['total']}/{stats['max']} ---")
                return
            except Exception as e:
                stats["retries"] += 1
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY * (attempt + 1)
                    print(f"  [{stats['total']+1}] {mun.municipio}, {mun.estado} -> ERROR ({type(e).__name__}), retry {attempt+2}/{MAX_RETRIES} en {delay}s")
                    await asyncio.sleep(delay)
                else:
                    stats["failed"] += 1
                    stats["total"] += 1
                    print(f"  [{stats['total']}] {mun.municipio}, {mun.estado} -> FALLO DEFINITIVO ({type(e).__name__}: {str(e)[:80]})")


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

    print(f"Municipios sin coordenadas: {total} (concurrency={CONCURRENCY})")

    semaphore = asyncio.Semaphore(CONCURRENCY)
    stats = {"updated": 0, "not_found": 0, "failed": 0, "retries": 0, "total": 0, "max": total}

    tasks = [geocode_one(session_factory, mun, semaphore, stats) for mun in muns]
    await asyncio.gather(*tasks)

    print(f"\nFinalizado: {stats['updated']} actualizados, {stats['not_found']} no encontrados, {stats['failed']} fallos, {stats['retries']} reintentos de {total}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(geocode_all())
