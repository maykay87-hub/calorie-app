# May Bloom test release — consolidated acceptance

The test branch is tracker-v2/mobile-entry-session-fixes. Production main is unchanged.

## Automated checks

73 tests pass, including 14 real Streamlit AppTest scenarios.

Real Streamlit AppTest executes the complete application against in-memory Google Sheets doubles. It covers search changes, package-label input, missing values, serving and meal edits, individual deletion, shrinking entry lists, exercise duration edits, negative net energy, saving and fresh-session restore, separate date drafts, opening a day from history, logout and switching accounts, legacy replacement protection, failed-save retry, and profile failure/recovery and persistence. Pure unit tests separately verify per-record nutrient scaling, provenance, schema handling, empty gspread sheets, partial protein totals, latest-row history, and account/date separation.

## Ready for one combined live check

Use a test student account and a new test date. Search a local meal; confirm the displayed portion and whether protein is available. Add it and one exercise, edit a quantity, save, reopen and confirm the same details. Confirm profile values and inspect History. No real client records need to be edited.

## Boundaries

AppTest verifies Streamlit widget behavior and server logic; it does not verify the live deployment, actual Google credentials/permissions, or visual phone rendering. Food references are estimates for stated portions, not vendor-specific analyses. Shared catalogue has112 selectable entries:19 complete Singapore HPB meal references,37 visible KKM references (six with matched MyFCD macros), and56 legacy exchange estimates awaiting source review. SG recipes and weights are explicitly labelled. Unknown macros remain unknown. Saved snapshots retain their original values.

Google Sheets has no transactional compare-and-swap: truly simultaneous sessions can still overwrite a row or duplicate an initial save. This release is a test version, not a claim that all clinical data and deployment conditions have been validated.

## Consolidated release improvements

History uses the latest saved row per account/date, retains old rows without
mutating the sheet, sorts dates and parses energy as numbers. Partial protein
appears as partial, and legacy summaries never become invented zero-protein days.
History can open a saved date while retaining other session drafts. Successful
saves invalidate the history cache. Connections are reused per sign-in for up to
five minutes; history is refreshed after save, manually, or after60seconds.
Logout clears cached connections along with account data. Default dates use
Asia/Kuala_Lumpur. Food edits support changing meal as well as quantity.
Failed-save messages preserve drafts and do not display raw server exceptions.
Retry after a lost write acknowledgement updates the existing row; this does not
provide transactional protection for genuinely simultaneous independent sessions.
