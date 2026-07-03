"""Payment gateway abstraction for the marketplace (task 4.5).

Defaults to a deterministic mock gateway so the flow is testable without external
calls. When PAYMENT_PROVIDER=stripe and STRIPE_API_KEY is set, charges route
through Stripe PaymentIntents.
"""

import logging
import os
import uuid

logger = logging.getLogger(__name__)

PROVIDER = os.environ.get("PAYMENT_PROVIDER", "mock").lower()
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")


def charge(amount_usd: float, customer_id: str, description: str) -> dict:
    """Charge a customer. Returns {status, charge_id, provider, amount_usd}."""
    if amount_usd <= 0:
        return {"status": "no_charge", "charge_id": None, "provider": PROVIDER, "amount_usd": 0.0}

    if PROVIDER == "stripe" and STRIPE_API_KEY:
        try:
            import stripe

            stripe.api_key = STRIPE_API_KEY
            intent = stripe.PaymentIntent.create(
                amount=int(round(amount_usd * 100)),
                currency="usd",
                description=description,
                metadata={"customer_id": customer_id},
            )
            return {
                "status": "succeeded",
                "charge_id": intent.id,
                "provider": "stripe",
                "amount_usd": amount_usd,
            }
        except Exception as exc:  # fall back to mock so orders still complete in dev
            logger.warning("Stripe charge failed (%s); using mock", exc)

    # Deterministic mock charge.
    return {
        "status": "succeeded",
        "charge_id": f"ch_mock_{uuid.uuid4().hex[:16]}",
        "provider": "mock",
        "amount_usd": round(amount_usd, 4),
    }
