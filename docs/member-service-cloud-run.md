# Google Cloud connection guide — not deployed

The existing AI Studio website remains the public front end. Deploy the membership API as a separate Cloud Run service built from `automation_service/Dockerfile` at the repository root. This guide does not create resources or authorize cloud spending. The browser could not open the Google Cloud console during the 22 October connection check; the website's actual Cloud project and its permissions remain unverified.

## Required decisions and access

Identify the existing website project in the owner's Google Cloud console before provisioning anything. Confirm the region, billing budget and dedicated PostgreSQL database. Do not reuse the production Tracker spreadsheet or copy student records into staging. Select a transactional sender and verify access to the sending domain/mailbox. Google account sign-in alone does not configure an authenticated SMTP sender.

## Service setup

1. Build the image using the repository-root context and `automation_service/Dockerfile`. Deploy a separate test service with container port **8080**. Keep the existing AI Studio website and student Streamlit service unchanged.
2. Connect durable PostgreSQL using the installed `psycopg` driver (`postgresql+psycopg://...`). Configure the Cloud SQL connection or private networking appropriate to that database. Enable backups and verify a restore with synthetic data before live student use.
3. Store credentials in Secret Manager and give the runtime identity access only to the required secret versions. Database credentials, encryption key, Stripe API/webhook keys, private Tracker bridge key, admin key and SMTP password never belong in GitHub or frontend source. Preserve the encryption key separately in the recovery plan.
4. Configure all fields in `.env.example`. Set `MB_ENV=production`, but keep Stripe **test mode** and release/booking/legacy-link switches off initially. The HTTPS `MB_PUBLIC_URL` must match the service's actual origin, with no path. The app verifies browser POST origin against this exact value. Do not guess a future URL.
5. Run `python -m automation_service.preflight` in the configured server environment. This does not contact external services and intentionally prints no supplied values. Resolve its named errors before starting a real buyer test.
6. The member page and Stripe webhook need external reachability. Any Cloud Run IAM/public access changes must be explicitly reviewed when applying them. The application retains its own member sessions, private bridge secret and admin authentication; never remove those controls to make a request work.
7. Register the test Stripe webhook at the real `/stripe/webhook` URL with the event list in the service README. Use the four matching **test Price IDs**, not live product names or live Payment Link URLs. Verify amounts, mode, signature rejection, replay and delayed invoice delivery.
8. Configure a protected scheduler to call `POST /admin/run-jobs` every five minutes. This endpoint uses its application `Authorization: Bearer` credential. Do not overwrite that header with an unrelated OIDC token or place the credential in a URL. Keep scheduler configuration private, restrict access and never log the header. An alternative private worker architecture needs a separate implementation and verification before replacing this setup.
9. Verify activation and booking emails arrive in the actual test inbox, then check reminders and ambiguous-send follow-up. SMTP acceptance alone is not inbox delivery. May signs in with the exact configured coach mailbox to publish only actual available times. Calendar conflict sync and automatic meeting URLs are not implemented.
10. Connect the private staging Tracker bridge, complete record/remark/attachment and coach review checks with synthetic users, and verify account isolation. Leave old-student linking disabled until existing paid rights are reviewed.
11. Record the tested GitHub commit, back up data and finalize start/expiry/refund/rescheduling terms. Only then configure live Stripe mappings, review the live release switch, and update website/Stripe next-step instructions. A frontend redirect does not grant paid access.

## Current external blocker

No Cloud Run service, PostgreSQL database, verified SMTP sender or scheduler has been provisioned through this work. The Google Cloud console returned “Site Unavailable” in this browser after one reload. This is an access limitation of the current session, not evidence that the user's Google project is down. Continue from the actual owner project once console access is available; do not silently move the site or member data to a different hosting provider.

Official references:
- https://docs.cloud.google.com/run/docs/configuring
- https://docs.cloud.google.com/run/docs/configuring/services/secrets
- https://docs.cloud.google.com/run/docs/triggering/using-scheduler

## Cost-conscious alternative

The optional event dispatcher is implemented but not provisioned. Follow the
service README and service-model-and-cost-controls.md before using a 30-minute
recovery sweep in place of the original five-minute baseline. The latter is not
a free-tier cost guarantee. Test queue permissions, runtime default credentials,
worker authentication and real delivery first; no unawaited post-response SMTP.
