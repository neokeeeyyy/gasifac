import re
from datetime import date

import httpx

from api.config import settings

CRE_INDEX_URL = "https://www.gob.mx/cne/articulos/precios-maximos-de-gas-lp-399035"


async def find_latest_pdf_url() -> str:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(CRE_INDEX_URL)
        resp.raise_for_status()
    match = re.search(
        r'(https://www\.gob\.mx/cms/uploads/attachment/file/\d+/[^\s"]+\.pdf)',
        resp.text,
    )
    if not match:
        raise ValueError("No se encontró el PDF más reciente en la página de la CRE")
    return match.group(1)


async def download_pdf(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


async def upload_to_storage(pdf_bytes: bytes) -> str:
    today = date.today().isoformat()
    path = f"cre/{today}/precios.pdf"
    url = f"{settings.SUPABASE_URL}/storage/v1/object/gas-lp/{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            content=pdf_bytes,
            headers={
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/pdf",
                "x-upsert": "true",
            },
        )
        if resp.status_code not in (200, 201):
            raise ValueError(f"Error subiendo PDF a Storage: {resp.text}")
    return path


async def download_from_storage(path: str) -> bytes:
    url = f"{settings.SUPABASE_URL}/storage/v1/object/gas-lp/{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            url,
            headers={"Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"},
        )
        resp.raise_for_status()
        return resp.content


async def fetch_pdf(url: str | None = None) -> tuple[bytes, str]:
    target = url or await find_latest_pdf_url()
    pdf_bytes = await download_pdf(target)
    storage_path = await upload_to_storage(pdf_bytes)
    return pdf_bytes, storage_path
