# Member service — staging implementation

This service is separate from Streamlit. It is **not deployed** and live fulfillment is disabled by default. No payment key, production account record, live webhook, SMTP login, database ID or student attachment is included in this repository.

## Implemented

- Signed Stripe webhooks with environment checks, canonical API reads, exact approved-price mapping and atomic deduplication by event and fulfilled payment object.
- Monthly access comes from paid invoice periods, not a guessed 30-day extension. Subscription cancellation is reconciled against Stripe; a stale event cannot reopen ended access. A failed renewal flags an operator issue without removing already-paid access or health records.
- One-time RM199 / RM699 / RM999 packages with 1 / 3 / 6 consultation credits and 7 days / 3 months / 6 months of Tracker access. They never become recurring subscriptions.
- Email activation and password reset, hashed passwords and session tokens, one-time activation tokens, 24-hour sessions, rate limits and encrypted transactional-email outbox. Tokens are not placed in frontend source or server logs.
- A bilingual member page, available-slot listing, 45-minute bookings, 15-minute separation, credit consumption and transactional prevention of double booking. All displayed appointment times use Asia/Kuala_Lumpur. The default booking lead time is 24 hours, configurable before launch.
- Confirmation emails with an ICS calendar attachment and one reminder within 24 hours of an appointment. May receives a separate booking notice at `MB_COACH_EMAIL`. SMTP runs in a separate authenticated jobs request. Ambiguous SMTP failures are flagged, not blindly resent.
- An optional HTTPS server-to-server Streamlit bridge, disabled unless explicitly configured. Existing manually configured accounts remain supported. A legacy student signs into the original Tracker account before linking an activated member account, retaining the original Sheets username and records. Already-used new Tracker identities cannot be silently renamed over existing data; those cases require reviewed migration.
- Coach access to new members, displayed by email rather than opaque storage keys. Student sessions cannot obtain the bridge key or admin key.

## What is not connected

No live Stripe webhook, deployment, durable database, outgoing mail sender, scheduled jobs, public member-service URL or production Streamlit secret has been configured. Published availability is managed in this service; **Google Calendar busy-time synchronization, Google Meet/Zoom link creation, automatic rescheduling/cancellation are not implemented**. May must supply the meeting link separately. No invented appointment schedule is enabled.

**Legacy-account linking is separately disabled by default.** Before enabling it, May must review existing paid rights, including Baya course access and its different review schedule. This service models the four new Stripe plans only; it does not import Baya orders or infer old course expiry. Do not let a new shorter Stripe purchase replace a longer existing paid entitlement. Unlinked old accounts continue using their existing login. Set both `MB_LEGACY_LINK_ENABLED=true` and the Tracker's `legacy_link_enabled=true` only after the migration has been reviewed and all existing rights are represented or otherwise preserved.

Human dietitian reviews remain human work. The existing dated review history is preserved. Refund/dispute events create review flags; they do not automatically refund money, delete records or guess a refund policy. Package expiry, reminders, start-date policy and rescheduling terms need owner review.

## Deployment prerequisites

1. Use an isolated Stripe test environment and an independent durable PostgreSQL database. SQLite is local QA only; production startup rejects it. PostgreSQL concurrency and actual cloud infrastructure must be tested before release.
2. Build the image from repository root with `docker build -f automation_service/Dockerfile .`. Deploy it as a separate server service. Do not replace the Streamlit app or existing website service. Configure HTTPS and the exact `MB_PUBLIC_URL`.
3. Configure server secrets using `.env.example`: database, three distinct strong keys, a Fernet encryption key, Stripe API/webhook credentials and an authenticated SMTP sender. A Fernet key can be generated using the cryptography library; never place it in source control. Preserve this encryption key in the disaster-recovery plan or queued emails cannot be decrypted.
4. Set `MB_STRIPE_PRICE_PLANS` to an object mapping exactly four **test** Price IDs to `tracker-monthly`, `consultation-initial`, `consultation-three-months`, and `consultation-six-months`. Stripe Price IDs, not product names, control grants. The gateway checks MYR base prices of 4800 / 19900 / 69900 / 99900 minor units and the recurring/one-time type. Public currency conversion is not used to infer a package.
5. Register `/stripe/webhook` with Stripe for `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`, `charge.refunded`, and `charge.dispute.created`.
6. Configure a scheduler to POST `/admin/run-jobs` every five minutes with `Authorization: Bearer <MB_ADMIN_KEY>`. Do not put the key in a scheduler URL. Test actual email receipt, appointment ICS and reminder delivery. Check `/admin/summary` for reconciliation and uncertain-mail issues.
7. Publish only the appointment slots May has actually approved. `python -m automation_service.admin slot --at <timezone-aware timestamp>` uses `MB_PUBLIC_URL` and `MB_ADMIN_KEY` from the environment. Slots are 45 minutes with 15 minutes between adjacent appointments. No slots exist unless published. Enable `MB_BOOKING_ENABLED` only after reviewing availability and operational rules.
8. Configure the **private staging** Tracker secrets:

   ```toml
   [membership_service]
   enabled = false
   legacy_link_enabled = false
   url = ""
   bridge_key = ""
   ```

   Set an HTTPS origin, a matching bridge key and `enabled = true` only for the private staging test. Demo mode remains before secrets and every external connection.
9. Merge the accompanying website patch into a fresh export of the current AI Studio site. The patch contains the four approved live Payment Links, but checkout and automatic member entry remain release-gated. Set the member origin only after it is deployed and tested. Do not overwrite newer website edits using an old source ZIP.
10. Run the complete test-mode buyer journey: pay → receipt → activation email → set password → Tracker → saved food/remark/file → coach review → published appointment → confirmation/reminder → renewal → failed renewal → cancellation → same-account re-purchase. Test the legacy-account linking path and both directions of account isolation.
11. Finalize public service/privacy/refund and rescheduling terms. Review the chosen package start policy: the draft defaults to first account activation for new accounts, immediate activation on purchase for already-activated accounts. It does not invent deferred package stacking. Decide how concurrent purchases and future package renewals should behave before live sales.
12. Back up existing data, record release source and a database recovery plan, then validate and promote a release separately. Use live Stripe price mappings and `MB_STRIPE_LIVE=true` only after the checklist passes and `MB_RELEASE_REVIEWED=true` is deliberately set. Do not move the existing release snapshot or replace current student records.

## Operator workflows

- `python -m automation_service.admin summary`: review accounts, payment/refund/dispute flags, and email-delivery states. Treat output as private student contact information; do not paste it into tickets or Git.
- `python -m automation_service.admin jobs`: run the email/reminder queue once. A successful SMTP acceptance is not proof of inbox delivery; verify the receiving mailbox in staging.
- `python -m automation_service.admin close-slot --slot-id <id>`: close an unbooked slot. Booked appointments cannot be silently canceled through this action. Re-publishing the same closed time reopens it after overlap validation.
- Expired or canceled access hides service access, not saved health data. Data export/retention requirements and access after expiry must be specified in public terms before release.
- After a member links an old Tracker account, the same internal username continues to address saved history. If a member already started using the newly generated Tracker identity, stop and review the two record sets before migration; never overwrite or automatically merge them.
- Database schema changes need explicit migrations and backups after initial release. `create_all` only installs the initial tables; it is not an upgrade/migration system.

## Tests and evidence

Run `python -m pytest -q` in a virtual environment containing the root Tracker requirements, this service's requirements and pytest. The service tests use synthetic Stripe objects, signed test payloads, temporary SQLite files and captured fake mail senders. They exercise HTTP authentication, CSRF, replay, duplicate fulfillment, expiry, renewal, concurrent bookings and email failure. They do **not** establish live Stripe, PostgreSQL, SMTP, Google Calendar or cloud-deployment readiness.

Primary implementation references: https://docs.stripe.com/checkout/fulfillment and https://docs.stripe.com/billing/subscriptions/webhooks . Stripe Python 16 resources are converted using their documented `to_dict()` boundary before processing.

## May’s availability screen

Set `MB_COACH_EMAIL` to the verified owner mailbox. At the member portal, request an activation email using that address and set a password through the delivered link. This verified owner can publish and close available consultation slots, inspect bookings and see follow-up issues without purchasing a plan or exposing admin API keys. A working mail sender and email worker are required. Enter times in Malaysia time. Published slots protect availability within this service only; outside calendar conflicts must still be checked.

## Deployment check before connecting services

Run `python -m automation_service.preflight` inside the configured server environment. It reads environment variables, prints only field names and fixed diagnostic reasons, exits with code 2 for invalid setup, and never calls Stripe, SMTP or PostgreSQL. A passing result confirms configuration shape only; it does not replace the buyer-journey tests. Use the installed `psycopg` driver explicitly in `MB_DATABASE_URL`: `postgresql+psycopg://...`.

For a Google Cloud deployment, follow [the Cloud Run connection guide](../docs/member-service-cloud-run.md). Hosting has not been created and no billing or access permissions have been changed.

## Low-cost event-driven option — not deployed

See [service model and cost controls](../docs/service-model-and-cost-controls.md).
Set MB_TASK_QUEUE to an already-provisioned dedicated Cloud Tasks resource path
only after runtime enqueue permissions, worker authentication, real mail delivery
and quota checks pass. Blank (default) makes no Google credential/API calls.
This code does not create queues or grant IAM permissions.

The optional dispatcher wakes /admin/run-jobs after committed payments, queued
activation/reset messages and successful bookings. SMTP stays outside the Stripe
webhook. Queue failures preserve the outbox and flag an operator issue. Stable
hashed task names handle event replay; task inspection must be restricted because
request headers contain the private worker credential. Configure worker timeout
to at least 600 seconds and review email batch size, queue concurrency, retries
and sender limits before launch. Do not log task headers or full request objects.

Once actual event wakeups pass, use a 30-minute recovery/reminder sweep instead of
the original five-minute scheduler-only instructions above. Without wakeups, mail
can wait for the next sweep; that is not instant activation. Frequent empty polls
can exhaust a sleeping database's free compute allowance even with no buyers.
No Cloud Tasks queue or sender has been configured yet. The isolated Neon Free
test database is now provisioned; see the validation checkpoint below.

## Returning-student continuation — development only

MB_RENEWAL_ENABLED defaults to false. When deliberately enabled in staging,
/api/renewal requires an authenticated verified member, non-revoked paid history
and no remaining/future/unstarted paid access. Explicit monthly-subscription
consent is required. The server checks all matching Stripe customer identities
for active, trialing, past-due, unpaid, paused or incomplete subscriptions before
creating one fixed-price, fixed-quantity Checkout Session. Retried/concurrent
requests reuse a one-hour reservation and Stripe idempotency key. A redirect
never creates access; only canonical paid-invoice fulfillment does.

The new mb_renewal_checkouts table is additive; no existing record is rewritten.
Before an actual student release, back up and verify this schema change on a
dedicated PostgreSQL staging database, including concurrent requests and restore.
SQLite compatibility tests are not evidence of production PostgreSQL validation.

Before opening live continuation, retire the unrestricted public monthly Payment
Link after reviewing existing subscribers, and verify their renewals continue.
Do not reject already-paid legacy invoices or silently cancel subscriptions.
Do not expose the private renewal form as a public sign-up product.
Baya course entitlements still require verified order ingestion/import before
they can qualify here; no course-order integration has been assumed or created.

## PostgreSQL validation checkpoint — 2026-10-23

An isolated Neon Free project in Singapore now has a clean baseline branch and
a separate staging branch. Compute is fixed at 0.25 CU; the baseline was observed
automatically suspended after about five minutes idle. No paid plan or add-on
was enabled. No existing Sheets records or student deployment were changed.

`python -m automation_service.postgres_validation --run-id <8-24 hex characters>`
generates synthetic SQL checks from the current SQLAlchemy schema; it does not
connect or load credentials. Use explicit test project/branch/database targets.
The database name must end in `_test`. Run the plan sections in order, with both
booking transactions submitted concurrently, and expect the deliberate rollback
section to fail. Never run this helper against a student database.

Official Neon SQL tools executed the 13-table schema on PostgreSQL 17.11. Checks
observed one entitlement/event after payment replay, one booking and one debit
for two competing transactions, no change on retry, and complete rollback after
a deliberate unique-constraint failure. A logical export containing eight
synthetic rows was rebuilt in a second empty test database; all 13 tables matched.
The restore generator also rejects nonempty destinations rather than merging.

These are representative SQL transaction checks, not execution of the Python
application against Neon. This environment cannot resolve the database hostname.
The 55 focused local application tests passed separately. Actual hosted driver
connectivity, concurrent application requests, Stripe test events, real email,
queue retries, and hosted recovery remain release requirements. The logical
rebuild does not validate pg_dump/pg_restore, provider PITR, or existing Sheets
backups. Google Cloud console still returns Site Unavailable in this browser;
deployment has not been performed.
