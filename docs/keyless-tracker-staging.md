# Optional keyless Tracker test deployment

Status: implemented and locally tested, not deployed. The existing Streamlit
test and stable student apps remain on their existing hosting and branches.

The owner Cloud project reports KEY_CREATION_BLOCKED_BY_POLICY when creating a
new service-account JSON key. Do not disable that policy or reuse the student
credential. Google Cloud Run can supply short-lived Application Default
Credentials for its attached service identity instead.

The opt-in `google_sheets.use_runtime_identity=true` setting is accepted only
under the staging entry point in Cloud Run. An explicit external credential
file is rejected. Legacy production authentication and its existing scopes are
preserved. Demo mode still stops before secrets or Sheets access.

`Dockerfile.tracker-staging` builds this separate app, serving staging.app.py
on PORT (8080 by default). It needs a private Streamlit TOML configuration from
Secret Manager, the existing private member bridge, and an independent test
spreadsheet. The production spreadsheet identifier is only an isolation guard.
No Google private key is needed or copied into the container.

The owner-run deploy_tracker_keyless.py helper on the membership feature branch
is preparation for review. It defaults to read-only preflight. Its --apply
creates a separate Cloud Run service named maybloom-tracker-staging, a versioned
configuration secret and a secret-scoped accessor permission for its dedicated
runtime identity. The service exposes the login/demo page publicly; actual
records require member or coach authentication. The dedicated identity must be
shared on only the approved test Sheet as Editor. The stable app is not touched,
and MB_TRACKER_URL is not changed until hosted acceptance passes.

Cost controls are request billing, minimum zero instances and maximum one
instance. Builds, image storage, requests and long-lived Streamlit WebSocket
connections can incur charges. This is not a promise of a free service. The
owner must approve the additional usage-billed test hosting before deployment.

Local validation covers runtime/scopes selection, refusal in production or
outside Cloud Run, the unchanged legacy path, test Sheet isolation, a real
Streamlit managed-login flow against synthetic providers, demo safety and
existing member/record flows. Actual Cloud Run identity/scopes, Sheet access,
browser login, records, coach review, restart and expiry remain hosted checks.

References checked 28 October 2026:
- https://docs.gspread.org/en/master/oauth2.html
- https://docs.cloud.google.com/run/docs/securing/service-identity
- https://codelabs.developers.google.com/codelabs/cloud-run/local-testing-cloud-run-google-sheets-adk-agent
