"""Bilingual display labels and filters; stable English IDs retain nutrition data."""
import re
import unicodedata
from nutrition_registry import REFERENCE_RECORDS, HIDDEN_LEGACY_IDS, reference_portion

ALL_FOODS = "全部食物 · All foods"
RECENT_FOODS = "最近使用 · Recent"
MEAL_LABELS = {"Breakfast": "早餐 Breakfast", "Lunch": "午餐 Lunch", "Dinner": "晚餐 Dinner", "Snack": "加餐 Snack"}

CATEGORIES = ["主食与谷物 · Grains & starches","水果 · Fruit","蔬菜 · Vegetables","肉蛋豆鱼 · Protein foods","奶类与酸奶 · Dairy","油脂与坚果 · Fats & nuts","本地餐食 · Local meals","饮料 · Drinks"]

FOOD_META = {
    "Rice (1/2 cup)": ("白饭（半杯）", "主食与谷物 · Grains & starches"),
    "Whole Meal Bread (1 slice)": ("全麦面包（1片）", "主食与谷物 · Grains & starches"),
    "Oats (3 tablespoons)": ("燕麦（3汤匙）", "主食与谷物 · Grains & starches"),
    "Mee / Noodle (1/2 cup)": ("面条（半杯）", "主食与谷物 · Grains & starches"),
    "Potato/ Carrot (1/2 cup)": ("马铃薯／胡萝卜（半杯）", "主食与谷物 · Grains & starches"),
    "Corn / Jagung (1/2 cup)": ("玉米（半杯）", "主食与谷物 · Grains & starches"),
    "Yam / Keladi (1/2 cup)": ("芋头（半杯）", "主食与谷物 · Grains & starches"),
    "Cream Crackers (3 pieces)": ("苏打饼（3片）", "主食与谷物 · Grains & starches"),
    "Plain Biscuits / Marie (3 pieces)": ("玛丽饼／原味饼干（3片）", "主食与谷物 · Grains & starches"),
    "Bun (1 small plain)": ("原味小面包（1个）", "主食与谷物 · Grains & starches"),
    "Spaghetti (1/2 cup)": ("意大利面（半杯）", "主食与谷物 · Grains & starches"),
    "Baked beans,canned/ Lentils (1/3 cup)": ("罐头焗豆／扁豆（⅓杯）", "主食与谷物 · Grains & starches"),
    "Apple (1 small)": ("苹果（小，1个）", "水果 · Fruit"),
    "Orange (1 small)": ("橙（小，1个）", "水果 · Fruit"),
    "Pear (1/2 medium)": ("梨（中，半个）", "水果 · Fruit"),
    "Kiwi (1 large)": ("奇异果（大，1个）", "水果 · Fruit"),
    "Ciku (2 medium)": ("人心果（中，2个）", "水果 · Fruit"),
    "Pineapple (1 slice)": ("黄梨／菠萝（1片）", "水果 · Fruit"),
    "Honeydew (1 slice)": ("蜜瓜（1片）", "水果 · Fruit"),
    "Jackfruit / Nangka (4 pieces)": ("菠萝蜜（4块）", "水果 · Fruit"),
    "Plum (2 medium)": ("李子（中，2个）", "水果 · Fruit"),
    "Mango (1/2 small)": ("芒果（小，半个）", "水果 · Fruit"),
    "Guava (1/2 medium)": ("番石榴（中，半个）", "水果 · Fruit"),
    "Banana (1 small)": ("香蕉（小，1条）", "水果 · Fruit"),
    "Papaya (1 slice)": ("木瓜（1片）", "水果 · Fruit"),
    "Watermelon (1 slice)": ("西瓜（1片）", "水果 · Fruit"),
    "Ulam (Cucumber/Raw Greens)": ("生菜／黄瓜", "蔬菜 · Vegetables"),
    "Bayam Soup (Spinach)": ("菠菜汤", "蔬菜 · Vegetables"),
    "Sawi / Choy Sum (Blanched)": ("烫青菜／菜心", "蔬菜 · Vegetables"),
    "Steamed Broccoli/ cauliflower": ("蒸西兰花／花椰菜", "蔬菜 · Vegetables"),
    "Stir fry vegetables": ("炒蔬菜", "蔬菜 · Vegetables"),
    "Chicken Drumstick (1 piece)": ("鸡腿（1只）", "肉蛋豆鱼 · Protein foods"),
    "Meat / Beef / Mutton (Lean - 2 matchbox size)": ("瘦肉／牛肉／羊肉（2火柴盒大小）", "肉蛋豆鱼 · Protein foods"),
    "Prawns (6 medium)": ("虾（中，6只）", "肉蛋豆鱼 · Protein foods"),
    "Egg (1 whole)": ("鸡蛋（1个）", "肉蛋豆鱼 · Protein foods"),
    "Fish (1 medium piece)": ("鱼（中，1块）", "肉蛋豆鱼 · Protein foods"),
    "Taukua (1 piece)": ("豆干（1块）", "肉蛋豆鱼 · Protein foods"),
    "Ikan Bilis (2 tbsp)": ("江鱼仔（2汤匙）", "肉蛋豆鱼 · Protein foods"),
    "Yogurt (Natural - 1 cup)": ("原味酸奶（1杯）", "奶类与酸奶 · Dairy"),
    "Low Fat Milk (1 glass)": ("低脂牛奶（1杯）", "奶类与酸奶 · Dairy"),
    "Full Cream Milk (1 glass)": ("全脂牛奶（1杯）", "奶类与酸奶 · Dairy"),
    "Skim Milk (1 glass)": ("脱脂牛奶（1杯）", "奶类与酸奶 · Dairy"),
    "Cooking Oil (1 tsp)": ("食用油（1茶匙）", "油脂与坚果 · Fats & nuts"),
    "Butter / Margarine / Mayonnaise (1 tsp)": ("牛油／人造黄油／美乃滋（1茶匙）", "油脂与坚果 · Fats & nuts"),
    "Peanut (20 small)": ("花生（小，20粒）", "油脂与坚果 · Fats & nuts"),
    "Walnut (1 whole)": ("核桃（1整颗）", "油脂与坚果 · Fats & nuts"),
    "Almond/ Cashew nut (6 whole)": ("杏仁／腰果（6粒）", "油脂与坚果 · Fats & nuts"),
    "Sesame seed (1 level tablespoon)": ("芝麻（1平汤匙）", "油脂与坚果 · Fats & nuts"),
    "Coconut milk (santan) (2 level tablespoons)": ("椰浆（2平汤匙）", "油脂与坚果 · Fats & nuts"),
    "Nasi Lemak (Standard Hawker)": ("椰浆饭（普通小贩份量）", "本地餐食 · Local meals"),
    "Chicken Rice (Roasted - 1 plate)": ("烧鸡饭（1盘）", "本地餐食 · Local meals"),
    "Mee Goreng / Fried Mee (1 plate)": ("炒面（1盘）", "本地餐食 · Local meals"),
    "Noodle Soup / Mee Soup (1 bowl)": ("汤面（1碗）", "本地餐食 · Local meals"),
    "Curry Mee (1 bowl)": ("咖喱面（1碗）", "本地餐食 · Local meals"),
    "Char Kuey Teow (1 plate)": ("炒粿条（1盘）", "本地餐食 · Local meals"),
    "Roti Canai (1 piece + dhal)": ("印度煎饼（1片配豆酱）", "本地餐食 · Local meals"),
    "Tosai (1 piece)": ("印度薄饼 Tosai（1片）", "本地餐食 · Local meals"),
    "Sandwich (Egg Mayo - 2 slices)": ("鸡蛋美乃滋三明治（2片面包）", "本地餐食 · Local meals"),
    "Satay (Chicken - 5 sticks)": ("鸡肉沙爹（5串）", "本地餐食 · Local meals"),
    "Teh Tarik (1 glass)": ("拉茶（1杯）", "饮料 · Drinks"),
    "Kopi O (Black with Sugar)": ("咖啡乌（加糖）", "饮料 · Drinks"),
    "Kopi Susu (Coffee with Milk)": ("奶咖啡", "饮料 · Drinks"),
    "Milo (1 cup)": ("美禄（1杯）", "饮料 · Drinks"),
    "Syrup Bandung (1 glass)": ("玫瑰奶露（1杯）", "饮料 · Drinks"),
    "Plain Water": ("白开水", "饮料 · Drinks"),
}

FOOD_META.update({key: (item["zh"], item["category"]) for key, item in REFERENCE_RECORDS.items()})


def food_label(food_id):
    reference = REFERENCE_RECORDS.get(food_id)
    if reference:
        portions = {"1 bowl": "1碗", "1 plate": "1盘", "1 piece": "1片", "1 set": "1份",
                    "1 pack": "1包", "1 pot": "1煲", "1 scoop": "1勺", "1 cup": "1杯"}
        portion = reference.get("portion_zh", portions.get(reference["portion"], reference["portion"]))
        name = food_id.split(" (" + reference["portion"] + ",", 1)[0]
        region = "，SG参考" if reference.get("source_id") == "hpb_sgfoodid" else ""
        amount, unit = reference_portion(reference)
        return f"{reference['zh']}（{portion}，{amount:g}{unit}{region}） · {name}"
    metadata = FOOD_META.get(food_id)
    return f"{metadata[0]} · {food_id}" if metadata else food_id


def remember_food(recent, food_id, limit=8):
    """Return a new list, most recent first, with unique stable IDs."""
    return ([food_id] + [item for item in recent if item != food_id])[:limit]


SEARCH_ALIASES = {
    "Nasi Lemak (Standard Hawker)": "nasi lemak 椰浆饭 椰漿飯",
    "Chicken Rice (Roasted - 1 plate)": "nasi ayam chicken rice 鸡饭 雞飯 烧鸡饭 燒雞飯",
    "Mee Goreng / Fried Mee (1 plate)": "mee goreng mi goreng fried noodles 炒面 炒麵",
    "Noodle Soup / Mee Soup (1 bowl)": "mee sup mi sup noodle soup 汤面 湯麵",
    "Curry Mee (1 bowl)": "mee kari mi kari curry noodles 咖喱面 咖哩麵",
    "Char Kuey Teow (1 plate)": "char kuey teow char kway teow 炒粿条 炒粿條",
    "Roti Canai (1 piece + dhal)": "roti canai roti prata 印度煎饼 印度煎餅",
    "Tosai (1 piece)": "tosai thosai dosa dosai",
    "Teh Tarik (1 glass)": "teh tarik 拉茶",
}


SEARCH_ALIASES.update({key: item["aliases"] + " " + item["original_name"] for key, item in REFERENCE_RECORDS.items()})


def _search_text(value):
    return " ".join(re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFKC", value).casefold()).split())


def _matches_search(query, searchable):
    # Accept reordered words and omitted spaces without guessing a different dish.
    return (all(word in searchable for word in query.split())
            or query.replace(" ", "") in searchable.replace(" ", ""))


def filter_foods(database, category=ALL_FOODS, query="", recent=()):
    query = _search_text(query)
    visible = [key for key in database if key not in HIDDEN_LEGACY_IDS]
    visible.sort(key=lambda key: 0 if REFERENCE_RECORDS.get(key, {}).get("source_id") == "hpb_sgfoodid"
                 else 1 if key in REFERENCE_RECORDS else 2)
    # A typed food name always searches the entire database. Categories only
    # narrow browsing when the search box is empty.
    if query:
        matches = [
            key for key in visible
            if _matches_search(query, _search_text(food_label(key) + " " + SEARCH_ALIASES.get(key, "")))
        ]
        matches.sort(key=lambda key: query not in _search_text(food_label(key) + " " + SEARCH_ALIASES.get(key, "")))
        return matches
    if category == RECENT_FOODS:
        return list(dict.fromkeys(item for item in recent if item in database and item not in HIDDEN_LEGACY_IDS))
    if category == ALL_FOODS:
        return visible
    return [key for key in visible if FOOD_META.get(key, ("", ""))[1] == category]
