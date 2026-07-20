import io
import re
from dataclasses import dataclass, field

import pdfplumber


MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


@dataclass
class PrecioRow:
    estado: str
    municipio: str
    region_numero: int
    precio_kg: float
    precio_litro: float


@dataclass
class ParseResult:
    rows: list[PrecioRow]
    total_pages: int
    periodo_inicio: str = ""
    periodo_fin: str = ""


def parse_pdf(pdf_bytes: bytes, page_start: int = 0, page_end: int | None = None) -> ParseResult:
    rows: list[PrecioRow] = []
    periodo_inicio = ""
    periodo_fin = ""

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        total_pages = len(pdf.pages)

        first_text = pdf.pages[0].extract_text() or ""
        periodo_inicio, periodo_fin = _extract_period(first_text)

        end = page_end or total_pages
        for page in pdf.pages[page_start:end]:
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue
                header_idx = 0
                first_row = [str(c).strip().lower() if c else "" for c in table[0]]
                if not any(k in " ".join(first_row) for k in ("region", "entidad", "municipio")):
                    header_idx = 1
                if header_idx >= len(table):
                    continue
                header = [str(c).strip().lower() if c else "" for c in table[header_idx]]
                for raw_row in table[header_idx + 1:]:
                    if not raw_row or all(c is None for c in raw_row):
                        continue
                    cleaned = [str(c).strip() if c else "" for c in raw_row]
                    try:
                        row = _map_row(header, cleaned)
                        if row:
                            rows.append(row)
                    except (ValueError, IndexError):
                        continue

    return ParseResult(rows=rows, total_pages=total_pages, periodo_inicio=periodo_inicio, periodo_fin=periodo_fin)


def _extract_period(text: str) -> tuple[str, str]:
    match = re.search(
        r"DEL\s+(\d{1,2})\s+AL\s+(\d{1,2})\s+DE\s+(\w+)\s+DE\s+(\d{4})",
        text, re.IGNORECASE,
    )
    if not match:
        return "", ""
    dia_inicio, dia_fin, mes_str, anio = match.groups()
    mes = MESES.get(mes_str.lower(), 0)
    if not mes:
        return "", ""
    inicio = f"{anio}-{mes:02d}-{int(dia_inicio):02d}"
    fin = f"{anio}-{mes:02d}-{int(dia_fin):02d}"
    return inicio, fin


def _map_row(header: list[str], values: list[str]) -> PrecioRow | None:
    col_map = {}
    for i, h in enumerate(header):
        if "estado" in h or "entidad" in h:
            col_map["estado"] = i
        elif "municipio" in h:
            col_map["municipio"] = i
        elif "regi" in h:
            col_map["region"] = i
        elif "kg" in h or "kilogramo" in h:
            col_map["precio_kg"] = i
        elif "litro" in h:
            col_map["precio_litro"] = i

    if not all(k in col_map for k in ("estado", "municipio", "precio_kg", "precio_litro")):
        return None

    price_kg = values[col_map["precio_kg"]].replace("$", "").replace(",", ".").strip()
    price_litro = values[col_map["precio_litro"]].replace("$", "").replace(",", ".").strip()

    return PrecioRow(
        estado=values[col_map["estado"]],
        municipio=values[col_map["municipio"]],
        region_numero=int(values[col_map.get("region", 0)] or 0) if "region" in col_map else 0,
        precio_kg=float(price_kg),
        precio_litro=float(price_litro),
    )
