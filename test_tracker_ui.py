import unittest
from tracker_ui import calorie_summary, remaining_panel
from food_catalogue import food_picker_label
from nutrition_registry import REFERENCE_RECORDS


class CaloriePresentationTests(unittest.TestCase):
    def test_remaining_and_over_target_are_distinct_without_changing_values(self):
        self.assertIn('613 left', calorie_summary(880, 0, 880, 613))
        self.assertIn('613', remaining_panel(613))
        self.assertIn('kcal remaining', remaining_panel(613))
        self.assertIn('20 over', calorie_summary(1513, 0, 1513, -20))
        self.assertIn('above target', remaining_panel(-20))
        self.assertNotIn('left', calorie_summary(0, 0, 0, None))

    def test_picker_keeps_dish_and_portion_without_source_metadata(self):
        key = next(k for k,v in REFERENCE_RECORDS.items() if v.get('source_id')=='hpb_sgfoodid')
        label = food_picker_label(key)
        self.assertIn(REFERENCE_RECORDS[key]['zh'], label)
        self.assertNotIn('SG参考', label)
        self.assertNotIn('HPB', label)

    def test_zero_balance_and_float_noise_show_at_target_without_over_warning(self):
        for value in (0, 0.0000001, -0.0000001):
            panel = remaining_panel(value)
            self.assertIn('已达到今日目标', panel)
            self.assertNotIn('above target', panel)
            badge = calorie_summary(1500, 0, 1500, value)
            self.assertIn('At target', badge)
            self.assertNotIn('0 over', badge)
        self.assertIn('above target', remaining_panel(-0.1))

    def test_incomplete_zero_balance_does_not_claim_target_was_reached(self):
        panel = remaining_panel(0, provisional=True)
        self.assertIn('暂估余额', panel)
        self.assertNotIn('已达到', panel)
        self.assertNotIn('at target', panel)

    def test_provisional_remaining_is_visible_and_never_a_complete_green_check(self):
        panel = remaining_panel(613, provisional=True)
        self.assertIn('613', panel)
        self.assertIn('暂估剩余', panel)
        self.assertIn('provisional', panel)
        self.assertNotIn('✓', panel)
        self.assertIn('暂估高于目标', remaining_panel(-20, provisional=True))
