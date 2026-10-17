"""Regression checks for recoverable profile failures without live credentials."""
import ast
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest


class ProfilePanelTests(unittest.TestCase):
    def panel(self, connection, loaded=False):
        state = {"username": "student"}
        if loaded:
            state.update(profile_loaded_user="student", profile_height_cm=164.0,
                         profile_weight_kg=52.0, profile_activity="Sedentary (x25)",
                         profile_baseline=None)
        errors = []
        captions = []
        st = SimpleNamespace(
            session_state=state, subheader=lambda *a: None,
            error=errors.append, caption=captions.append,
            button=lambda label, **kw: "Save profile" in label,
            number_input=lambda *a, **kw: state[kw["key"]],
            selectbox=lambda *a, **kw: state[kw["key"]],
            divider=lambda: None, success=lambda *a: None,
        )
        # Only extract the two functions; do not execute the app or contact Sheets.
        tree = ast.parse(Path(__file__).with_name("advancedplus.app.py").read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in {"render_profile_panel", "report_profile_error"}]
        ns = {"st": st, "logging": logging, "get_sheet_connection": connection,
              "load_profile": lambda *a: None,
              "save_profile": lambda *a: None,
              "ACTIVITIES": ["Sedentary (x25)", "Active (x30)"]}
        exec(compile(ast.Module(body=functions, type_ignores=[]), "panel", "exec"), ns)
        return ns["render_profile_panel"], state, errors

    def test_read_failure_returns_without_stopping_daily_tracker(self):
        def unavailable(*a, **kw):
            raise ValueError("Unexpected profile columns.")
        panel, state, errors = self.panel(unavailable)
        with self.assertLogs(level="ERROR"):
            self.assertIsNone(panel())
        self.assertIn("open_profiles / ValueError", errors[0])
        self.assertNotIn("profile_loaded_user", state)

    def test_save_failure_preserves_current_inputs_and_baseline(self):
        def unavailable(*a, **kw):
            raise PermissionError("unavailable")
        panel, state, errors = self.panel(unavailable, loaded=True)
        with self.assertLogs(level="ERROR"):
            current = panel()
        self.assertEqual(current["height_cm"], 164.0)
        self.assertEqual(current["weight_kg"], 52.0)
        self.assertIsNone(state["profile_baseline"])
        self.assertIn("open_profiles / PermissionError", errors[0])


if __name__ == "__main__":
    unittest.main()
