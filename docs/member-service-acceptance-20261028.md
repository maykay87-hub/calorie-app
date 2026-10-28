# Member service acceptance — 28 October 2026 (MYT)

## Hosted evidence

The separate member service has now built and deployed successfully. An actual
Stripe sandbox RM199 Checkout payment created one consultation-initial grant in
the isolated PostgreSQL staging database. The owner received the activation
email, activated the account and opened the coach portal on a phone. Database
reads confirm verified_at, one consultation credit, and exactly seven days
between starts_at and ends_at. The two purchase/activation outbox items are sent.
The coach also published a future availability slot successfully.

The full-service checkout notification was observed as HTTP 200 with result
processed in Stripe Event deliveries. A deliberate resend on 28 October at
00:15:54 MYT returned HTTP 200 with result duplicate. Subsequent PostgreSQL reads
confirm exactly one event, exactly one grant for that payment and zero pending
mail. The newly deployed `/api/health` route returns ok=true, live=false and
booking_enabled=false on the actual hosted service.

This is sandbox fulfillment evidence. It is not a live release, an end-to-end
hosted booking test, or evidence that Tracker login is connected. A synthetic
appointment remains visible in the coach portal; it is not a customer booking.
No password, activation token, private database identifier or email payload is
recorded here.

## Completed preparation for reliable email

`automation_service/scripts/connect_jobs.py` consolidates the remaining cloud
configuration into a repeatable procedure. It is not executed by importing or
running tests. It defaults to a read-only preflight and requires `--apply` to
change cloud resources.

From the repository root in the owner's authenticated Cloud Shell:

```bash
python3 automation_service/scripts/connect_jobs.py --project YOUR_PROJECT_ID
python3 automation_service/scripts/connect_jobs.py --project YOUR_PROJECT_ID --apply
```

The apply step verifies explicitly disabled live Stripe mode, reads the current
service origin and existing Secret Manager reference, enables the required APIs,
creates or updates a dedicated mail queue, grants the current runtime identity
queue-scoped enqueue permission, sets the worker timeout to 600 seconds, and adds
only MB_TASK_QUEUE to the service environment. It preserves other variables and
secret references. It creates or updates a dedicated 30-minute recovery job and
checks the authenticated worker response.

Credentials are read into process memory. They are not command arguments,
temporary files, terminal output or repository data. Cloud Tasks and Scheduler
store the private worker Authorization header, so task/job inspection permissions
must remain restricted. This setup uses no OIDC header that would replace the
application's worker credential. Cloud APIs, builds, queue retries and executions
can incur usage charges; a zero monthly bill is not guaranteed.

The script refuses queue routing overrides and a recovery job pointing at a
different service. Failures can leave completed earlier steps in place; rerun
after resolving permissions rather than deleting existing resources. It never
deletes resources, changes public IAM, enables live payments or alters a database.

After applying, verify an actual event-generated activation/reset email arrives
without manually calling the worker; inspect successful queue delivery and the
scheduled recovery execution. A successful direct worker response alone does
not verify the runtime identity's enqueue permission or Scheduler delivery.

An additional `/api/health` route provides the same limited mode/health response
as `/healthz`. Use it to avoid the observed Google-branded `/healthz` 404 in this
hosted environment; the original route remains available for existing callers.

## Remaining acceptance work

- Apply and validate the queue/recovery configuration in the owner Cloud session.
- Confirm the private staging Tracker app and its independent test Sheet. Its
  existing membership client on development/next requires a private
  `[membership_service]` section: enabled=true, url=the exact member-service
  HTTPS origin, bridge_key=the existing server secret. Keep legacy_link_enabled
  false. Never expose that key in the portal or a browser URL. Configure
  MB_TRACKER_URL only after confirming this staging app and its private bridge.
- Verify managed login, saved-record compatibility, account isolation, coach
  feedback and expiry against the private staging Tracker. Do not modify the
  stable student deployment or copy student data for testing.
- Configure and test supported subscription, payment-failure and refund events
  before releasing those flows; the existing endpoint currently only receives
  checkout.session.completed.
- Review privacy notice/consent, enable hosted intake/booking deliberately and
  validate a paid slot reservation, preparation form, confirmation and reminder.
- Calendar conflict synchronization and automatic meeting-link creation remain
  unimplemented. Live billing and public website release remain gated.

Historical deployment guides and older dated checkpoints describe earlier
states. This file records the newer observed hosted evidence and distinguishes
completed preparation from cloud setup that has not yet run.

## Afternoon connection checkpoint — 28 October 2026

The owner ran connect_jobs.py successfully. It reported Connected and sent=0;
there was no pending outbox work. A subsequent activation request through the
actual hosted portal produced a new outbox item that reached sent five seconds
after creation, without a manual worker request. This validates the event-driven
runtime queue/worker path. Actual Scheduler execution remains to be inspected.

Streamlit management confirms may-bloom-lab uses development/next and staging.app.py.
Its Secrets editor is empty. After waking, the app explicitly stops with the
independent test/production spreadsheet identifier requirement. No settings were
saved. The stable student app remains on its existing branch.

prepare_tracker.py consolidates the owner-only setup: sandbox preflight, a
dedicated staging Sheets service account (no project role grants), a reusable
Secret Manager service-account key, a separate reusable staging coach password,
and a 0600 local TOML file using the existing member-service bridge secret. It
requires distinct --test-sheet and --production-sheet arguments; production ID
is only an isolation guard. It does not share a Sheet, modify Streamlit or print
private credentials. Run --apply only in the owner's Cloud Shell, download the
private output and paste it only into may-bloom-lab Secrets. Never upload it to
chat, GitHub or a shared folder. New credential entry remains an owner step.

Share only the independent test Sheet with the printed service-account address,
as Editor, before testing managed login and record/coach flows. Do not reuse the
student service-account key or copy student data. Keep the downloaded private
file safely and remove the temporary Cloud Shell file after successful setup.
Five additional standard-library synthetic tests cover isolation, TOML encoding,
private file permissions, reuse and secret-free command arguments/errors.
