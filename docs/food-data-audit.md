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
