# Consultation booking requirements — approved 2026-10-24

This is development configuration, not a published booking calendar. The current
website still uses WhatsApp enquiries. No live availability or payment flow is
enabled by this document or the candidate generator.

## Availability (Asia/Kuala_Lumpur)

- Open dates: 1 November through 31 December 2026 only. Do not roll forward or
  infer any January availability. May will review next year's dates separately.
- Monday–Friday: 14:00–14:45, 15:00–15:45, 16:00–16:45.
- Monday, Tuesday, Wednesday, Friday: also 20:30–21:15.
- Saturday–Sunday: retain 17:00–17:45 from the previous instruction.
- Inclusive full-day exclusions: 14, 22, 28–29 November; 5–12, 24–27 December;
  30 December 2026–3 January 2027. The January exclusion is retained explicitly
  even though no January slots are approved.

`python -m automation_service.availability` prints candidate slots without
network calls or credentials. A deployed booking service must subtract closed,
held and booked slots and enforce lead time before exposing availability.

## Required purchase journey (implemented in development, not hosted)

1. Choose the consultation package and first available appointment.
2. Server holds that slot for a limited period; concurrent customers cannot buy
   the same slot. Expired/failed checkout releases it. Late payments need explicit
   reconciliation, not a second confirmation for an occupied slot.
3. Create Stripe Checkout tied to the hold and approved package/price. Confirm
   only after a verified successful payment webhook; a browser redirect is not
   proof of payment.
4. Confirm the appointment and provide a private pre-consultation questionnaire
   link on the verified paid confirmation page and in the confirmation email.
   Keep the questionnaire link accessible later; email failure must not lose it.
5. May reviews the intake before the appointment. Tracker access, subsequent
   appointments and remaining consultation credits follow the purchased package.

## Short post-payment questionnaire

Use the existing consultation workflow/record template as the starting point:
purchase email and preferred contact, age/sex, height/weight, main goals, relevant
medical history, current medicines/supplements, allergies and activity. Pregnancy
or breastfeeding only when relevant. Existing blood tests/body-composition
reports are optional. Detailed meal history can be taken during the consultation;
follow-ups ask only for changes. Do not require new tests to book.

Do not send medical answers, report attachments or access tokens to Stripe
metadata, payment URLs, public source or logs. Intake needs authenticated/private
access, appropriate privacy/consent text and limited access for May before launch.
The development implementation now provides authenticated form endpoints. They
remain disabled by default; no real health answers have been collected.

## Implementation and release checks — 2026-10-24

- New tables: `mb_consultation_holds` and `mb_consultation_intakes`. Intake
  submissions are encrypted with the deployment's Fernet key and append new
  versions instead of overwriting previous answers. Preserve that key in backups.
  No real report uploader has been added. Reports remain optional and privately
  arranged with May.
- The dedicated member-service `/consultation` page lists published approved
  slots and creates one-time Stripe Checkout for RM199/699/999. `/intake` requires
  a verified account and an owned, paid consultation booking. Coach access is
  checked server-side. General admin summaries and emails omit health answers.
- Checkout returns do not confirm a booking. Verified paid webhook fulfillment
  books the held slot and consumes one package credit in the same transaction.
  Remaining package credits remain available for later appointments.
- Card payments only in this first checkout implementation. Do not advertise FPX
  or other delayed methods as supported by this booking flow until tested.
- A hold lasts up to 60 minutes. Only canonical Stripe `expired` state releases
  it. A network timeout or local clock expiry alone does not release the slot.
  Unknown checkout creation / late paid conflicts are flagged for operator
  review. A paid late conflict preserves paid access but never replaces another
  customer's booking. No automatic refunds are performed.
- `/api/consultation/resume` recovers a pending checkout for its original browser
  using the same idempotency key. No health information is placed in checkout
  metadata, callback URLs or email notifications.
- Set `MB_CONSULTATION_CHECKOUT_ENABLED=false` and `MB_INTAKE_ENABLED=false` until
  test-mode release checks pass. Enabling intake requires a reviewed HTTPS
  `MB_INTAKE_PRIVACY_URL` and `MB_INTAKE_CONSENT_VERSION`. The form records that
  consent version with each submission; this is not a legal compliance audit.
- In an isolated hosted staging database, install the two additive tables from
  current metadata, verify previous tables/records are unchanged and validate
  backup/restore. Local SQLite tests do not establish PostgreSQL deployment.
- Publish approved candidates using `python -m automation_service.admin approved-slots`
  with the staging service origin/key. It skips existing rows, including closed,
  held and booked rows; it never reopens a manually closed slot. The offline
  candidate count is 142, before lead-time checks and operational closures.
- Register `checkout.session.expired` in addition to the existing Stripe webhook
  events. Run the authenticated jobs sweep for expiry recovery/reminders; verify
  actual activation, booking ICS and preparation-notice inbox receipt.
- Verify actual Stripe test payment → webhook → single booking → activation →
  intake → coach review, including two buyers competing for a slot, failed and
  abandoned payments, return-before-webhook, duplicate webhooks, browser retry,
  late paid conflict, account isolation and persisted data after restart.
- Only after hosted validation, link the CURRENT AI Studio website package CTAs
  to the deployed member-service `/consultation?plan=<approved-plan-key>`. Do not
  copy the stale local website export or expose service secrets in AI Studio
  client source. The current public WhatsApp CTAs are unchanged by this commit.
- Google Calendar busy-time sync and automated Google Meet link creation are
  still not implemented. May supplies the meeting link separately. Do not claim
  calendar conflict checks beyond the published slots stored in this service.

Current deployment blocker: the local runtime has no configured member-service
origin, Stripe test credentials/webhook or transactional mail credentials. Google
Cloud Console was observed returning “Site Unavailable” in this browser on
2026-10-24. No new service was deployed, no billing plan was enabled and no live
checkout or questionnaire gate was opened.
