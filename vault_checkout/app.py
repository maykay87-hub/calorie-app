"""Stripe-verified delivery for the May Bloom Eat & Shop Smart PDF."""

import hashlib
import os
import re
from pathlib import Path

import stripe
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from google.api_core.exceptions import NotFound, PreconditionFailed
from google.cloud import storage
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool


PRICE_MINOR = 1990
PDF_NAME = "MayBloom-Eat-and-Shop-Smart-Bundle.pdf"
ASSETS = Path(__file__).parent
SESSION_ID = re.compile(r"cs_(live|test)_[A-Za-z0-9]{16,200}\Z")
PAID_EVENTS = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


class DownloadRequest(BaseModel):
    session_id: str = Field(max_length=220)


def configured_mode() -> str:
    mode = os.environ["STRIPE_MODE"]
    if mode not in {"live", "test"}:
        raise RuntimeError("Invalid Stripe mode")
    return mode


def order_key(session_id: str, mode: str) -> str | None:
    match = SESSION_ID.fullmatch(session_id)
    if not match or match.group(1) != mode:
        return None
    return f"orders/{mode}/{hashlib.sha256(session_id.encode()).hexdigest()}"


def paid_order_key(event: dict, mode: str, payment_link: str) -> str | None:
    if event.get("type") not in PAID_EVENTS or event.get("livemode") is not (mode == "live"):
        return None
    session = event["data"]["object"]
    if (
        session.get("payment_link") != payment_link
        or session.get("payment_status") != "paid"
        or session.get("mode") != "payment"
        or session.get("currency") != "myr"
        or session.get("amount_total") != PRICE_MINOR
    ):
        return None
    return order_key(session["id"], mode)


def bucket():
    return storage.Client().bucket(os.environ["VAULT_BUCKET"])


def record_paid_order(key: str) -> None:
    try:
        bucket().blob(key).upload_from_string(b"paid", if_generation_match=0)
    except PreconditionFailed:
        # A retry found the existing paid order.
        pass


def has_paid_order(session_id: str) -> bool:
    key = order_key(session_id, configured_mode())
    return bool(key and bucket().blob(key).exists())


@app.middleware("http")
async def private_responses(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'self'; connect-src 'self'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(default="")):
    try:
        event = stripe.Webhook.construct_event(
            await request.body(), stripe_signature, os.environ["STRIPE_WEBHOOK_SECRET"]
        ).to_dict()
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "Invalid Stripe signature") from None

    key = paid_order_key(event, configured_mode(), os.environ["STRIPE_PAYMENT_LINK_ID"])
    if key:
        await run_in_threadpool(record_paid_order, key)
    return {"received": True}


@app.get("/eat-and-shop-smart")
def landing():
    return FileResponse(ASSETS / "delivery.html", media_type="text/html")


@app.get("/delivery.js")
def delivery_script():
    return FileResponse(ASSETS / "delivery.js", media_type="text/javascript")


@app.post("/status")
def order_status(payload: DownloadRequest):
    return {"ready": has_paid_order(payload.session_id)}


@app.post("/download")
def download(payload: DownloadRequest):
    if not has_paid_order(payload.session_id):
        raise HTTPException(403, "Payment has not been verified")
    pdf = bucket().blob(os.environ["VAULT_PDF_OBJECT"])
    try:
        pdf.reload()
    except NotFound:
        raise HTTPException(503, "PDF temporarily unavailable") from None

    def stream_pdf():
        with pdf.open("rb", chunk_size=2 * 1024 * 1024) as reader:
            while chunk := reader.read(2 * 1024 * 1024):
                yield chunk

    return StreamingResponse(
        stream_pdf(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{PDF_NAME}"',
            "Content-Length": str(pdf.size),
        },
    )
