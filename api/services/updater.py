from datetime import date, datetime

from sqlalchemy import select
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
        periodo_inicio=parse_result.periodo_inicio,
        periodo_fin=parse_result.periodo_fin,
        total_paginas=parse_result.total_pages,
        pagina_actual=min(BATCH_SIZE, parse_result.total_pages),
        status="processing",
    )
    db.add(estado)
    await db.flush()

    inserted = await _insert_rows(db, parse_result.rows, parse_result.periodo_inicio, parse_result.periodo_fin)
    estado.registros_insertados = inserted

    if estado.pagina_actual >= estado.total_paginas:
        estado.status = "done"
        estado.completed_at = datetime.utcnow()
        await db.commit()
        return {
            "status": "ok",
            "registros_insertados": estado.registros_insertados,
            "total_paginas": estado.total_paginas,
            "periodo": f"{parse_result.periodo_inicio} al {parse_result.periodo_fin}",
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

    inserted = await _insert_rows(db, parse_result.rows, estado.periodo_inicio, estado.periodo_fin)
    estado.registros_insertados += inserted
    estado.pagina_actual = page_end

    if estado.pagina_actual >= estado.total_paginas:
        estado.status = "done"
        estado.completed_at = datetime.utcnow()
        await db.commit()
        return {
            "status": "ok",
            "registros_insertados": estado.registros_insertados,
            "total_paginas": estado.total_paginas,
            "periodo": f"{estado.periodo_inicio} al {estado.periodo_fin}",
        }

    await db.commit()
    return {
        "status": "in_progress",
        "pagina_actual": estado.pagina_actual,
        "total_paginas": estado.total_paginas,
        "registros_hasta_ahora": estado.registros_insertados,
    }


async def _insert_rows(db: AsyncSession, rows, periodo_inicio: str, periodo_fin: str) -> int:
    if not rows:
        return 0

    from datetime import date as _date
    fi = _date.fromisoformat(periodo_inicio) if periodo_inicio else None
    ff = _date.fromisoformat(periodo_fin) if periodo_fin else None
    if not fi or not ff:
        raise ValueError(f"Periodo inválido: inicio={periodo_inicio}, fin={periodo_fin}")

    existing = await db.execute(
        select(Municipio.estado, Municipio.municipio, Municipio.id)
    )
    mun_map = {(r[0], r[1]): r[2] for r in existing.all()}

    new_muns = []
    for row in rows:
        key = (row.estado, row.municipio)
        if key not in mun_map:
            new_muns.append(
                {
                    "estado": row.estado,
                    "municipio": row.municipio,
                    "region_numero": row.region_numero,
                }
            )

    if new_muns:
        stmt = pg_insert(Municipio).values(new_muns).on_conflict_do_nothing()
        await db.execute(stmt)

        existing = await db.execute(
            select(Municipio.estado, Municipio.municipio, Municipio.id)
        )
        mun_map = {(r[0], r[1]): r[2] for r in existing.all()}

    precio_rows = []
    seen = set()
    for row in rows:
        key = (row.estado, row.municipio)
        if key in seen:
            continue
        seen.add(key)
        mun_id = mun_map.get(key)
        if mun_id:
            precio_rows.append(
                {
                    "municipio_id": mun_id,
                    "precio_kg": row.precio_kg,
                    "precio_litro": row.precio_litro,
                    "fecha_inicio": fi,
                    "fecha_fin": ff,
                }
            )

    if precio_rows:
        stmt = pg_insert(Precio).values(precio_rows).on_conflict_do_nothing()
        await db.execute(stmt)

    return len(precio_rows)
