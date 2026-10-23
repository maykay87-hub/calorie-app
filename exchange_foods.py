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

EXCHANGE_RECORDS['Chicken Meat (40 g raw, skinless, boneless; exchange)'] = {
    'zh': '鸡肉（去皮去骨生重40g，不含额外油）',
    'name': 'Chicken meat (40g raw, skinless, boneless; no added oil) · 1 exchange',
    'category': '肉蛋豆鱼 · Protein foods', 'weight_g': 40,
    'energy_kcal': 65, 'protein_g': 7, 'carbs_g': 0, 'fat_g': 4,
    'pdf_page': 211, 'basis': 'generic_poultry_exchange_raw',
    'aliases': 'chicken raw skinless boneless ayam mentah 鸡肉 生重 去皮 去骨',
}

# The owner supplied Appendix 5 pages from this book. No unverified full-book
# download or page numbers are claimed. These are exchange estimates, not a
# transcribed per-food composition table.
ATLAS_SOURCE = {
    'title': 'Atlas Makanan: Saiz Pertukaran & Porsi / Atlas of Food Exchanges & Portion Sizes, second edition',
    'section': 'Appendix 5: Food Groups and Exchange Lists',
    'source_type': 'owner_supplied_reference_pages',
}


def _atlas_exchange(name, zh, portion, portion_zh, category, energy, protein, carbs, fat,
                    weight_g=None, preparation='as_listed', aliases=''):
    key=f'{name} ({portion}; Atlas exchange)'
    if 'cup' in portion and category != '奶类与酸奶 · Dairy':
        portion_zh += '；量杯200ml'
    EXCHANGE_RECORDS[key] = dict(
        zh=f'{zh}（{portion_zh}，交换估算）', name=f'{name} ({portion}; exchange estimate)',
        category=category, weight_g=weight_g, energy_kcal=energy, protein_g=protein,
        carbs_g=carbs, fat_g=fat, basis='food_group_exchange', source=ATLAS_SOURCE,
        preparation=preparation, portion=portion, aliases=f'{name} {zh} {aliases}')
    if 'cup' in portion:
        EXCHANGE_RECORDS[key]['household_measure_basis'] = 'Atlas cup = 200ml'
    if 'tablespoon' in portion:
        EXCHANGE_RECORDS[key]['household_measure_basis'] = 'Atlas level tablespoon uses the book measure; do not substitute another tablespoon size'


for row in (
    ('Rice porridge','白粥','1 cup cooked','熟粥1杯',None,'cooked','粥 bubur'),
    ('Brown rice','糙米饭','1/2 cup cooked','熟饭半杯',None,'cooked','brown rice nasi perang'),
    ('Kway teow','粿条','1/2 cup cooked','熟粿条半杯',None,'cooked','kuey teow 河粉'),
    ('Mee hoon','米粉','1/2 cup cooked','熟米粉半杯',None,'cooked','bihun bee hoon'),
    ('Tang hoon','冬粉','1/2 cup cooked','熟冬粉半杯',None,'cooked','glass noodles 粉丝'),
    ('Macaroni','通心粉','1/2 cup cooked','熟通心粉半杯',None,'cooked','pasta macaroni'),
    ('Wet yellow noodles','黄面','1/3 cup','湿面三分之一杯',None,'as_listed','mee wet noodles'),
    ('Idli','印度蒸米糕','1 piece (60g)','1个60g',60,'as_listed','idli idly'),
    ('Putu mayam','印度米线糕','1 piece (40g)','1个40g',40,'as_listed','putu mayam'),
    ('Thosai plain','原味印度薄饼','1/2 piece (20cm diameter)','直径20cm的半片',None,'as_listed','tosai thosai dosa'),
    ('Chapatti plain','原味全麦薄饼','1/3 piece (20cm diameter)','直径20cm的三分之一片',None,'as_listed','chapati capati'),
    ('White bread','白面包','1 slice (30g)','1片30g',30,'as_listed','roti putih'),
    ('Pita bread','皮塔饼','1/2 piece (6 inch diameter)','直径6英寸的半片',None,'as_listed','pita'),
    ('Oatmeal cooked','熟燕麦粥','1/4 cup cooked','熟燕麦粥四分之一杯',None,'cooked','oats porridge'),
    ('Sweet potato','番薯','1/2 cup (45g)','半杯45g',45,'as_listed','sweet potato ubi keledek 红薯 地瓜'),
    ('Tapioca','木薯','1/2 cup (45g)','半杯45g',45,'as_listed','ubi kayu cassava'),
    ('Pumpkin','南瓜','1 cup (100g)','1杯100g',100,'as_listed','labu'),
    ('Potato','马铃薯','1 small (75g)','小1个75g',75,'as_listed','kentang 土豆'),
    ('Green peas','青豆','1/2 cup','半杯',None,'as_listed','peas kacang pis'),
    ('Water chestnuts','马蹄','4 pieces','4个',None,'as_listed','water chestnuts 荸荠'),
):
    name,zh,portion,portion_zh,weight,state,aliases=row
    _atlas_exchange(name,zh,portion,portion_zh,'主食与谷物 · Grains & starches',75,2,15,.5,
                    weight,state,aliases)

for name,zh,portion,portion_zh,weight,aliases in (
    ('Star fruit','杨桃','1 medium','中1个',None,'belimbing starfruit'),
    ('Custard apple','番荔枝','1 medium','中1个',None,'buah nona 释迦'),
    ('Persimmon','柿子','1 medium','中1个',None,'persimmon'),
    ('Hog plum','沙梨','6 whole','6个',None,'kedondong ambarella'),
    ('Mangosteen','山竹','2 small','小2个',None,'manggis'),
    ('Duku langsat','杜古／兰撒果','8 pieces','8个',None,'duku langsat'),
    ('Grapes','葡萄','8 pieces','8粒',None,'anggur grapes'),
    ('Lychee','荔枝','5 whole','5个',None,'laici lychee'),
    ('Rambutan','红毛丹','5 whole','5个',None,'rambutan'),
    ('Pomelo','柚子','5 slices','5瓣',None,'limau bali pomelo'),
    ('Soursop','刺果番荔枝','1 slice','1片',None,'durian belanda soursop'),
    ('Prunes','西梅干','3 pieces','3粒',None,'prunes'),
    ('Dates dried','椰枣干','2 pieces','2粒',None,'kurma dates'),
    ('Raisins','葡萄干','20g','20g',20,'kismis raisins'),
    ('Durian','榴莲','2 medium seeds of flesh','中等2粒果肉',None,'durian'),
):
    _atlas_exchange(name,zh,portion,portion_zh,'水果 · Fruit',60,None,15,None,weight,aliases=aliases)

for name,zh,portion,portion_zh,weight,aliases in (
    ('Tau kwa','豆干','1/2 piece (60g)','半块60g',60,'taukua tau kwa'),
    ('Soft tofu','嫩豆腐','3/4 piece (90g)','四分之三块90g',90,'tau hoo tauhu tofu'),
    ('Tempeh','天贝','1 piece (45g)','1块45g',45,'tempeh tempe'),
    ('Dried bean curd sheet','腐竹','1.5 sheets (30g)','1.5片30g',30,'fucok fuchuk'),
    ('Cheddar cheese','切达奶酪','2 thin slices (30g)','薄2片30g',30,'keju cheese'),
    ('Cottage cheese','茅屋奶酪','1/4 small cup','小杯四分之一杯',None,'cottage cheese'),
):
    _atlas_exchange(name,zh,portion,portion_zh,'肉蛋豆鱼 · Protein foods',65,7,0,4,weight,aliases=aliases)

for name,zh,portion,portion_zh,weight,aliases in (
    ('Fish flesh','鱼肉','40g edible portion','可食鱼肉40g',40,'ikan fish'),
    ('Squid','鱿鱼','1 medium (40g)','中1只40g',40,'sotong squid 苏东'),
    ('Prawns','虾','6 medium','中6只',None,'udang prawns shrimp'),
):
    _atlas_exchange(name,zh,portion,portion_zh,'肉蛋豆鱼 · Protein foods',35,7,0,1,weight,aliases=aliases)

for name,zh,portion,portion_zh,aliases in (
    ('Butter','牛油','1 level teaspoon','1平茶匙','butter mentega'),
    ('Margarine','人造黄油','1 level teaspoon','1平茶匙','margarine marjerin'),
    ('Mayonnaise','美乃滋','1 level teaspoon','1平茶匙','mayo mayonnaise'),
    ('Peanut butter','花生酱','2 level teaspoons','2平茶匙','peanut butter'),
    ('Coconut milk','椰浆','2 level tablespoons','2平汤匙','santan coconut milk'),
    ('Non-dairy creamer powder','奶精粉','2 level tablespoons','2平汤匙','krimer creamer'),
):
    _atlas_exchange(name,zh,portion,portion_zh,'油脂与坚果 · Fats & nuts',45,None,None,5,aliases=aliases)

for name,zh,energy,protein,carbs,fat in (
    ('Skimmed milk','脱脂牛奶',90,8,15,None),
    ('Low fat milk','低脂牛奶',125,8,12,5),
    ('Full cream milk','全脂牛奶',150,8,10,9),
):
    _atlas_exchange(name,zh,'240ml','240ml','奶类与酸奶 · Dairy',energy,protein,carbs,fat)
    EXCHANGE_RECORDS[f'{name} (240ml; Atlas exchange)']['volume_ml']=240
