# May Bloom V1.0 release preparation — 2026-10-20

## Fixed destinations and source

Student entry: https://calorie-app-pmjb9bbwfmikr8yqgicxdc.streamlit.app/

Public demo: https://calorie-app-pmjb9bbwfmikr8yqgicxdc.streamlit.app/?demo=1

Existing live channel: `tracker-v2/mobile-entry-session-fixes`, `advancedplus.app.py`.
Verified live source: `2b3e25f8d2973450284ded5d242c639920d8afd8`.
Snapshot ref: `release/v1.0-20261020`. Development branch: `development/next`.
The existing live channel stays in place to preserve the public URL. Branch
separation is a release process, not server-enforced GitHub branch protection.

## Current status

- Live demo, guide, positive/zero/over balance and Undo verified.
- 147 tests passed for the live source; the final guide formatting adjustment
  and development isolation code are on development only, not on the live app.
- Snapshot and development refs created after explicit GitHub authorization.
- Development isolation plus existing application checks: all 154 tests passed
  in 50.089 seconds, no failures or skips. The guard stops unconfigured staging
  before Google access; the staging demo remains independent of Google.
- A new cloud staging instance has not yet been deployed or configured.
- Database backup has not been verified; do not mark paid launch complete yet.
- Website is maintained/published in the existing Google AI Studio project;
  Cloudflare manages its domain. No domain or hosting migration is required.

## Separate staging setup

Create a separate Streamlit app using `development/next` and `staging.app.py`.
Keep it private. Use synthetic student accounts and synthetic records only.
Do not reuse the production account credential list.

Set these in that test app's Secrets (never commit actual values):

```toml
production_spreadsheet_id = "ID of the existing student database"
staging_spreadsheet_id = "ID of the independent empty test database"
```

Its `service_account` and `passwords` sections also need their own suitable
configuration. If an existing `spreadsheet_id` was copied from the student app,
the staging guard rejects using that same ID as the testing ID. The staging
entry point stops before opening Google if required separation is missing.
The student deployment keeps its existing explicit `spreadsheet_id` setting.

## Backup and recovery

Copy the entire existing spreadsheet, not just the first tab or feedback tab.
Suggested name: `wellness_database_backup_2026-10-20`. Keep existing access
restricted. Confirm all original tabs, headers and non-empty record counts are
present in the copy, including attachments, reviews and profiles.
Record the copy URL and time privately; do not put them in this repository.
The connected Drive service could not locate the known database at preparation
time, so this document does not claim a backup was made or validated.

Before a future release, keep a new backup and a tested compatibility plan for
any schema change. Validate with the staging database before publishing code.
For a code problem without a data change, publish a new commit restoring the
verified snapshot source rather than force-pushing a production branch. Do not
blindly restore old data: preserve newer records and reconcile them first.
Complete an isolated restore rehearsal before promising recovery capability.

## Baya handoff

Use the fixed student entry URL in the existing course, labelled
"进入生活记录 · Open Lifestyle Tracker". Keep the demo URL separate.
The student uses the username and password provided by May; the course link
alone does not create or activate an account. Opening Baya does not sign the
student into Streamlit automatically. No single sign-on is implemented.

Suggested member instructions:

> 点击「进入生活记录」，用 May 提供的账号登入。记录饮食与运动后按保存。
> May 的点评会显示在追踪器的反馈区，可回看以往点评。

The Baya course has not been edited or its live link validated in this preparation.

## Validated runtime record

The checked local runtime used Streamlit 1.66.0, pandas 2.2.3, gspread 6.2.1,
oauth2client 4.1.3. This records the tested environment; it does not change the
current live installation or claim a full dependency lock is already deployed.
