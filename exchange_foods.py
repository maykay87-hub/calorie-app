"""Explicit teaching exchanges; estimates rather than cut-specific lab analysis."""
EXCHANGE_SOURCE = {
    'title': 'Malaysia CPG Management of Type 2 Diabetes Mellitus, 6th edition (2020), Appendix 3',
    'url': 'https://www.moh.gov.my/images/04-penerbitan/penerbitan-klinikal/panduan-amalan-klinikal/CPG_T2DM_6th_Edition_2020_13042021.pdf',
}

# Published-reference portions do not replace these original teaching portions.
# Ambiguous zero-energy vegetables and prepared dishes stay out of this set.
RESTORED_EXCHANGE_IDS = {
    'Rice (1/2 cup)', 'Whole Meal Bread (1 slice)', 'Oats (3 tablespoons)',
    'Apple (1 small)', 'Orange (1 small)', 'Banana (1 small)', 'Papaya (1 slice)',
    'Guava (1/2 medium)', 'Watermelon (1 slice)', 'Egg (1 whole)',
    'Taukua (1 piece)', 'Yogurt (Natural - 1 cup)', 'Low Fat Milk (1 glass)',
    'Full Cream Milk (1 glass)', 'Skim Milk (1 glass)',
}

EXCHANGE_RECORDS = {
    'Cooking Oil (1 tsp)': {
        'zh': '食用油（1平茶匙，交换份量5g）', 'name': 'Cooking oil (1 level tsp, 5g)',
        'category': '油脂与坚果 · Fats & nuts', 'weight_g': 5,
        'energy_kcal': 45, 'protein_g': 0, 'carbs_g': 0, 'fat_g': 5,
        'pdf_page': 213, 'basis': 'fat_exchange',
        'aliases': 'oil oils cooking oil olive oil vegetable oil 油 食油 食用油 橄榄油 烹调油 1 tsp teaspoon 茶匙',
    },
}

# Apply the guideline's generic poultry exchange to each named cut. These are
# 30g cooked edible meat portions, NOT one whole thigh/wing/drumstick each.
for cut, zh, aliases in (
    ('Drumstick', '鸡小腿肉', 'chicken drumstick ayam betis 鸡腿 小腿 雞腿'),
    ('Thigh', '鸡大腿肉', 'chicken thigh ayam paha 鸡腿 大腿 雞腿'),
    ('Wing', '鸡翅肉', 'chicken wing ayam kepak 鸡翅 鸡翼 雞翅 雞翼'),
):
    EXCHANGE_RECORDS[f'Chicken {cut} Meat (30 g cooked, skinless, boneless; exchange)'] = {
        'zh': f'{zh}（去皮去骨熟重30g，不含额外油）',
        'name': f'Chicken {cut.lower()} meat (30g cooked, skinless, boneless; no added oil) · 1 exchange',
        'category': '肉蛋豆鱼 · Protein foods', 'weight_g': 30,
        'energy_kcal': 65, 'protein_g': 7, 'carbs_g': 0, 'fat_g': 4,
        'pdf_page': 211, 'basis': 'generic_poultry_exchange',
        'aliases': aliases,
    }
