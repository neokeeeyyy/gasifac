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
MAX_RETRIES = 3
CONCURRENCY = 15

PROXY_SOURCES = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=mx",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
]


async def fetch_proxies() -> list[str]:
    proxies = set()
    async with httpx.AsyncClient(timeout=10) as client:
        for url in PROXY_SOURCES:
            try:
                resp = await client.get(url, headers={"User-Agent": USER_AGENT})
                if resp.status_code == 200:
                    for line in resp.text.strip().splitlines():
                        line = line.strip()
                        if line and ":" in line and not line.startswith("#"):
                            proxies.add(f"http://{line}")
            except Exception:
                continue
    return list(proxies)


async def test_proxy(client: httpx.AsyncClient, proxy: str, semaphore: asyncio.Semaphore) -> str | None:
    async with semaphore:
        try:
            resp = await client.get(
                NOMINATIM_URL,
                params={"q": "Mexico City, Mexico", "format": "json", "limit": 1},
                proxy=proxy,
                timeout=8,
            )
            if resp.status_code == 200:
                return proxy
        except Exception:
            pass
    return None


async def geocode_one(client: httpx.AsyncClient, proxy: str, mun: tuple, limiter: asyncio.Semaphore, stats: dict):
    municipio, estado, mun_id = mun
    async with limiter:
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.get(
                    NOMINATIM_URL,
                    params={"q": f"{municipio}, {estado}, Mexico", "format": "json", "limit": 1, "countrycodes": "mx"},
                    proxy=proxy,
                    timeout=12,
                )
                if resp.status_code == 429:
                    delay = 2 * (attempt + 1)
                    await asyncio.sleep(delay)
                    continue
                if resp.status_code >= 500:
                    await asyncio.sleep(1.5 * (attempt + 1))
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
                if stats["total"] % 20 == 0:
                    print(f"  [{stats['total']}/{stats['max']}] {stats['updated']} ok, {stats['not_found']} no encontrados, {stats['failed']} fallos")
                else:
                    print(f"  [{stats['total']}/{stats['max']}] {municipio}, {estado} -> {lat}, {lng}")
                return
            except Exception:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1.5 * (attempt + 1))
                continue

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
    print(f"Municipios sin coordenadas: {total}")
    print("Buscando proxies...")
    all_proxies = await fetch_proxies()
    print(f"Proxies encontrados: {len(all_proxies)}")

    if not all_proxies:
        print("No se encontraron proxies. Usando conexion directa...")
        all_proxies = [None]

    test_sem = asyncio.Semaphore(30)
    async with httpx.AsyncClient(timeout=8, headers={"User-Agent": USER_AGENT}) as client:
        tasks = [test_proxy(client, p, test_sem) for p in all_proxies]
        results = await asyncio.gather(*tasks)
    working = [p for p in results if p]
    print(f"Proxies funcionales: {len(working)} de {len(all_proxies)}")

    if not working:
        print("Ningun proxy funciona, usando conexion directa")
        working = [None]

    proxy_idx = 0
    limiter = asyncio.Semaphore(CONCURRENCY)
    stats = {"updated": 0, "not_found": 0, "failed": 0, "retries": 0, "total": 0, "max": total, "db_factory": session_factory}

    async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
        tasks = []
        for mun in muns:
            proxy = working[proxy_idx % len(working)]
            proxy_idx += 1
            tasks.append(geocode_one(client, proxy, mun, limiter, stats))
        await asyncio.gather(*tasks)

    print(f"\nFinalizado: {stats['updated']} actualizados, {stats['not_found']} no encontrados, {stats['failed']} fallos")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(geocode_all())
