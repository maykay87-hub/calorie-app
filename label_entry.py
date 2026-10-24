"""User-entered package labels; unknown nutrients are distinct from zero."""
import math
from food_catalogue import MEAL_LABELS


def _amount(value, name, positive=False, optional=False):
    if value is None and optional:
        return None
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value) or value < 0 or (positive and value == 0)):
        raise ValueError(f"{name}：请输入有效数值 · Enter a valid amount.")
    return float(value)


def make_label_entry(name, meal, unit, label_amount, consumed_amount,
                     calories, protein=None, carbs=None, fat=None):
    name = name.strip() if isinstance(name, str) else ""
    if not name or len(name) > 120:
        raise ValueError("请填写食物名称（最多120字） · Enter a food name.")
    if meal not in MEAL_LABELS or unit not in {"g", "ml", "serving"}:
        raise ValueError("请选择餐次及标签单位 · Choose meal and label unit.")
    basis = _amount(label_amount, "标签份量 Label amount", positive=True)
    consumed = _amount(consumed_amount, "实际食用量 Amount eaten", positive=True)
    ratio = consumed / basis
    if not math.isfinite(ratio) or ratio <= 0:
        raise ValueError("份量过大或过小，请检查单位 · Check the amount and unit.")
    raw = {"Calories": _amount(calories, "热量 kcal"),
           "Protein": _amount(protein, "蛋白质 Protein", optional=True),
           "Carbs": _amount(carbs, "碳水 Carbs", optional=True),
           "Fat": _amount(fat, "脂肪 Fat", optional=True)}
    scaled = {key: None if value is None else round(value * ratio, 6)
              for key, value in raw.items()}
    if not math.isfinite(ratio) or any(value is not None and not math.isfinite(value) for value in scaled.values()):
        raise ValueError("份量过大，请检查单位 · Check the amount and unit.")
    suffix = "份 serving" if unit == "serving" else unit
    return {"Meal": meal, "Food": f"{name}（标签每 {basis:g} {suffix} · Label）",
            "Qty": ratio, **scaled,
            "Source": {"status": "user_entered_package_label", "title": "包装标签 · Package label (user entered)",
                       "product_name": name, "label_amount": basis, "label_unit": unit,
                       "nutrients_per_label_amount": raw}}


def entry_amount_label(entry):
    source = entry.get("Source", {})
    if source.get("status") == "user_entered_package_label":
        unit = source["label_unit"]
        unit = "份" if unit == "serving" else unit
        return f"{entry['Qty'] * source['label_amount']:g} {unit}"
    return f"{entry['Qty']:g} 份"
