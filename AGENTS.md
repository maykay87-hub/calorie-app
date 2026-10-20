# May Bloom release channels

The public student URL is deployed from `tracker-v2/mobile-entry-session-fixes`,
entry point `advancedplus.app.py`. Treat that branch as the stable student channel
from 2026-10-20 onward, regardless of its historical name. Do not rename it or
delete/redeploy the app merely for a prettier branch name; preserve the student URL.

- Everyday work goes to `development/next`. Its separate Streamlit test app must
  use `staging.app.py` and an independent test spreadsheet and test credentials.
- Never copy real student records into a test environment. Use synthetic records.
- Do not deploy `development/next` to the student app, or push development changes
  to the student channel without an explicitly requested, validated release.
- Before a student release: verify a complete database backup and recovery plan,
  run relevant checks including saved-record compatibility and account isolation,
  then record the exact source commit and preserve a release snapshot.
- `release/v1.0-20261020` records the verified live commit
  `2b3e25f8d2973450284ded5d242c639920d8afd8`. Do not move or force-push snapshot refs.
- Database restoration is separate from code rollback. Never overwrite current
  records from an older backup without checking records created after the backup
  and obtaining authorization for the specific restoration.
- Never publish credentials, database IDs, real student records, attachments or
  internal account-testing details in commits or pull-request descriptions.
- Demo sessions never connect to Google Sheets. Preserve that boundary.
