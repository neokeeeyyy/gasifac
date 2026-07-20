import io
from dataclasses import dataclass

import pdfplumber


@dataclass
class PrecioRow:
    estado: str
    municipio: str
    region_numero: int
    precio_kg: float
    precio_litro: float


def parse_pdf(pdf_bytes: bytes) -> list[PrecioRow]:
    rows: list[PrecioRow] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue
                header = [str(c).strip().lower() if c else "" for c in table[0]]
                for raw_row in table[1:]:
                    if not raw_row or all(c is None for c in raw_row):
                        continue
                    cleaned = [str(c).strip() if c else "" for c in raw_row]
                    try:
                        row = _map_row(header, cleaned)
                        if row:
                            rows.append(row)
                    except (ValueError, IndexError):
                        continue
    return rows


def _map_row(header: list[str], values: list[str]) -> PrecioRow | None:
    col_map = {}
    for i, h in enumerate(header):
        if "estado" in h:
            col_map["estado"] = i
        elif "municipio" in h or "municipio" in h:
            col_map["municipio"] = i
        elif "regi" in h:
            col_map["region"] = i
        elif "kg" in h:
            col_map["precio_kg"] = i
        elif "litro" in h:
            col_map["precio_litro"] = i

    if not all(k in col_map for k in ("estado", "municipio", "precio_kg", "precio_litro")):
        return None

    return PrecioRow(
        estado=values[col_map["estado"]],
        municipio=values[col_map["municipio"]],
        region_numero=int(values[col_map.get("region", 0)] or 0) if "region" in col_map else 0,
        precio_kg=float(values[col_map["precio_kg"]].replace(",", ".")),
        precio_litro=float(values[col_map["precio_litro"]].replace(",", ".")),
    )
