"""Meal composition, original portions, and source boundaries."""
import unittest
from food_database import build_food_database
from food_catalogue import filter_foods, food_picker_label, BUILD_MEAL, READY_MEALS
from nutrition_registry import make_food_entry
from tracker_storage import save_day, load_day, HEADERS
from test_tracker_storage import Sheet


class ExchangeFoodTests(unittest.TestCase):
    def test_rice_meat_plain_vegetables_and_oil_combine_and_round_trip(self):
        database = build_food_database()
        keys = ['Rice (1/2 cup)',
                'Chicken Thigh Meat (30 g cooked, skinless, boneless; exchange)',
                'Broccoli Boiled Edible (100 g edible portion, 100 g; HPB SG reference)',
                'Cooking Oil (1 tsp)']
        choices = filter_foods(database, mode=BUILD_MEAL)
        for key in keys:
            self.assertIn(key, choices)
        entries = [make_food_entry(database, key, 'Lunch', qty)
                   for key, qty in zip(keys, [2, 2, 1, 1])]
        self.assertEqual(sum(item['Calories'] for item in entries), 360)
        self.assertEqual(entries[-1]['Fat'], 5)
        self.assertEqual(entries[-1]['Source']['weight_g_per_serving'], 5)
        sheet = Sheet([HEADERS])
        save_day(sheet, 'student', '2026-10-23', entries, [], 360, 'composed meal', 'None')
        self.assertEqual(load_day(sheet, 'student', '2026-10-23')['food_log'], entries)

    def test_chicken_cuts_use_edible_weight_not_whole_piece_claims(self):
        database = build_food_database()
        for name in ['drumstick', 'thigh', 'wing']:
            choices = filter_foods(database, query='chicken '+name)
            key = next(k for k in choices if '; exchange)' in k)
            self.assertIn('30g', food_picker_label(key))
            self.assertIn('去皮去骨', food_picker_label(key))
            item = make_food_entry(database, key, 'Dinner', 2)
            self.assertEqual((item['Calories'], item['Protein'], item['Fat']), (130, 14, 8))
            self.assertEqual(item['Source']['basis'], 'generic_poultry_exchange')

    def test_original_portions_and_ready_meals_both_remain_available(self):
        database = build_food_database()
        for key, kcal in [('Rice (1/2 cup)',75), ('Egg (1 whole)',65),
                         ('Cooking Oil (1 tsp)',45), ('Chicken Drumstick (1 piece)',130)]:
            self.assertIn(key, filter_foods(database))
            self.assertEqual(database[key]['Cals'], kcal)
        oil = filter_foods(database, query='食油')
        self.assertIn('Cooking Oil (1 tsp)', oil)
        self.assertIn('5g', food_picker_label('Cooking Oil (1 tsp)'))
        ready = filter_foods(database, mode=READY_MEALS)
        self.assertTrue(any('Wantan Mee Dry' in k for k in ready))
        self.assertNotIn('Cooking Oil (1 tsp)', ready)
        self.assertFalse(filter_foods(database, query='chicken rice', mode=BUILD_MEAL))
        vegetables = filter_foods(database, query='蔬菜', mode=BUILD_MEAL)
        self.assertTrue(any(key.startswith('Broccoli Boiled Edible') for key in vegetables))
        self.assertNotIn('Ulam (Cucumber/Raw Greens)', filter_foods(database))
        # References remain available alongside original teaching portions.
        self.assertTrue(any('White Rice Cooked (' in k for k in filter_foods(database)))

    def test_new_catalogue_instances_do_not_share_personal_food_mutations(self):
        first = build_food_database()
        first['Cooking Oil (1 tsp)']['Cals'] = 999
        first['Private package'] = {}
        second = build_food_database()
        self.assertEqual(second['Cooking Oil (1 tsp)']['Cals'], 45)
        self.assertNotIn('Private package', second)
