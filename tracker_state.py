"""Session-only drafts, separated by signed-in account and entry date."""
from copy import deepcopy


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


def daily_signature(foods, exercises):
    """Compare full saved snapshots, including unknown nutrients and sources."""
    import json
    return json.dumps([foods, exercises], sort_keys=True, ensure_ascii=False, allow_nan=False)


def change_entries(draft, kind, entries):
    if kind not in {"food", "exercise"}:
        raise ValueError("Unknown entry kind.")
    current = draft[kind + "_log"]
    if current == entries:
        return False
    history = draft.setdefault(kind + "_undo", [])
    history.append(deepcopy(current))
    del history[:-20]
    current[:] = deepcopy(entries)
    return True


def undo_entries(draft, kind):
    if kind not in {"food", "exercise"}:
        raise ValueError("Unknown entry kind.")
    history = draft.get(kind + "_undo", [])
    if not history:
        return False
    draft[kind + "_log"][:] = history.pop()
    return True


def pending_dates(state, username):
    """Loaded, changed drafts for this account only; include cleared saved days."""
    return sorted(day for (owner, day), draft in state.get("daily_drafts", {}).items()
                  if owner == username and draft.get("loaded")
                  and daily_signature(draft["food_log"], draft["exercise_log"])
                  != draft.get("saved_signature"))
