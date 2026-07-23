import httpx
from fastapi import APIRouter, HTTPException

from api.config import settings
from api.schemas import SugerenciaRequest

router = APIRouter(prefix="/api/v1", tags=["sugerencias"])

CATEGORY_LABELS = {
    "bug": "Error / Bug",
    "feature": "Nueva funcionalidad",
    "mejora": "Mejora existente",
    "otro": "Otro",
}


@router.post("/sugerencias")
async def send_suggestion(body: SugerenciaRequest):
    if not settings.RESEND_API_KEY:
        raise HTTPException(status_code=500, detail="Servicio de correo no configurado.")

    category_label = CATEGORY_LABELS.get(body.category, body.category)

    html = f"""
    <div style="font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:32px;">
      <h2 style="margin:0 0 8px;font-size:1.2rem;">Nueva sugerencia — Gasifac</h2>
      <p style="color:#666;font-size:0.85rem;margin:0 0 24px;">Recibida desde neokey.dev/gasifac/sugerencias</p>
      <table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
        <tr>
          <td style="padding:8px 0;color:#888;width:120px;vertical-align:top;">Nombre</td>
          <td style="padding:8px 0;font-weight:600;">{body.name}</td>
        </tr>
        <tr>
          <td style="padding:8px 0;color:#888;vertical-align:top;">Correo</td>
          <td style="padding:8px 0;font-weight:600;">{body.email}</td>
        </tr>
        <tr>
          <td style="padding:8px 0;color:#888;vertical-align:top;">Categoría</td>
          <td style="padding:8px 0;font-weight:600;">{category_label}</td>
        </tr>
      </table>
      <div style="margin-top:20px;padding:16px;background:#f5f5f5;border-radius:8px;font-size:0.9rem;line-height:1.7;color:#333;">
        {body.message.replace(chr(10), '<br>')}
      </div>
    </div>
    """

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": "Gasifac <sugerencias@neokey.dev>",
                "to": ["soporte@neokey.dev"],
                "reply_to": body.email,
                "subject": f"[Gasifac] {category_label} — {body.name}",
                "html": html,
            },
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail="Error al enviar el correo.")

    return {"ok": True}
