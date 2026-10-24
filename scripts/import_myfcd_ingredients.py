"""Refresh a curated public MyFCD batch; never fetch food data at app runtime.

Requires only Python's standard library. Review the generated manifest before
committing; a missing or changed nutrient cell fails the import, never becomes 0.
"""
import concurrent.futures
from datetime import date
from html.parser import HTMLParser
from html import unescape
import json
from pathlib import Path
import re
from urllib.request import urlopen

# Public food codes verified against the official catalogue index. English and
# Chinese labels describe the ingredient, not an inferred cooked preparation.
FOODS = [
 ('105007','Winged beans','四角豆',100,'raw'),
 ('105008','French beans','四季豆',100,'raw'),
 ('105009','Long beans','长豆',100,'raw'),
 ('105015','Pak choy','小白菜',100,'raw'),
 ('105017','Cabbage','包菜',100,'raw'),
 ('105018','Carrot','胡萝卜',100,'raw'),
 ('105020','Cauliflower','花椰菜',100,'raw'),
 ('105031','Cucumber','黄瓜',100,'raw'),
 ('105035','Brinjal','茄子',100,'raw'),
 ('105039','Bitter gourd','苦瓜',100,'raw'),
 ('105041','Snake gourd','蛇瓜',100,'raw'),
 ('105042','Winter melon','冬瓜',100,'raw'),
 ('105049','Okra','秋葵',100,'raw'),
 ('105051','Lettuce','生菜',100,'raw'),
 ('105058','Mung bean sprouts','绿豆芽',100,'raw'),
 ('105060','Fresh oyster mushrooms','鲜蚝菇',100,'raw'),
 ('105061','Choy sum','菜心',100,'raw'),
 ('105062','Mustard greens','芥菜',100,'raw'),
 ('105078','Pumpkin','南瓜',100,'raw'),
 ('105088','Spinach','菠菜',100,'raw'),
 ('105089','Bayam','苋菜',100,'raw'),
 ('105093','Red bayam','红苋菜',100,'raw'),
 ('105095','Kangkung','空心菜',100,'raw'),
 ('105098','Tomato','番茄',100,'raw'),
 ('103015','Tempeh','天贝',45,'as_listed'),
 ('103016','Tau kwa','豆干',60,'as_listed'),
 ('103019','Soft tofu','嫩豆腐',90,'as_listed'),
 ('103020','Dried bean curd sheet','腐竹',30,'dry'),
 ('108002','Lean beef','瘦牛肉',40,'raw'),
 ('108013','Chicken breast','鸡胸肉',40,'raw'),
 ('108014','Chicken thigh','鸡大腿肉',40,'raw'),
 ('108015','Chicken wing','鸡翅肉',40,'raw'),
 ('108028','Lean mutton','瘦羊肉',40,'raw'),
 ('110006','Tilapia','非洲鱼',40,'raw'),
 ('110052','Spanish mackerel tenggiri batang','巴当马鲛鱼',40,'raw'),
 ('110053','Indian mackerel ikan kembung','甘望鱼',40,'raw'),
 ('110062','Black pomfret','黑鲳鱼',40,'raw'),
 ('110064','White pomfret','白鲳鱼',40,'raw'),
 ('110066','Pink prawn','鲜虾',40,'raw'),
]

class Rows(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr': self.row=[]
        if tag in {'td','th'} and self.row is not None: self.cell=[]
    def handle_data(self,data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in {'td','th'} and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split())); self.cell=None
        if tag=='tr' and self.row is not None:
            self.rows.append(self.row); self.row=None

def fetch(item):
    code,name,zh,amount,state=item
    url=f'https://myfcd.moh.gov.my/myfcd97/index.php/site/detail_product/{code}/0/10/-1/0/0/'
    page=urlopen(url,timeout=30).read().decode('utf-8')
    if 'Value per' not in page or 'data-ori-value="100g"' not in page:
        raise ValueError(f'{code}: expected published 100g basis')
    parser=Rows(); parser.feed(page)
    heading=re.search(r'<h3[^>]*>(.*?)</h3>',page,re.S)
    if not heading: raise ValueError(f'{code}: source title missing')
    original_name=unescape(re.sub('<[^>]+>','',heading.group(1))).strip()
    cells={r[0]:r for r in parser.rows if len(r)>=3}
    raw={}
    for field in ['Energy','Protein','Fat','Carbohydrate']:
        row=cells.get(field)
        if not row or not re.fullmatch(r'\d+(?:\.\d+)?',row[2]):
            raise ValueError(f'{code}: missing or changed {field}')
        raw[field]=float(row[2])
    if cells['Energy'][1].lower()!='kcal': raise ValueError(f'{code}: wrong energy unit')
    for field in ['Protein','Fat','Carbohydrate']:
        if cells[field][1]!='g': raise ValueError(f'{code}: wrong macro unit')
    # Do not turn source serving weights/edible percentages into a second yield
    # correction: published composition is already per 100g edible portion.
    category='蔬菜 · Vegetables' if code.startswith('105') else '肉蛋豆鱼 · Protein foods'
    if code=='105078': category='主食与谷物 · Grains & starches'
    portion={'raw':'raw edible portion','dry':'dry edible portion','as_listed':'edible portion'}[state]
    portion_zh={'raw':'生重可食部 / raw','dry':'干重可食部 / dry','as_listed':'可食部 / edible'}[state]
    aliases={'105061':'sawi choy sum coy sam 青菜 菜心', '105095':'kangkung 通菜 蕹菜 空心菜',
             '105049':'bendi ladies fingers 秋葵 羊角豆', '105015':'pak choy bok choy 小白菜 青菜',
             '105035':'terung eggplant 茄子', '103019':'tau hoo tauhu tofu 豆腐',
             '105060':'cendawan mushroom 蘑菇 鲜菇', '110053':'kembong kembung 甘望鱼'}
    if category=='蔬菜 · Vegetables': aliases[code]=aliases.get(code,'')+' 蔬菜 vegetables'
    skin='not_specified' if code.startswith('10801') else 'not_applicable'
    return dict(id=f'{name} ({amount} g {portion}; MyFCD 1997 reference)',
        zh=zh,original_name=original_name,category=category,portion=portion,portion_zh=portion_zh,
        weight_g=amount,energy_kcal=round(raw['Energy']*amount/100,3),
        protein_g=round(raw['Protein']*amount/100,3),carbs_g=round(raw['Carbohydrate']*amount/100,3),
        fat_g=round(raw['Fat']*amount/100,3),per_100g=raw,food_code=code,
        source_id='myfcd_1997',source_url=url,data_year=1997,
        portion_basis='edible_weight',preparation=state,skin_status=skin,
        preparation_basis='curated_ingredient_interpretation' if state=='raw' else 'source_name',
        aliases=f'{name} {zh} '+aliases.get(code,''))

def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        records=list(pool.map(fetch,FOODS))
    result={'source':{'title':'Malaysian Food Composition Database (MyFCD 1997)',
        'url':'https://myfcd.moh.gov.my/','retrieved_on':date.today().isoformat(),
        'basis':'Published nutrient composition per 100g edible portion; selected weights scaled linearly.'},
        'records':records}
    path=Path(__file__).resolve().parents[1]/'data'/'foods_myfcd_ingredients.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(f'Validated {len(records)} source records; saved {path.name}')

if __name__=='__main__': main()
