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

USER_AGENT = "GasifacBot/1.0 (https://neokey.dev)"
TOR_PROXY = "socks5://127.0.0.1:9050"
MAX_RETRIES = 3
CONCURRENCY = 10
ROTATE_EVERY = 12

PROVIDERS = [
    {"name": "nominatim", "url": "https://nominatim.openstreetmap.org/search", "rate": 1.1},
    {"name": "photon", "url": "https://photon.komoot.io/search", "rate": 0.5},
]


class CircuitRotator:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._count = 0

    async def maybe_rotate(self):
        async with self._lock:
            self._count += 1
            if self._count % ROTATE_EVERY == 0:
                try:
                    from stem.control import Controller
                    with Controller.from_port(port=9051) as controller:
                        controller.authenticate()
                        controller.signal("NEWNYM")
                        await asyncio.sleep(1.5)
                except Exception:
                    pass


class ProviderRateLimiter:
    def __init__(self):
        self._locks = {p["name"]: asyncio.Lock() for p in PROVIDERS}
        self._last = {p["name"]: 0.0 for p in PROVIDERS}

    async def acquire(self, provider_name: str, interval: float):
        async with self._locks[provider_name]:
            now = time.monotonic()
            wait = interval - (now - self._last[provider_name])
            if wait > 0:
                await asyncio.sleep(wait)
            self._last[provider_name] = time.monotonic()


async def try_provider(client: httpx.AsyncClient, provider: dict, municipio: str, estado: str) -> dict | None:
    params = {"q": f"{municipio}, {estado}, Mexico", "format": "json", "limit": 1, "countrycodes": "mx"}
    try:
        resp = await client.get(provider["url"], params=params, timeout=12)
        if resp.status_code == 429:
            raise Exception("Rate limited")
        if resp.status_code >= 500:
            raise Exception(f"Server {resp.status_code}")
        if resp.status_code != 200:
            return None
        data = resp.json()
        features = data.get("features", data) if isinstance(data, dict) else data
        if not features:
            return None
        f = features[0]
        if provider["name"] == "photon":
            coords = f.get("geometry", {}).get("coordinates", [])
            if len(coords) >= 2:
                return {"lat": float(coords[1]), "lng": float(coords[0])}
        else:
            if "lat" in f and "lon" in f:
                return {"lat": float(f["lat"]), "lng": float(f["lon"])}
        return None
    except Exception:
        raise


async def geocode_one(client: httpx.AsyncClient, limiter: ProviderRateLimiter, rotator: CircuitRotator, mun: tuple, stats: dict):
    municipio, estado, mun_id = mun
    await rotator.maybe_rotate()

    for attempt in range(MAX_RETRIES):
        for provider in PROVIDERS:
            await limiter.acquire(provider["name"], provider["rate"])
            try:
                result = await try_provider(client, provider, municipio, estado)
                if result:
                    async with stats["db_factory"]() as db:
                        await db.execute(
                            update(Municipio).where(Municipio.id == mun_id).values(latitud=result["lat"], longitud=result["lng"])
                        )
                        await db.commit()
                    stats["updated"] += 1
                    stats["total"] += 1
                    if stats["total"] % 25 == 0:
                        print(f"  [{stats['total']}/{stats['max']}] {stats['updated']} ok, {stats['not_found']} not found, {stats['failed']} failed")
                    return
            except Exception:
                continue

        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(3 * (attempt + 1))
            await rotator.maybe_rotate()

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
    print(f"Municipios sin coordenadas: {total}")
    print(f"Providers: {', '.join(p['name'] for p in PROVIDERS)} (Tor + NEWNYM)")

    limiter = ProviderRateLimiter()
    rotator = CircuitRotator()
    stats = {"updated": 0, "not_found": 0, "failed": 0, "total": 0, "max": total, "db_factory": session_factory, "failed_list": []}

    async with httpx.AsyncClient(
        proxy=TOR_PROXY,
        timeout=20,
        headers={"User-Agent": USER_AGENT},
        limits=httpx.Limits(max_connections=CONCURRENCY + 5, max_keepalive_connections=CONCURRENCY),
    ) as client:

        print(f"\n--- Pasada 1: {len(muns)} municipios ---")
        await geocode_batch(client, limiter, rotator, muns, stats)

        if stats["failed_list"]:
            failed = list(stats["failed_list"])
            stats["failed_list"] = []
            stats["failed"] = 0
            print(f"\n--- Pasada 2: reintentando {len(failed)} fallidos (espera 20s) ---")
            await asyncio.sleep(20)
            await geocode_batch(client, limiter, rotator, failed, stats)

        if stats["failed_list"]:
            failed = list(stats["failed_list"])
            stats["failed_list"] = []
            stats["failed"] = 0
            print(f"\n--- Pasada 3: reintentando {len(failed)} fallidos (espera 45s) ---")
            await asyncio.sleep(45)
            await geocode_batch(client, limiter, rotator, failed, stats)

    print(f"\nFinalizado:")
    print(f"  Actualizados: {stats['updated']}")
    print(f"  No encontrados: {stats['not_found']}")
    print(f"  Fallos definitivos: {len(stats['failed_list'])}")
    if stats["failed_list"]:
        print(f"\nMunicipios que fallaron:")
        for mun, est, _ in stats["failed_list"]:
            print(f"  - {mun}, {est}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(geocode_all())
