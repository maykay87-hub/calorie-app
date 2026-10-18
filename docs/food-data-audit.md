# Food data audit — 18 October 2026

The original tracker contains 65 entries with no per-entry source URLs, measured portion weights, version or review date. Its numerical values are retained for historical compatibility, not relabeled as verified measurements.

## Findings

- Three vegetable entries assign zero energy and zero macronutrients without defining a portion. This may reflect an exchange-system convention, but does not describe actual composition. They are excluded from new selection pending review.
- Generic meal labels (e.g. one hawker nasi lemak) omit weight and recipe details. Source-backed variants now distinguish basic, packed, rendang, sambal sotong and spiced fried chicken nasi lemak.
- Protein portions and milk/oil/nut entries mix exchange estimates and named foods. They need per-entry portion/cooking/source review; the new records do not validate the remaining legacy estimates.
- Energy and macronutrients do not consistently align with a basic 4/4/9 calculation. This is a review flag, not an automatic correction rule, because source methods and rounding can differ.

## Added reference data

`data/foods_kkm.json` contains 46 manually transcribed records from KKM's *Bank Kalori Makanan dan Minuman di Malaysia*. Each records the exact published portion weight, energy, PDF page (1-based), original food name, and original reference code.

Source: https://hq.moh.gov.my/nutrition/wp-content/uploads/2025/10/Bank-Calorie-Bahagian-Pemakanan-merged.pdf

The URL's upload path is not treated as an edition date. Accessed 18 October 2026. Original reference codes are retained: MFC = Malaysian Food Composition; SFC = Singapore Food Composition; NP = Nutritionist Pro. KKM's compilation is not evidence that every row was measured in Malaysia or that a vendor's portion has the published composition.

This source provides energy, not macronutrient breakdowns. Protein, carbohydrate and fat are therefore null, never substituted with zero or inferred from generic recipes. The UI displays missing data as a dash, and the saved detailed entry includes a source snapshot.

## Selection and historical records

Seven legacy IDs with zero/ambiguous portions or directly superseded variants are excluded from new selection. They remain readable in historical logs. Other legacy estimates remain selectable with an explicit original-estimate notice. Saved calories are not recalculated from the current catalogue during restoration.

## Next data work

Use MyFCD (https://myfcd.moh.gov.my/) for complete per-100g composition and retain raw/cooked/preparation distinctions. Add branded label data only with product identity and label date. Extend coverage through source-reviewed batches, rather than treating a long unreviewed list as accurate.

Reference values are portion-specific estimates. Soup and dry versions must remain separate; neither the dry pan mee entry nor its aliases claim to describe chilli pan mee. User confirmation of food, preparation and portion remains necessary even if photo or barcode entry is added later.


## Macronutrient enrichment and editing (2026-10-18)

Six MFC-coded KKM preparations now have matched MyFCD 1997 protein, carbohydrate
and fat estimates: cooked white rice (101014), fried rice (221021), fried rice
noodles (221013), plain roti canai (221023), roti telur (221024), and plain chapati (221001).
The official per-100g values, food code, detail URL and access date are stored
per record in `macronutrient_source`. Match checks use preparation name and an
energy agreement within 2.5% after scaling to KKM weight; this tolerance is a
cross-check, not evidence that vendors use identical recipes. KKM energy remains
unchanged. Other new dishes retain unknown macros. Existing saved snapshots are
not retroactively enriched or recalculated.

The dashboard displays known protein and missing-entry counts; partial sums
are never labeled full-day totals. Original exchange estimates remain explicitly
unverified. Serving edits scale the saved snapshot, preserving unknown nutrients
and provenance. Deletion and edits require the user's normal Save action; status
compares the full draft against its last loaded/saved snapshot.


## Label fallback and search (2026-10-18)

Package-label entry supports per-serving, per-g and per-ml values. The label
basis and amount eaten use the same unit. Energy is required; optional protein,
carbohydrate and fat default to unknown, not zero. Entries snapshot the original
label values with a `user_entered_package_label` source status. They are personal
daily records, not verified additions to the shared food catalogue. Editing shows
actual g/ml, then scales from the stored snapshot. Existing logged food values
remain unchanged. No energy-from-macros assumption or vendor precision is added.

Chapati enrichment uses official MyFCD 1997 food code 221001: per100g, 300kcal,
protein9g, carbohydrate46.6g, fat8.6g. Both preparation and100g serving match the
KKM entry. Cucumber code105031 was inspected but NOT merged: its per100g energy
would imply21.76kcal for136g, differing from KKM15kcal, beyond the matching rule.

Phone search accepts reordered words, Unicode full-width characters and omitted
spaces. It does not invent an approximate substitute for an unmatched dish.

Validation includes real Streamlit AppTest runs with an in-memory Sheets double:
label add, validation failure, zero-amount edit rejection, quantity edit, deletion,
save and restoration in a fresh session, and changes between matching/unmatched
food searches. No credentials or live Sheets writes are used by these tests.


## HPB SG FoodID whole-meal reference update (2026-10-18)

Added19 complete meal records from the Singapore Health Promotion Board's public
SG FoodID search/details service. These include dry/soup wanton noodles, dry/soup
ban mian, chilli ban mian, prawn noodles, chicken rice, char kway teow, laksa,
mee goreng, mee soto and three nasi lemak sets. Each stores its food code, public
detail URL, original name, reference portion weight, edible portion percentage,
data year and source method. Sixteen are marked Lab Analysis by the source;
three2026 nasi lemak sets are marked Derived. Preserve these distinct methods.

Use the provider's published calculated default-portion values for ALL energy and
macros. Do not attach these macros to KKM energy or mix recipe definitions.
Validate per100g values against default weight times edible portion, allowing
rounding of the published base and portion values. This is important for meals
with bones/shells: multiplying gross weight by edible-basis values directly is
incorrect. Sources labelled Singapore remain visibly labelled SG reference and
are not represented as vendor-specific Malaysian analyses.

Eleven superseded selections (nine KKM references and two original estimates)
remain internally readable but are hidden from new selection. Original records
and saved snapshots are unchanged. The catalogue now contains130 stable IDs,
112 selectable entries:19 SG FoodID records,37 visible KKM records, and56 original
exchange estimates.25 visible references have source-backed full macros
(19 SG FoodID and6 matched KKM/MyFCD records).31 visible KKM references still have
unknown macros. Original exchange estimates remain under source review.

Official entrypoint: https://www.hpb.gov.sg/services/
Public tool: https://pphtpc.hpb.gov.sg/web/sgfoodid/tools/food-search
Record URLs are stored in data/foods_hpb_sg.json. Chinese preparation descriptions
are concise paraphrases, not claims of identical Malaysian stall recipes.
