import asyncio
import os
import sys
import time
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
CONCURRENCY = 6
ROTATE_EVERY = 10


class CircuitRotator:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._count = 0

    async def maybe_rotate(self):
        async with self._lock:
            self._count += 1
            if self._count % ROTATE_EVERY == 0:
                await self._force_new_circuit()

    async def _force_new_circuit(self):
        try:
            from stem.control import Controller
            with Controller.from_port(port=9051) as controller:
                controller.authenticate()
                controller.signal("NEWNYM")
                await asyncio.sleep(1.5)
        except Exception:
            pass


class RateLimiter:
    def __init__(self, interval: float):
        self.interval = interval
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            wait = self.interval - (now - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


async def geocode_one(client: httpx.AsyncClient, limiter: RateLimiter, rotator: CircuitRotator, mun: tuple, stats: dict):
    municipio, estado, mun_id = mun
    await limiter.acquire()
    await rotator.maybe_rotate()

    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.get(
                NOMINATIM_URL,
                params={"q": f"{municipio}, {estado}, Mexico", "format": "json", "limit": 1, "countrycodes": "mx"},
            )
            if resp.status_code == 429:
                delay = 5 * (attempt + 1)
                await asyncio.sleep(delay)
                await rotator._force_new_circuit()
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
    stats.setdefault("failed_list", []).append((municipio, estado, mun_id))
    print(f"  [{stats['total']}/{stats['max']}] {municipio}, {estado} -> FAILED")


async def geocode_batch(client, limiter, rotator, muns, stats):
    tasks = [geocode_one(client, limiter, rotator, mun, stats) for mun in muns]
    await asyncio.gather(*tasks)


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
    print(f"Municipios sin coordenadas: {total} (Tor + NEWNYM, {CONCURRENCY} parallel)")

    limiter = RateLimiter(0.25)
    rotator = CircuitRotator()
    stats = {"updated": 0, "not_found": 0, "failed": 0, "total": 0, "max": total, "db_factory": session_factory, "failed_list": []}

    async with httpx.AsyncClient(
        proxy=TOR_PROXY,
        timeout=20,
        headers={"User-Agent": USER_AGENT},
        limits=httpx.Limits(max_connections=CONCURRENCY + 5, max_keepalive_connections=CONCURRENCY),
    ) as client:

        print(f"\n--- Pasada 1 de {len(muns)} ---")
        await geocode_batch(client, limiter, rotator, muns, stats)

        if stats["failed_list"]:
            failed_round1 = list(stats["failed_list"])
            stats["failed_list"] = []
            stats["failed"] = 0
            failed_count = len(failed_round1)
            print(f"\n--- Pasada 2: reintentando {failed_count} fallidos (espera 30s) ---")
            await asyncio.sleep(30)
            await geocode_batch(client, limiter, rotator, failed_round1, stats)

        if stats["failed_list"]:
            failed_round2 = list(stats["failed_list"])
            stats["failed_list"] = []
            stats["failed"] = 0
            failed_count = len(failed_round2)
            print(f"\n--- Pasada 3: reintentando {failed_count} fallidos (espera 60s) ---")
            await asyncio.sleep(60)
            await geocode_batch(client, limiter, rotator, failed_round2, stats)

    print(f"\nFinalizado:")
    print(f"  Actualizados: {stats['updated']}")
    print(f"  No encontrados en Nominatim: {stats['not_found']}")
    print(f"  Fallos definitivos: {len(stats['failed_list'])}")
    if stats["failed_list"]:
        print(f"\nMunicipios que fallaron:")
        for mun, est, _ in stats["failed_list"]:
            print(f"  - {mun}, {est}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(geocode_all())
