"""Session-only drafts, separated by signed-in account and entry date."""


def select_draft(state, username, entry_date):
    drafts = state.setdefault("daily_drafts", {})
    draft = drafts.setdefault(
        (username, str(entry_date)), {"food_log": [], "exercise_log": []}
    )
    state["food_log"] = draft["food_log"]
    state["exercise_log"] = draft["exercise_log"]
    return draft


def logout(state):
    # Clear widgets, profile values and drafts before another account signs in.
    state.clear()
