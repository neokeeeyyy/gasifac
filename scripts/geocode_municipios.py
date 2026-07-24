import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from api.config import settings
from api.models import Municipio

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "GasifacBot/1.0 (https://neokey.dev)"
TOR_PROXY = "socks5://127.0.0.1:9050"
MAX_RETRIES = 4
CONCURRENCY = 10
REQUEST_DELAY = 0.15


class RateLimiter:
    def __init__(self, interval: float):
        self.interval = interval
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def acquire(self):
        async with self._lock:
            import time
            now = time.monotonic()
            wait = self.interval - (now - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


async def geocode_one(client: httpx.AsyncClient, limiter: RateLimiter, mun: tuple, stats: dict):
    municipio, estado, mun_id = mun
    async with limiter:
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.get(
                    NOMINATIM_URL,
                    params={"q": f"{municipio}, {estado}, Mexico", "format": "json", "limit": 1, "countrycodes": "mx"},
                )
                if resp.status_code == 429:
                    delay = 3 * (attempt + 1)
                    await asyncio.sleep(delay)
                    continue
                if resp.status_code >= 500:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                if resp.status_code != 200:
                    stats["not_found"] += 1
                    stats["total"] += 1
                    return
                data = resp.json()
                if not data:
                    stats["not_found"] += 1
                    stats["total"] += 1
                    return
                lat, lng = float(data[0]["lat"]), float(data[0]["lon"])
                async with stats["db_factory"]() as db:
                    await db.execute(
                        update(Municipio).where(Municipio.id == mun_id).values(latitud=lat, longitud=lng)
                    )
                    await db.commit()
                stats["updated"] += 1
                stats["total"] += 1
                if stats["total"] % 25 == 0:
                    print(f"  [{stats['total']}/{stats['max']}] {stats['updated']} ok, {stats['not_found']} not found, {stats['failed']} failed")
                return
            except Exception:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2 * (attempt + 1))

        stats["failed"] += 1
        stats["total"] += 1
        print(f"  [{stats['total']}/{stats['max']}] {municipio}, {estado} -> FAILED")


async def geocode_all():
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0} if "pooler" in settings.DATABASE_URL else {},
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        result = await db.execute(
            select(Municipio.id, Municipio.estado, Municipio.municipio).where(Municipio.latitud.is_(None))
        )
        rows = result.all()

    total = len(rows)
    if total == 0:
        print("Todos los municipios ya tienen coordenadas.")
        await engine.dispose()
        return

    muns = [(r[2], r[1], r[0]) for r in rows]
    print(f"Municipios sin coordenadas: {total} (via Tor, {CONCURRENCY} parallel)")

    limiter = RateLimiter(REQUEST_DELAY)
    stats = {"updated": 0, "not_found": 0, "failed": 0, "total": 0, "max": total, "db_factory": session_factory}

    async with httpx.AsyncClient(
        proxy=TOR_PROXY,
        timeout=20,
        headers={"User-Agent": USER_AGENT},
        limits=httpx.Limits(max_connections=CONCURRENCY + 5, max_keepalive_connections=CONCURRENCY),
    ) as client:
        tasks = [geocode_one(client, limiter, mun, stats) for mun in muns]
        await asyncio.gather(*tasks)

    print(f"\nFinalizado: {stats['updated']} actualizados, {stats['not_found']} no encontrados, {stats['failed']} fallos")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(geocode_all())
