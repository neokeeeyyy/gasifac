import json
import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import get_db
from api.models import Pago, Suscripcion, Usuario
from api.schemas import CheckoutRequest, CheckoutResponse
from api.services.license_generator import generate_pro_license

router = APIRouter(prefix="/api/stripe", tags=["stripe"])

stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(body: CheckoutRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Usuario).where(Usuario.email == body.email)
    )
    usuario = result.scalar_one_or_none()

    if not usuario:
        usuario = Usuario(email=body.email, plan="free")
        db.add(usuario)
        await db.flush()

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[
            {"price": settings.STRIPE_PRICE_ID, "quantity": 1}
        ],
        success_url=body.success_url,
        cancel_url=body.cancel_url,
        customer_email=body.email,
        metadata={
            "usuario_id": str(usuario.id),
            "machine_id": body.machine_id,
        },
    )
    return CheckoutResponse(checkout_url=session.url)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        await _handle_checkout_completed(session, db)
    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        await _handle_subscription_updated(subscription, db)
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        await _handle_subscription_deleted(subscription, db)
    elif event["type"] == "invoice.paid":
        invoice = event["data"]["object"]
        await _handle_invoice_paid(invoice, db)

    return {"status": "ok"}


async def _handle_checkout_completed(session, db: AsyncSession):
    usuario_id = session.get("metadata", {}).get("usuario_id")
    machine_id = session.get("metadata", {}).get("machine_id")
    if not usuario_id:
        return
    result = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    usuario = result.scalar_one_or_none()
    if usuario:
        usuario.stripe_customer_id = session.get("customer")
        sub = Suscripcion(
            usuario_id=usuario_id,
            stripe_subscription_id=session.get("subscription"),
            stripe_price_id=session.get("metadata", {}).get("price_id"),
            status="active",
        )
        db.add(sub)
        usuario.plan = "pro"
        await db.commit()

    if machine_id and usuario:
        license_data = generate_pro_license(machine_id, usuario.email)
        if license_data:
            import httpx
            url = f"{settings.SUPABASE_URL}/storage/v1/object/gasifac/licenses/{machine_id}.json"
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    url,
                    content=json.dumps(license_data, indent=2).encode(),
                    headers={
                        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                        "Content-Type": "application/json",
                        "x-upsert": "true",
                    },
                )


async def _handle_subscription_updated(subscription, db: AsyncSession):
    result = await db.execute(
        select(Suscripcion).where(
            Suscripcion.stripe_subscription_id == subscription["id"]
        )
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.status = subscription["status"]
        await db.commit()


async def _handle_subscription_deleted(subscription, db: AsyncSession):
    result = await db.execute(
        select(Suscripcion).where(
            Suscripcion.stripe_subscription_id == subscription["id"]
        )
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.status = "canceled"
        usuario_result = await db.execute(
            select(Usuario).where(Usuario.id == sub.usuario_id)
        )
        usuario = usuario_result.scalar_one_or_none()
        if usuario:
            usuario.plan = "free"
        await db.commit()


async def _handle_invoice_paid(invoice, db: AsyncSession):
    customer_id = invoice.get("customer")
    result = await db.execute(
        select(Usuario).where(Usuario.stripe_customer_id == customer_id)
    )
    usuario = result.scalar_one_or_none()
    if usuario:
        pago = Pago(
            usuario_id=usuario.id,
            stripe_payment_intent_id=invoice.get("payment_intent"),
            stripe_invoice_id=invoice.get("id"),
            monto_cents=invoice.get("amount_paid", 0),
            moneda=invoice.get("currency", "mxn").upper(),
            status="paid",
        )
        db.add(pago)
        await db.commit()
