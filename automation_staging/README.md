# May Bloom Stripe + Neon staging

This is an isolated Stripe webhook **receiver**, not yet a membership fulfillment system. It does not modify production Streamlit or Google Sheets.

## Current verified state
- Neon project: `MayBloom Member Automation Test`
- Staging branch: `staging-automation-20261023` (use its connection string, not the default/baseline branch)
- Existing table: `public.mb_events(id, kind, processed_at)` with a primary key on `id`
- GitHub branch: `feature/stripe-neon-staging-20261027`

## Deployment
Deploy `automation_staging.webhook_app:app` with ASGI server `uvicorn automation_staging.webhook_app:app --host 0.0.0.0 --port ${PORT:-8080}`. Install `automation_staging/requirements.txt`.

Configure **server-side secrets only**, never commit values:
- `MAY_BLOOM_DEPLOYMENT=staging`
- `STAGING_DATABASE_URL` = Neon staging branch connection string
- `STRIPE_WEBHOOK_SECRET` = signing secret for the **test-mode endpoint**

Health: `GET /health`; Stripe endpoint: `POST /stripe/webhook`.

## Acceptance checks before enabling any fulfillment
1. Deployment is HTTPS and health check works.
2. Invalid signature gets HTTP 400; missing configuration gets 503.
3. Valid Stripe test-mode event gets HTTP 200 and one `mb_events` record.
4. Retrying same event does not create a second record.
5. Confirm connection string targets Neon staging branch, not baseline.
6. Test a failed database connection and confirm 503 so Stripe retries.
7. Only then implement and test paid-product mapping, member grant, expiry, email invitation, refunds and disputes. Never grant membership on receipt alone without validated product/payment state.

Do not use live Stripe keys or real customer information in staging. No credentials should appear in chat or GitHub files.
