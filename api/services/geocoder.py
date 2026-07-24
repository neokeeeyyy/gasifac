import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "GasifacBot/1.0 (https://neokey.dev)"


async def geocode_municipio(municipio: str, estado: str) -> dict | None:
    query = f"{municipio}, {estado}, Mexico"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "mx"},
            headers={"User-Agent": USER_AGENT},
        )
        if resp.status_code == 429:
            raise Exception("Rate limited")
        if resp.status_code >= 500:
            raise Exception(f"Server error {resp.status_code}")
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data:
            return None
        return {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}
