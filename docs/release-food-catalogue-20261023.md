# Food catalogue release — 23 October 2026

Food-only source: `be17caa68988663cb121b1839e9acb02e73f886f`, scoped onto the original stable student code `2b3e25f8d2973450284ded5d242c639920d8afd8`. Original sign-in, spreadsheet configuration, profiles, reviews, notes and attachment flows are preserved. No payment/member automation is included.

The shared demo/student catalogue offers 250 selectable food/portion records (270 including historical IDs). This expansion adds 39 official MyFCD ingredient records and 54 source-labelled teaching exchanges. Names/portions are not a count of unique food species. Source dates, original headings, edible-weight scaling, raw-basis interpretation, skin uncertainty and unknown nutrients are retained. Atlas cup measures remain distinct from milk volume.

Validation: the isolated stable candidate passed 157 tests and 229 subtests. Eight focused exchange/composition checks passed again after the final raw-poultry option was added. Synthetic tests cover composition, saved-record round trips, undo, unit/source distinctions, account isolation and demo separation. The development suite separately passed 228 tests and 229 subtests before the final additive raw option.

Before release, a full copy of the active student workbook was created in the owner's Drive. All populated cells across its five tabs matched, and the copy has owner-only access. Backup locations and database IDs are private. No student spreadsheet cells were changed by this code release.

Recovery: `release/pre-food-expansion-20261023` preserves the previous student source. For a code problem, publish a new commit restoring that source; do not force-push or restore an older database over newer records. This release changes catalogue code/data only and requires no database migration.

The runtime update must be observed on the existing Streamlit student URL after the stable ref changes. A successful Git push alone does not prove the hosted runtime has updated or that the separate payment automation is live.
