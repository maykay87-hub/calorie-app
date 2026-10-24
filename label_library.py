"""Reuse a student's own label snapshots without a new shared database."""
from datetime import date
import hashlib
import json
import unicodedata
from label_entry import make_label_entry
from tracker_storage import _read, _decode


def as_template(entry):
    source = entry.get("Source") if isinstance(entry, dict) else None
    if not isinstance(source, dict) or source.get("status") != "user_entered_package_label":
        return None
    try:
        raw = source["nutrients_per_label_amount"]
        return make_label_entry(source["product_name"], "Breakfast", source["label_unit"],
                                source["label_amount"], source["label_amount"],
                                raw["Calories"], raw.get("Protein"), raw.get("Carbs"), raw.get("Fat"))
    except (KeyError, TypeError, ValueError, AttributeError):
        # A malformed optional template must not prevent daily tracking.
        return None


def template_key(template):
    source = template["Source"]
    name = " ".join(unicodedata.normalize("NFKC", source["product_name"]).casefold().split())
    identity = [name, source["label_unit"], source["label_amount"]]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()


def remember_label(library, entry, limit=30):
    template = as_template(entry)
    if template is None:
        return list(library)
    key = template_key(template)
    return ([template] + [item for item in library if template_key(item) != key])[:limit]


def reuse_label(template, meal, amount_eaten):
    validated = as_template(template)
    if validated is None:
        raise ValueError("标签资料不完整，请重新填写 · Re-enter this package label.")
    source = validated["Source"]
    raw = source["nutrients_per_label_amount"]
    return make_label_entry(source["product_name"], meal, source["label_unit"],
                            source["label_amount"], amount_eaten, raw["Calories"],
                            raw["Protein"], raw["Carbs"], raw["Fat"])


def load_personal_labels(sheet, username):
    headers, rows = _read(sheet)
    latest = {}
    for row in rows:
        item = dict(zip(headers, row))
        if item.get("username") != username:
            continue
        try:
            day = str(date.fromisoformat(item.get("Date", "")))
        except (TypeError, ValueError):
            continue
        latest[day] = item
    library = []
    for day in sorted(latest):
        value = latest[day].get("Food_JSON")
        if not value:
            continue
        try:
            foods = _decode(value, "food")
        except (ValueError, TypeError):
            continue
        for entry in foods:
            library = remember_label(library, entry)
    return library
