# May Bloom test release — consolidated acceptance

The test branch is `tracker-v2/mobile-entry-session-fixes`. Production main is unchanged.

## Automated checks

112 tests pass, including 29 real Streamlit AppTest scenarios.

Real Streamlit AppTest executes the complete application against in-memory Google Sheets doubles. It covers search changes, package-label input, missing values, serving and meal edits, individual deletion, shrinking entry lists, exercise duration edits, negative net energy, saving and fresh-session restore, separate date drafts, opening a day from history, logout and switching accounts, legacy replacement protection, failed-save retry, and profile failure/recovery and persistence. Pure unit tests separately verify per-record nutrient scaling, provenance, schema handling, empty gspread sheets, partial protein totals, latest-row history, and account/date separation.

## Ready for one combined live check

Use a test student account and a new test date. Search a local meal; confirm the displayed portion and whether protein is available. Add it and one exercise, edit a quantity, save, reopen and confirm the same details. Confirm profile values and inspect History. No real client records need to be edited.

## Boundaries

AppTest verifies Streamlit widget behavior and server logic; it does not verify the live deployment, actual Google credentials/permissions, or visual phone rendering. Food references are estimates for stated portions, not vendor-specific analyses. Shared catalogue has 131 selectable entries:57 complete Singapore HPB food references,36 visible KKM references (six with matched MyFCD macros), and 38 legacy exchange estimates awaiting source review. SG origins, source methods and portion units are explicitly labelled. Unknown macros remain unknown. Saved snapshots retain their original values.

Google Sheets has no transactional compare-and-swap: truly simultaneous sessions can still overwrite a row or duplicate an initial save. This release is a test version, not a claim that all clinical data and deployment conditions have been validated.

## Consolidated release improvements

History uses the latest saved row per account/date, retains old rows without
mutating the sheet, sorts dates and parses energy as numbers. Partial protein
appears as partial, and legacy summaries never become invented zero-protein days.
History can open a saved date while retaining other session drafts. Successful
saves invalidate the history cache. Connections are reused per sign-in for up to
five minutes; history is refreshed after save, manually, or after 60 seconds.
Logout clears cached connections along with account data. Default dates use
Asia/Kuala_Lumpur. Food edits support changing meal as well as quantity.
Failed-save messages preserve drafts and do not display raw server exceptions.
Retry after a lost write acknowledgement updates the existing row; this does not
provide transactional protection for genuinely simultaneous independent sessions.

## Personal package reuse and basic-food checks

New tests cover loading saved personal labels on a fresh sign-in, reusing them on
another date without re-entering nutrients, account isolation, latest-version
selection, malformed optional templates, bounded template count and searching a
personal label in the main food search. Nutrient provenance and unknown values
survive reuse. Volume-reference rendering is exercised in AppTest, and source
checks distinguish raw/cooked oats, ml versus g, and the explicitly edible 100 g
broccoli basis. This supplements the original consolidated check; a separate live
check is not required after each change.

Common drink variants now preserve recipe and published ml portions. A no-added-
sugar milk coffee retains its published energy/carbohydrate values. This release
adds 26 basic-food references and 12 drink references to the earlier 19-meal set.
Remaining missing macro data and unreviewed exchange estimates are still labelled.

## Recovery, stale-page guard and export

Every food/exercise add, edit, delete or clear records a bounded per-date,
per-account undo checkpoint. Undo remains available after clearing the last entry,
and after saving that clear; restoring entries becomes an unsaved change until
saved again. Undo stacks last only for this sign-in session and are not cloud
revision history.

Day loads retain a snapshot of user-owned fields. Save re-reads the latest row
and rejects a changed snapshot before writing, while allowing an identical retry
after a lost acknowledgement. Numeric display noise is normalized. Other accounts,
dates and coach-only columns do not form part of this day's stale-page comparison.
A detected conflict preserves the local draft, offers a structured JSON backup and
a saved-summary comparison, and disables saving until the user explicitly confirms
reloading the cloud record. Backups retain raw entries and provenance for keeping
or comparing the input; automatic JSON import is not part of this release.

This is optimistic checking, not an atomic transaction: two requests that both
read the old state before either writes can still race. Google Sheets remains a
limitation for simultaneous independent sessions.

Saved-history CSV exports only the signed-in account's latest records. Complete
protein, known protein and missing-item counts are separate columns; unavailable
values stay blank. UTF-8 BOM supports Chinese in Excel. Text cells that could be
interpreted as spreadsheet formulas are escaped; numeric negative net energy is
preserved. Download buttons do not rerun the form.

AppTest adds two independent page sessions to verify a stale save is blocked,
local entries remain and reloading requires confirmation. It also clears a saved
food list, saves the empty day, undoes the clear and saves/restores the recovered
entries. Exercise clear/undo is exercised separately. Unit tests verify bounded
undo isolation, snapshots, retry, old-summary conflicts and export contents.

## Flexible real-life amounts

Food servings accept direct numeric input starting at 0.01, with quarter-serving
steps as a convenience. Exercise minutes accept any positive whole minute; the
five-minute step does not restrict typed values. Defaults remain one serving and
30 minutes. A full AppTest records a quarter-serving meal and ten-minute exercise,
then saves and restores identical nutrient snapshots in a fresh session.

## Unsaved-date navigation

A collapsed list shows the signed-in account's loaded drafts that differ from
their saved snapshots, including a cleared saved day. Open another pending date
without losing the current draft. Saving or undoing back to the saved contents
removes that date from the list. Drafts remain session-only, not a replacement
for Save day. Tests cover account isolation and returning to a pending day,
saving it and removing its reminder.

## Coach view consistency

The existing admin account now selects one student at a time and shows only the
latest saved record per student/date, matching the student editor and history.
Saved-day counts exclude duplicate historical rows, invalid dates and admin test
records. Latest date is the greatest valid saved date, not the last physical row.
The overview reads the sheet once and does not modify any rows. Protein distinguishes
complete totals, partial known totals and unavailable values; legacy or malformed
details retain their text summaries. AppTest switches between two students and
checks that only the selected student's summary appears. Unit tests verify the
single read, latest-row rule, original-row preservation and partial protein.

## Confirmed profile before energy target

New accounts may record food/exercise immediately but have no energy target until
they confirm and save their profile. Default input values no longer produce an
apparently personalized target. Unsaved profile edits keep the target based on the
saved profile; a caption explains how to update it. A failed profile save preserves
the input fields and previous baseline. Existing daily records are not recalculated.
AppTest covers a new profile through first save, food entry before profile save,
and a weight change that updates the target only after successful profile save.

## Login and deployment handoff

Login is a bilingual Streamlit form, supporting keyboard submission. Trim only
outer username spaces; retain case and exact password matching. Failed credentials
remain signed out; successful sign-in removes login input credentials from session
state. Tests cover rejection, retry, credential cleanup and logout/account isolation.
The four runtime dependencies are present in requirements.txt.

The confirmed test URL is https://calorie-app-pmjb9bbwfmikr8yqgicxdc.streamlit.app/.
The protected revised desktop UI was checked after secure sign-in on 19 October:
saved profile 162 cm / 52 kg, target 1300 kcal; existing test day restored at
100 kcal with 1200 remaining. Food and exercise forms and saved-history chart
rendered. No new daily records or profile changes were written in this pass.

## Calorie-first interface revision (19 October)

This revision follows May's feedback that the earlier interface exposed too much
source and nutrient metadata and lost the original May Bloom visual hierarchy.
Restore the large rose title, coloured Food Intake / Exercise Burn / Net Calories
cards, remaining balance badge, Daily Energy Progress and large remaining-calorie
message. A teal-tinted profile sidebar distinguishes settings from daily logging.
Saved-profile boilerplate is removed; first-use/dirty/error guidance stays conditional.

The primary food path is Meal → Food Item → Servings → Add Meal in one desktop
row, stacking on mobile. The Food Item select box supports typing directly. Optional
alias search, categories, personal labels, custom labels, nutrients and provenance
remain under one closed More options expander. Student tables default to calories;
unknown nutrients and provenance remain intact in stored snapshots and coach tools.
History returns to Your Wellness History and the energy chart uses the brand rose.

New AppTests cover logging from the simple row without search/label input, preserved
nutrient data and a visible remaining-calorie panel. Unit checks cover remaining /
over-target wording and concise food labels. All existing save, restore, conflict,
undo, account-isolation and label workflows continue to pass.

The HTML files ui-review-desktop.html and ui-review-mobile.html are clearly marked
layout previews with sample values, not live account screenshots. Their main cards
reuse tracker_ui.py. Visual inspection of the static reviews is complete; the revised
protected desktop live UI has now been checked. A fresh phone viewport render check remains outstanding.

## Live progress colour correction

The live progressbar reported 7%, but the custom CSS coloured its entire track
rose. Keep the track neutral and apply rose only to its inner fill. This changes
presentation only; calories, targets, stored records and progress arithmetic stay
unchanged. Production main remains unchanged.

## Human reviews and isolated public demo

120 checks pass, including 32 full student/coach AppTest scenarios and one
public-demo AppTest. The coach can publish weekly/monthly text reviews from the
admin screen, with account selection, preserved input on failure, RAW writes,
append-only revisions, and serial identical-retry deduplication. Original
username/month/note headers remain compatible; unexpected schema is preserved
and rejected. Student reviews are account-scoped, sorted by recognized period,
and accessible from the main page with past periods and a refresh action.
There is no automated AI generation, unread receipt, entitlement or scheduling
engine. Dates for weekly/monthly service are managed by May.

The ?demo=1 route runs before credentials and worksheet access. It uses public
food reference values and labelled sample feedback, keeps entries in its own
session keys, and does not write real records. AppTest runs it without secrets,
with gspread authorization set to fail if called, and exercises add, sample
exercise, try-save and reset. Course wording, website connection instructions
and a 90-second demo script are in course-offer-and-demo.md. Website integration,
production merge, student free-text/attachments and AI photo detection are not
part of this published test-stage change.

## Short guide and non-replacing feedback timeline

122 checks pass. The short guide now includes Food Log, Exercise Log, Save and
Wellness History, plus one Remaining formula. Every feedback row is accessible,
including supplements for the same period; earlier notes are no longer collapsed
away. New coach publications append a Malaysia-time ISO timestamp in an optional
published_at column, added only when publishing. Existing rows/extra columns
are preserved; legacy records retain their period without fabricated timestamps.
Reviews sort by actual publication time where available. Student history selects
unique row keys, so same-period notes do not collide. Tests cover same-period
visibility, timestamps, late follow-ups, account isolation and schema preservation.
No live review was posted merely to test this change.
