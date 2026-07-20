from datetime import date, datetime

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
        inserted_municipios = 0
        inserted_precios = 0

        for row in rows:
            result = await db.execute(
                select(Municipio).where(
                    Municipio.estado == row.estado,
                    Municipio.municipio == row.municipio,
                )
            )
            municipio = result.scalar_one_or_none()
            if not municipio:
                municipio = Municipio(
                    estado=row.estado,
                    municipio=row.municipio,
                    region_numero=row.region_numero,
                )
                db.add(municipio)
                await db.flush()
                inserted_municipios += 1

            stmt = (
                pg_insert(Precio)
                .values(
                    municipio_id=municipio.id,
                    precio_kg=row.precio_kg,
                    precio_litro=row.precio_litro,
                    fecha_inicio=today,
                    fecha_fin=today,
                )
                .on_conflict_do_nothing()
            )
            await db.execute(stmt)
            inserted_precios += 1

        actualizacion = Actualizacion(
            periodo_inicio=today,
            periodo_fin=today,
            registros_insertados=inserted_precios,
            exitoso=True,
        )
        db.add(actualizacion)
        await db.commit()

        return {
            "status": "ok",
            "municipios_insertados": inserted_municipios,
            "precios_insertados": inserted_precios,
        }

    except Exception as e:
        actualizacion = Actualizacion(
            periodo_inicio=date.today(),
            periodo_fin=date.today(),
            exitoso=False,
            error_msg=str(e),
        )
        db.add(actualizacion)
        await db.commit()
        return {"status": "error", "detail": str(e)}
