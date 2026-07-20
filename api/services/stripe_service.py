import stripe

from api.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_checkout_session(
    email: str,
    success_url: str,
    cancel_url: str,
    usuario_id: str,
) -> stripe.checkout.Session:
    return stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=email,
        metadata={"usuario_id": usuario_id},
    )
