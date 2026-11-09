import hashlib
import hmac
import io
import json
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.api_core.exceptions import PreconditionFailed

import app


SESSION = "cs_test_AAAAAAAAAAAAAAAAAAAAAAAAA"
LINK = "plink_example"
PDF = b"%PDF-1.4\nTest fixture\n"


class MemoryBucket:
    def __init__(self):
        self.objects = {"products/guide.pdf": PDF}
        self.new_objects = 0

    def blob(self, key):
        bucket = self

        class Blob:
            def exists(self):
                return key in bucket.objects

            def upload_from_string(self, data, if_generation_match):
                if if_generation_match != 0:
                    raise AssertionError("Write must be atomic")
                if self.exists():
                    raise PreconditionFailed("Duplicate")
                bucket.objects[key] = data
                bucket.new_objects += 1

            def reload(self):
                self.size = len(bucket.objects[key])

            def open(self, mode, chunk_size):
                return io.BytesIO(bucket.objects[key])

        return Blob()


class FulfillmentTest(unittest.TestCase):
    def setUp(self):
        self.bucket = MemoryBucket()
        for replacement in (
            patch.object(app, "bucket", return_value=self.bucket),
            patch.dict(app.os.environ, {
                "STRIPE_MODE": "test",
                "STRIPE_WEBHOOK_SECRET": "fixture-signing-secret",
                "STRIPE_PAYMENT_LINK_ID": LINK,
                "VAULT_PDF_OBJECT": "products/guide.pdf",
            }),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)
        self.client = TestClient(app.app)
        self.order = {"session_id": SESSION}

    def webhook(self, event_type="checkout.session.completed", livemode=False, valid=True, **fields):
        event = {
            "id": "evt_example", "object": "event", "type": event_type,
            "livemode": livemode, "data": {"object": {
                "id": SESSION, "object": "checkout.session", "mode": "payment",
                "payment_link": LINK, "payment_status": "paid", "currency": "myr",
                "amount_total": 1990, **fields,
            }},
        }
        body = json.dumps(event)
        timestamp = int(time.time())
        signature = hmac.new(
            b"fixture-signing-secret" if valid else b"wrong-key",
            f"{timestamp}.{body}".encode(), hashlib.sha256,
        ).hexdigest()
        return self.client.post("/stripe/webhook", content=body, headers={
            "Stripe-Signature": f"t={timestamp},v1={signature}",
        })

    def test_missing_or_unpaid_order_cannot_download(self):
        self.assertEqual(self.client.post("/download", json=self.order).status_code, 403)
        self.assertEqual(self.webhook(payment_status="unpaid").status_code, 200)
        self.assertEqual(self.client.post("/status", json=self.order).json(), {"ready": False})
        self.assertEqual(self.client.post("/download", json=self.order).status_code, 403)

    def test_rejected_signature(self):
        self.assertEqual(self.webhook(valid=False).status_code, 400)
        self.assertEqual(self.bucket.new_objects, 0)

    def test_unrelated_or_mismatched_payment_is_ignored(self):
        for fields in ({"payment_link": "plink_other"}, {"amount_total": 1900},
                       {"currency": "usd"}, {"livemode": True}, {"mode": "subscription"}):
            with self.subTest(fields=fields):
                self.assertEqual(self.webhook(**fields).status_code, 200)
        self.assertEqual(self.bucket.new_objects, 0)

    def test_paid_order_download_and_webhook_retry(self):
        self.assertEqual(self.webhook().status_code, 200)
        self.assertEqual(self.webhook().status_code, 200)
        self.assertEqual(self.bucket.new_objects, 1)
        self.assertEqual(self.client.post("/status", json=self.order).json(), {"ready": True})
        response = self.client.post("/download", json=self.order)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertEqual(response.content, PDF)

    def test_live_link_metadata_requires_matching_key_and_payment_link(self):
        with patch.dict(app.os.environ, {
            "STRIPE_MODE": "live", "STRIPE_PAYMENT_LINK_ID": "",
            "VAULT_PAYMENT_LINK_KEY": "eat-and-shop-smart-live",
        }):
            live_session = SESSION.replace("cs_test_", "cs_live_")
            order = {"session_id": live_session}
            self.webhook(livemode=True, id=live_session, metadata={"vault_key": "another-product"})
            self.webhook(livemode=True, id=live_session, payment_link=None,
                         metadata={"vault_key": "eat-and-shop-smart-live"})
            self.assertEqual(self.client.post("/download", json=order).status_code, 403)
            self.assertEqual(self.webhook(livemode=True, id=live_session,
                                          metadata={"vault_key": "eat-and-shop-smart-live"}).status_code, 200)
            self.assertEqual(self.client.post("/download", json=order).status_code, 200)

    def test_webhook_is_unavailable_until_signing_secret_is_configured(self):
        with patch.dict(app.os.environ, {"STRIPE_WEBHOOK_SECRET": ""}):
            self.assertEqual(self.webhook().status_code, 503)
            self.assertEqual(self.bucket.new_objects, 0)

    def test_delayed_payment_grants_access_after_confirmation(self):
        self.webhook(payment_status="unpaid")
        self.assertEqual(self.client.post("/download", json=self.order).status_code, 403)
        self.assertEqual(self.webhook("checkout.session.async_payment_succeeded").status_code, 200)
        self.assertEqual(self.client.post("/download", json=self.order).status_code, 200)


if __name__ == "__main__":
    unittest.main()
