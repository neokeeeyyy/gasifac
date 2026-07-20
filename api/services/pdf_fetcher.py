import httpx

CRE_PDF_URL = "https://www.gob.mx/cms/uploads/attachment/file/..."  # URL real del PDF CRE


async def fetch_pdf(url: str | None = None) -> bytes:
    target = url or CRE_PDF_URL
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(target)
        response.raise_for_status()
        return response.content
