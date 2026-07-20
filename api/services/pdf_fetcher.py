import re

import httpx

CRE_INDEX_URL = "https://www.gob.mx/cne/articulos/precios-maximos-de-gas-lp-399035"


async def find_latest_pdf_url() -> str:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(CRE_INDEX_URL)
        resp.raise_for_status()
    match = re.search(r'(https://www\.gob\.mx/cms/uploads/attachment/file/\d+/[^\s"]+\.pdf)', resp.text)
    if not match:
        raise ValueError("No se encontró el PDF más reciente en la página de la CRE")
    return match.group(1)


async def fetch_pdf(url: str | None = None) -> bytes:
    target = url or await find_latest_pdf_url()
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(target)
        response.raise_for_status()
        return response.content
