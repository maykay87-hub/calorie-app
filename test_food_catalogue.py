import ast
import copy
from pathlib import Path
import unittest
from nutrition_registry import REFERENCE_RECORDS, reference_database
from food_catalogue import (ALL_FOODS, RECENT_FOODS, CATEGORIES, FOOD_META,
                            food_label, filter_foods, remember_food)


def existing_database():
    tree = ast.parse(Path(__file__).with_name("advancedplus.app.py").read_text())
    node = next(node for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "food_database"
                        for target in node.targets))
    database = ast.literal_eval(node.value)
    database.update(reference_database())
    return database


class FoodCatalogueTests(unittest.TestCase):
    def setUp(self):
        self.database = existing_database()

    def test_every_existing_food_has_a_label_and_one_known_category(self):
        self.assertEqual(set(self.database), set(FOOD_META))
        for key in self.database:
            if key in REFERENCE_RECORDS:
                self.assertIn(REFERENCE_RECORDS[key]["zh"], food_label(key))
            else:
                self.assertIn(key, food_label(key))
            self.assertIn(FOOD_META[key][1], CATEGORIES)

    def test_search_supports_chinese_and_case_insensitive_english(self):
        self.assertIn("White Rice Cooked (1 bowl, 200 g; HPB SG reference)", filter_foods(self.database, query="白饭"))
        self.assertIn("White Rice Cooked (1 bowl, 200 g; HPB SG reference)", filter_foods(self.database, query=" RICE "))
        self.assertEqual(filter_foods(self.database, query="not-a-food"), [])

    def test_typed_food_search_works_across_any_browse_category(self):
        fruit = next(category for category in CATEGORIES if "Fruit" in category)
        self.assertTrue(any('Apple Red' in key for key in filter_foods(self.database, fruit)))
        self.assertIn("White Rice Cooked (1 bowl, 200 g; HPB SG reference)", filter_foods(self.database, fruit, "Rice"))
        grains = CATEGORIES[0]
        self.assertIn("Nasi Lemak Basic (1 plate, 230 g; KKM reference)", filter_foods(self.database, grains, "Nasi lemak"))
        self.assertIn("Nasi Lemak Basic (1 plate, 230 g; KKM reference)", filter_foods(self.database, RECENT_FOODS, "nasi lemak", recent=[]))

    def test_local_names_aliases_and_spacing(self):
        self.assertIn("Chicken Rice Roasted (1 plate, 363 g; HPB SG reference)", filter_foods(self.database, query="nasi ayam"))
        self.assertIn("Chicken Rice Roasted (1 plate, 363 g; HPB SG reference)", filter_foods(self.database, query="鸡饭"))
        self.assertIn("Nasi Lemak Basic (1 plate, 230 g; KKM reference)", filter_foods(self.database, query=" NASI   LEMAK "))
        self.assertIn("Char Kway Teow (1 plate, 480 g; HPB SG reference)", filter_foods(self.database, query="char kway teow"))

    def test_recent_is_unique_bounded_and_excludes_unknown_foods(self):
        original = ["Egg (1 whole)", "Rice (1/2 cup)"]
        self.assertEqual(remember_food(original, "Rice (1/2 cup)"),
                         ["Rice (1/2 cup)", "Egg (1 whole)"])
        self.assertEqual(original, ["Egg (1 whole)", "Rice (1/2 cup)"])
        self.assertEqual(len(remember_food(list(self.database), "new", limit=8)), 8)
        self.assertEqual(filter_foods(self.database, RECENT_FOODS,
                                     recent=["unknown", "Egg (1 whole)", "Egg (1 whole)"]), [])
        current_egg = next(key for key in self.database if key.startswith('Chicken Egg Hard Boiled ('))
        self.assertEqual(filter_foods(self.database, RECENT_FOODS, recent=[current_egg, current_egg]), [current_egg])

    def test_phone_search_accepts_reordered_words_and_missing_spaces(self):
        nasi = "Nasi Lemak Basic (1 plate, 230 g; KKM reference)"
        dry = "Wantan Mee Dry (1 bowl, 388 g; HPB SG reference)"
        for query in ["nasilemak", "ＮＡＳＩ　ＬＥＭＡＫ", "lemak nasi"]:
            self.assertIn(nasi, filter_foods(self.database, query=query))
        self.assertIn(dry, filter_foods(self.database, query="dry wantan"))
        self.assertNotIn(dry, filter_foods(self.database, query="soup wantan"))
        self.assertEqual(filter_foods(self.database, query="unicorn noodle"), [])

    def test_filters_preserve_stable_ids_and_nutrition_values(self):
        original = copy.deepcopy(self.database)
        for category in [ALL_FOODS, RECENT_FOODS] + CATEGORIES:
            keys = filter_foods(self.database, category, recent=list(self.database)[:8])
            for key in keys:
                self.assertEqual(self.database[key], original[key])
        self.assertEqual(self.database, original)
        self.assertEqual(self.database["Rice (1/2 cup)"]["Cals"], 75)
        self.assertEqual(food_label("New food"), "New food")


if __name__ == "__main__":
    unittest.main()
