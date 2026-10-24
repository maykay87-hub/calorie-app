# May Bloom calorie-first revision

The owner's original design and direct feedback are the primary reference.
Keep daily calorie balance prominent; do not require students to understand food
provenance or enter package nutrients before they can log a meal.

Primary path: date, calorie summary, one-row food form, Add Meal, Save.
Profile settings have a separate teal background. Rose remains the brand colour.

Official flow references consulted on 19 October 2026:
- MyFitnessPal food logging: https://support.myfitnesspal.com/hc/en-us/articles/360032274592-How-to-log-food-to-your-diary
- MyFitnessPal Today summary: https://support.myfitnesspal.com/hc/en-us/articles/39985611667341-Your-Today-tab
- MyFitnessPal website diary: https://support.myfitnesspal.com/hc/en-us/articles/360032624391-How-do-I-get-started-using-the-website
- Cronometer quick logging: https://cronometer.com/blog/log-food-fast/

These references inform the hierarchy and disclosure of optional functions.
No third-party interface, graphics or product claims are copied.

Static HTML reviews are a design reference, not the production Streamlit renderer.
Desktop has the four input/actions in one row; mobile stacks them vertically.
The actual code uses the same card, remaining-panel and brand styles from tracker_ui.py.
