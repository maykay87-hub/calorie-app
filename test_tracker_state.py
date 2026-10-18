import unittest
from tracker_state import logout, select_draft, daily_signature, change_entries, undo_entries


class DraftIsolationTests(unittest.TestCase):
    def test_delete_clear_and_edit_can_be_undone_without_losing_list_alias(self):
        state = {}
        draft = select_draft(state, 'student', '2026-10-18')
        change_entries(draft, 'food', [{'Food': 'Rice', 'Source': {'status': 'original'}}])
        alias = state['food_log']
        change_entries(draft, 'food', [])
        self.assertTrue(undo_entries(draft, 'food'))
        self.assertIs(state['food_log'], alias)
        self.assertEqual(state['food_log'][0]['Food'], 'Rice')
        change_entries(draft, 'food', [{'Food': 'Bread'}])
        undo_entries(draft, 'food')
        self.assertEqual(state['food_log'][0]['Source']['status'], 'original')

    def test_undo_is_bounded_and_separate_by_day_account_and_entry_kind(self):
        state = {}
        draft = select_draft(state, 'alice', '2026-10-18')
        for i in range(25):
            change_entries(draft, 'food', [{'amount': i}])
        self.assertEqual(len(draft['food_undo']), 20)
        self.assertFalse(undo_entries(draft, 'exercise'))
        other = select_draft(state, 'alice', '2026-10-19')
        self.assertFalse(undo_entries(other, 'food'))
        other_user = select_draft(state, 'bob', '2026-10-18')
        self.assertFalse(undo_entries(other_user, 'food'))
        self.assertEqual(len(draft['food_undo']), 20)

    def test_save_status_tracks_edits_deletions_and_unknown_nutrients(self):
        food = [{"Qty": 1, "Protein": None, "Calories": 100}]
        saved = daily_signature(food, [])
        self.assertEqual(saved, daily_signature([dict(reversed(list(food[0].items())))], []))
        food[0]["Protein"] = 0
        self.assertNotEqual(saved, daily_signature(food, []))
        food[0]["Protein"] = None
        self.assertEqual(saved, daily_signature(food, []))
        self.assertNotEqual(saved, daily_signature([], []))
        self.assertNotEqual(saved, daily_signature(food, [{"Activity": "Walk"}]))

    def test_date_switch_preserves_each_days_food_and_exercise(self):
        state = {}
        select_draft(state, "student", "2026-10-17")
        state["food_log"].append({"Food": "Rice"})
        state["exercise_log"].append({"Activity": "Walking"})
        select_draft(state, "student", "2026-10-18")
        self.assertEqual(state["food_log"], [])
        self.assertEqual(state["exercise_log"], [])
        select_draft(state, "student", "2026-10-17")
        self.assertEqual(state["food_log"], [{"Food": "Rice"}])
        self.assertEqual(state["exercise_log"], [{"Activity": "Walking"}])

    def test_accounts_have_separate_drafts_on_same_date(self):
        state = {}
        select_draft(state, "student_a", "2026-10-17")
        state["food_log"].append({"Food": "Rice"})
        select_draft(state, "student_b", "2026-10-17")
        self.assertEqual(state["food_log"], [])

    def test_clear_only_affects_selected_day(self):
        state = {}
        select_draft(state, "student", "2026-10-17")
        state["food_log"].append({"Food": "Rice"})
        select_draft(state, "student", "2026-10-18")
        state["food_log"].clear()
        select_draft(state, "student", "2026-10-17")
        self.assertEqual(len(state["food_log"]), 1)

    def test_logout_removes_credentials_and_previous_clients_data(self):
        state = {"logged_in": True, "username": "student_a", "login_pass": "example"}
        select_draft(state, "student_a", "2026-10-17")
        state["food_log"].append({"Food": "Rice"})
        logout(state)
        self.assertEqual(state, {})
        select_draft(state, "student_b", "2026-10-17")
        self.assertEqual(state["food_log"], [])


if __name__ == "__main__":
    unittest.main()
