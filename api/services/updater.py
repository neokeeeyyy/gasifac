from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Actualizacion, Municipio, Precio
from api.services.pdf_fetcher import fetch_pdf
from api.services.pdf_parser import parse_pdf


async def run_update(db: AsyncSession, pdf_url: str | None = None) -> dict:
    try:
        pdf_bytes = await fetch_pdf(pdf_url)
        rows = parse_pdf(pdf_bytes)
        if not rows:
            raise ValueError("No se extrajeron filas del PDF")

        today = date.today()

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
                .returning(Municipio.id, Municipio.estado, Municipio.municipio)
            )
            result = await db.execute(stmt)
            for r in result.all():
                mun_map[(r[1], r[2])] = r[0]

            remaining = await db.execute(
                select(Municipio.estado, Municipio.municipio, Municipio.id)
            )
            mun_map = {(r[0], r[1]): r[2] for r in remaining.all()}

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
            stmt = (
                pg_insert(Precio)
                .values(precio_rows)
                .on_conflict_do_nothing()
            )
            await db.execute(stmt)

        actualizacion = Actualizacion(
            periodo_inicio=today,
            periodo_fin=today,
            registros_insertados=len(precio_rows),
            exitoso=True,
        )
        db.add(actualizacion)
        await db.commit()

        return {
            "status": "ok",
            "municipios_insertados": len(new_muns),
            "precios_insertados": len(precio_rows),
        }

    except Exception as e:
        await db.rollback()
        return {"status": "error", "detail": str(e)}
