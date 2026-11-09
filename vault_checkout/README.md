# May Bloom Vault · Eat & Shop Smart delivery

This directory runs as a separate Cloud Run service from the consultation application. It receives Stripe Payment Link events and serves the 54-page guide from a private Cloud Storage bucket. The PDF, checkout session IDs and credentials are excluded from the repository and image.

## Configuration

| Setting | Source |
|---|---|
| `STRIPE_MODE` | `test` for the Stripe sandbox, `live` for production |
| `STRIPE_PAYMENT_LINK_ID` | The single Payment Link for this guide in that mode |
| `STRIPE_WEBHOOK_SECRET` | Secret Manager reference for this service's Stripe event destination |
| `VAULT_BUCKET` | A dedicated private bucket in the matching environment with public access prevention enabled |
| `VAULT_PDF_OBJECT` | Object path for the checked 54-page PDF, e.g. `products/eat-and-shop-smart-v1.pdf` |

The runtime service account needs `storage.objects.get` for the PDF and orders, `storage.objects.create` for new orders, and Secret Manager access to this endpoint's signing secret. It needs no Stripe API key, access to consultation data, or storage deletion permission. The public Cloud Run ingress is needed for Stripe and the customer-facing delivery page. The storage bucket remains private. Do not use the existing consultation event destination.

Configure a Stripe Payment Link with one unit at MYR 19.90, no price adjustments, and automatic tax off under May's current setup. Verify the displayed MYR price and the webhook's actual `currency` and `amount_total` before launch. The Stripe after-payment redirect target is `https://<service>/eat-and-shop-smart#session_id={CHECKOUT_SESSION_ID}`. Use the fragment to avoid putting the purchase reference in HTTP request URLs and logs. Verify in the sandbox that the placeholder is replaced and the fragment is retained.

Register this service's `POST /stripe/webhook` as a snapshot event destination for `checkout.session.completed` and `checkout.session.async_payment_succeeded`. Use a separate destination and signing secret in each environment. If a completed session is still unpaid, the service waits for the paid event. It records a hashed purchase reference with an atomic conditional write and exposes the PDF only if that record exists.

The buyer needs the Stripe return page in the same tab to download. If they lose the page, May can verify the order in Stripe and assist through the contact link. The service does not send buyer emails.

## Release checks

1. Run `pip install -r requirements.txt httpx` and `python -m unittest -v` in this directory.
2. In an isolated Stripe sandbox and Cloud Run test service, check that opening the delivery page by itself or cancelling checkout gives no PDF. Complete a sandbox purchase and confirm the signed event is accepted and the actual 54-page PDF downloads on desktop and phone.
3. Replay the same test event and confirm access still works with one order marker. Check a delayed payment and retry only after it is paid. Verify the file and purchase reference never appear on the public site.
4. After the sandbox passes, set up the separate live service and signed webhook. Verify health and the unpaid path. Attach the Stripe Payment Link to the existing product page only once the live configuration is ready. Keep the 6-page preview available throughout.
