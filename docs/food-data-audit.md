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


## Basic foods and personal package reuse (2026-10-18)

Add26 HPB reference records across grains/starches, protein foods, dairy, fruit,
vegetables and nuts. They cover white/wholemeal bread and wraps, cooked rice,
dry/cooked oats, milk/yoghurt, tofu, fried tau kwa, baked chicken breast, boiled
egg, fruit and unsalted baked almonds. Preserve the source method: at this checkpoint the45
HPB records comprised17 Lab Analysis,17 Borrowed,7 Derived and4 NIP. A record
listed in SG FoodID is not automatically a laboratory measurement in Singapore.

Use published default portions for25 of these26 additions. Their nutrient values
already account for the provider's edible-portion percentage. Labels explicitly
identify gross reference weights for peel/shell/bone where needed. Milk keeps its
published250ml glass and volume basis: `weight_g` is null rather than silently
assigning250g. Save volume metadata in the provenance snapshot.

Boiled broccoli is the exception: use its published100g edible-basis values,
explicitly labelled edible100g, rather than presenting the provider's100g gross
cup with a60% edible factor as100g eaten. Store the original provider portion
and edible percentage alongside `portion_basis=edible_100g` for audit. The new
references use neither an invented household weight nor a borrowed macro value
attached to a different source's energy.

Counts after the basic-food batch:156 stable IDs,123 selectable entries.82 selectable
entries are source-backed references (45 SG FoodID,37 KKM);51 have full referenced
macros (45 SG FoodID plus6 KKM/MyFCD).31 KKM entries still lack macros;41 original
exchange estimates remain selectable and marked as under review.15 superseded
basic-food selections are retained for old snapshots but hidden from new choices.

Personal package templates are derived only from that account's saved detailed
food rows, using the latest row per date. They use the original label basis and
values, not a scaled amount from a previous meal. Same-name/unit/basis templates
prefer the latest consumption date; distinct flavours remain distinct. A bounded
30-item sign-in list includes newly entered labels, while saving the day makes
them available on a new sign-in. No separate worksheet or shared food catalogue
is modified. Daily snapshots stay unchanged when a personal template is updated.

Personal labels can be reused from My label foods or searched in the normal food
search. Their source remains user_entered_package_label, including unknown macros;
it is never relabelled as a verified reference or an original exchange estimate.
The runtime search dictionary is per Streamlit session/run. Logout clears it with
the account state. History scan failures do not stop ordinary daily tracking.


## Beverage variants and latest consolidated counts (2026-10-18)

Add12 published HPB beverage references: Teh Tarik, Kopi, Kopi C, Kopi O, two
kosong variants, hot/iced/less-sweet Milo, and regular/less-sugar/no-added-sugar
soy milk. Keep the stated recipe and volume together: small Teh Tarik is150ml,
hot Milo250ml, iced Milo400ml, and these soy-drink references450ml. These are
source examples, not universal Malaysian cup sizes. Recipe names that say no
added sugar are not converted to zero-energy or zero-carbohydrate records.
The per-serving values are copied from the same provider record; their source
methods, including Derived, remain visible rather than being labelled measured.

The complete HPB set now has57 records:18 Lab Analysis,18 Derived,17 Borrowed,
and4 NIP. Latest catalogue:168 stable IDs,131 selectable items, including93
source-backed references (57 HPB,36 KKM).63 visible references contain complete
energy/protein/carbohydrate/fat data;30 KKM items still lack macros and38 original
exchange estimates remain marked under review. The legacy Teh Tarik KKM option
and three superseded original drink estimates are hidden, not deleted.

Validation:86 tests pass, including18 real Streamlit AppTest scenarios. Beverage
checks distinguish volumes and recipe variants and preserve energy in a no-added-
sugar milk-coffee example. All three main nutrition values retain unknown versus
zero semantics through logging, editing, personal-label reuse and save/restore.
