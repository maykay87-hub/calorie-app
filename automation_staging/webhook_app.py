"""Stripe webhook receiver for May Bloom *staging only*.

Does not grant membership. It verifies and records Stripe events for integration
testing. Never point a live Stripe endpoint at this service.
"""
import os
import stripe
import psycopg
from fastapi import FastAPI, Header, HTTPException, Request

app = FastAPI(title="May Bloom Stripe Staging")

@app.get("/health")
def health():
    return {"status": "ok", "mode": "staging", "fulfillment": "disabled"}

@app.post("/stripe/webhook")
async def webhook(request: Request, stripe_signature: str | None = Header(default=None)):
    if os.getenv("MAY_BLOOM_DEPLOYMENT") != "staging":
        raise HTTPException(503, "Staging environment required")
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    db_url = os.getenv("STAGING_DATABASE_URL", "")
    if not secret or not db_url or not stripe_signature:
        raise HTTPException(503, "Webhook is not configured")
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, secret)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "Invalid Stripe webhook")
    event_id = event.get("id")
    event_type = event.get("type")
    if not isinstance(event_id, str) or not isinstance(event_type, str):
        raise HTTPException(400, "Invalid event")
    # Atomic deduplication; unique id primary key already exists in staging.
    # No account is provisioned until the fulfillment pipeline is separately tested.
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO mb_events (id, kind, processed_at) "
                    "VALUES (%s, %s, EXTRACT(EPOCH FROM NOW())::integer) "
                    "ON CONFLICT (id) DO NOTHING",
                    (event_id, event_type),
                )
    except psycopg.Error:
        raise HTTPException(503, "Event persistence unavailable")
    return {"received": True}
