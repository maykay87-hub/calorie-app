# May Bloom UI refinement · Taste Skill v2

## Brief and method

Use the project's original Streamlit stack, pink May Bloom identity, teal profile
and calorie-first interaction. The main question is: what have I recorded today,
and how much remains against my saved target? The most frequent action is adding
a meal; exercise and history remain sibling tabs. Do not add marketing sections,
photo-recognition promises or more fields to make the screen look substantial.

Official skill installed locally at `.agents/skills/design-taste-frontend` from
Leonxlnx/taste-skill, commit b9ca2fd8047f4c72d7da90ebc1c1203e57c72cd2, with MIT licence.
Read SKILL.md and its complete app-screens.md before editing.
The app draw offered achromatic-ledger and editorial-greeting; chose
**editorial-greeting**, seed **20261020**, with palette and typography kept.
No redraw. A monochrome ledger would contradict the user's explicit colour brief.

## Product inventory and first-screen decisions

- Student profiles belong to a coach-provided account, with saved height, weight,
  activity and a calculated calorie target, not a fabricated goal.
- Meals use real saved catalogue identities and portion units; total kcal comes
  from the current day's rows. Existing nutrient snapshots are preserved.
- Exercise contributes its actual calculated kcal; net = food minus exercise.
- Remaining = saved target minus net. Pending unknown food remains explicitly
  provisional; an unavailable profile never produces a fabricated target.
- Food Intake, Exercise Burn and Net Calories retain their established peach,
  green and rose identities. The main Remaining figure is visually dominant.
- Profile remains recognisably separate on a pale teal surface.
- Malaysian meals and bilingual labels remain in the simple meal-entry row.
- Optional remarks and attachments stay collapsed; they are not removed.
- Human reviews keep their publication dates and previous supplements.
- Small and empty accounts display their real zeros; no invented streaks,
  progress, clients or success statistics are added.

Face: a drawn pink bloom wordmark on a blush-white ground. Signature element:
the three calorie figures and a clearly labelled energy balance, computed from
the same data. The skill's keyword match suggested a solar-power flow; rejected
as unrelated to this product and used the existing calorie relationship instead.

## Implementation

- Shared CSS moved to assets/may_bloom.css. The runtime does not load the skill.
- A consistent pink bloom mark and two-line brand lockup replace the oversized
  emoji title. May Bloom remains large and pink as specifically requested.
- Sign-in, students, the coach dashboard and public demo share the presentation
  layer. Sign-in retains its actual credential form and has less duplicate text.
- One 16px panel gap, 20px panel radius, 12px control radius and 44–48px touch
  targets. Desktop canvas maximum 1180px with equal 40px inner gutters.
- Calorie figures use tabular numerals, calmer weights and consistent units.
  Remaining has the largest data figure, not a small grey caption.
- Progress shows actual net and target labels; values use the same data as cards.
- White form controls have clear boundaries; profile focus uses teal, main focus
  uses rose. Keyboard focus stays visible. Disabled buttons remain readable.
- Primary form submits use the verified Streamlit `primaryFormSubmit` kind;
  secondary update/delete buttons do not all become filled pink buttons.
- Phone rules keep three compact peer figures, stack form inputs, allow tabs to
  scroll within their track, and let the Remaining label wrap below its number.
- Tablet rules provide a separate two-column form band, rather than squeezing
  the entire desktop entry row beside a sidebar.
- Hover is subtle feedback only; reduced-motion disables transitions.

Brand exceptions to the skill's default restraint: large pink wordmark, pale teal
profile with teal Save profile, three semantic calorie surfaces, existing familiar
tab/section symbols and successful-save balloons. These follow explicit client
requests. No marketing animation, photo quota or stock illustrations added.

## Verification and honest limits

Before screenshot: may-bloom-taste-before.jpg captured from the actual public demo.
All 145 application checks pass on the 2026-10-20 recheck (37.165 seconds), no failures or skips, including
saved records, profile, exercise, undo, provisional Remaining, remarks/attachments,
dated reviews and demo isolation. CSS lint: 0 FAIL, 0 WARN.
Measured CSS palette pairs meet 4.5:1 for primary buttons, body and secondary
text, teal profile text, amber provisional text and the food/exercise labels.
These pair checks are not a claim of full browser accessibility certification.

The bundled inspector cannot be used with this session's browser controls;
local-file preview navigation is blocked by the cloud browser URL policy.
It was not bypassed. No 1440/768/390 screenshot pass, browser score or completed
after-critique is claimed. Same-CSS design fixtures are internal samples only,
not proof that actual Streamlit controls render correctly at those widths.

Latest visual changes must be confirmed on the actual test deployment before
replacing production. Keep the draft PR and original app functions. Website and
production main remain unchanged; no real student data was edited for this UI work.

## Comparison and final recommendation

| Area | Before | Applied refinement |
| --- | --- | --- |
| Brand | Long single-line emoji heading competes with content | Drawn pink bloom, clear May Bloom name and smaller Lifestyle Tracker subtitle |
| Data hierarchy | Similar-size calorie figures; Remaining visually quieter | Largest data number is Remaining, units quieter, tabular digits throughout |
| Profile | Separate tint but inconsistent primary-button colour | Teal profile background, fields, focus and Save profile form one coherent area |
| Forms | Blush field fills; primary and secondary submits can share the same styling | White labelled controls with visible boundaries; explicit primary-only filled actions |
| Progress | Unlabelled bar | Current net and saved target label both ends; calculations unchanged |
| Spacing | Mixed corner radii and context-specific gaps | Repeated 16px gaps and equal canvas gutters, consistent panel and control radii |
| Sign-in and coach | Presentation applied only after the student auth branch | Shared style applied before sign-in and coach rendering |
| Phone/tablet | Desktop form mostly scaled or stacked | Separate tablet band, thumb-sized phone controls, contained tab scrolling |

Recommend this branded, calm editorial direction as the candidate for final sign-off.
Do not introduce all-black minimalism, photo-heavy marketing blocks, extra nutritional
forms, decorative score cards or more tutorial text. Keep optional detail behind
the existing disclosures. Any further changes should come from a visible rendering
or interaction problem, rather than another round of arbitrary recolouring.

An in-conversation, interactive before/proposed comparison uses illustrative
session data. It is a design demonstration, not a screenshot or proof of live
deployment. The 38 upstream files were rechecked by Git blob hash: none missing
or modified; LICENSE and UPSTREAM.md are the two project installation additions.
