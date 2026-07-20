import math
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Municipio, Precio, ProcesamientoEstado
from api.services.pdf_fetcher import download_from_storage, fetch_pdf
from api.services.pdf_parser import parse_pdf

BATCH_SIZE = 15


async def run_update(db: AsyncSession, pdf_url: str | None = None) -> dict:
    result = await db.execute(
        select(ProcesamientoEstado)
        .where(ProcesamientoEstado.status.in_(["pending", "processing"]))
        .order_by(ProcesamientoEstado.id.desc())
        .limit(1)
    )
    estado = result.scalar_one_or_none()

    if estado and estado.status in ("pending", "processing"):
        return await _continue_batch(db, estado)

    return await _start_new(db, pdf_url)


async def _start_new(db: AsyncSession, pdf_url: str | None) -> dict:
    pdf_bytes, storage_path = await fetch_pdf(pdf_url)

    parse_result = parse_pdf(pdf_bytes, page_start=0, page_end=BATCH_SIZE)

    estado = ProcesamientoEstado(
        pdf_url=storage_path,
        pdf_storage_path=storage_path,
        total_paginas=parse_result.total_pages,
        pagina_actual=min(BATCH_SIZE, parse_result.total_pages),
        status="processing",
    )
    db.add(estado)
    await db.flush()

    inserted = await _insert_rows(db, parse_result.rows)
    estado.registros_insertados = inserted

    if estado.pagina_actual >= estado.total_paginas:
        estado.status = "done"
        from datetime import datetime
        estado.completed_at = datetime.utcnow()
        await db.commit()
        return {
            "status": "ok",
            "registros_insertados": estado.registros_insertados,
            "total_paginas": estado.total_paginas,
        }

    await db.commit()
    return {
        "status": "in_progress",
        "pagina_actual": estado.pagina_actual,
        "total_paginas": estado.total_paginas,
        "registros_hasta_ahora": estado.registros_insertados,
    }


async def _continue_batch(db: AsyncSession, estado: ProcesamientoEstado) -> dict:
    pdf_bytes = await download_from_storage(estado.pdf_storage_path)

    page_start = estado.pagina_actual
    page_end = min(page_start + BATCH_SIZE, estado.total_paginas)

    parse_result = parse_pdf(pdf_bytes, page_start=page_start, page_end=page_end)

    inserted = await _insert_rows(db, parse_result.rows)
    estado.registros_insertados += inserted
    estado.pagina_actual = page_end

    if estado.pagina_actual >= estado.total_paginas:
        estado.status = "done"
        from datetime import datetime
        estado.completed_at = datetime.utcnow()
        await db.commit()
        return {
            "status": "ok",
            "registros_insertados": estado.registros_insertados,
            "total_paginas": estado.total_paginas,
        }

    await db.commit()
    return {
        "status": "in_progress",
        "pagina_actual": estado.pagina_actual,
        "total_paginas": estado.total_paginas,
        "registros_hasta_ahora": estado.registros_insertados,
    }


async def _insert_rows(db: AsyncSession, rows) -> int:
    if not rows:
        return 0

    existing = await db.execute(
        select(Municipio.estado, Municipio.municipio, Municipio.id)
    )
    mun_map = {(r[0], r[1]): r[2] for r in existing.all()}

    new_muns = []
    for row in rows:
        if (row.estado, row.municipio) not in mun_map:
            new_muns.append(
                {
                    "estado": row.estado,
                    "municipio": row.municipio,
                    "region_numero": row.region_numero,
                }
            )

    if new_muns:
        stmt = (
            pg_insert(Municipio)
            .values(new_muns)
            .on_conflict_do_nothing()
        )
        await db.execute(stmt)

        existing = await db.execute(
            select(Municipio.estado, Municipio.municipio, Municipio.id)
        )
        mun_map = {(r[0], r[1]): r[2] for r in existing.all()}

    today = date.today()
    precio_rows = []
    for row in rows:
        mun_id = mun_map.get((row.estado, row.municipio))
        if mun_id:
            precio_rows.append(
                {
                    "municipio_id": mun_id,
                    "precio_kg": row.precio_kg,
                    "precio_litro": row.precio_litro,
                    "fecha_inicio": today,
                    "fecha_fin": today,
                }
            )

    if precio_rows:
        stmt = pg_insert(Precio).values(precio_rows).on_conflict_do_nothing()
        await db.execute(stmt)

    return len(precio_rows)
