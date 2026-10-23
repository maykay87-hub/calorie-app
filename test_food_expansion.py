"""Verify source distinctions and realistic component combinations."""
import json
from pathlib import Path
from food_database import build_food_database
from food_catalogue import filter_foods, food_picker_label, BUILD_MEAL, READY_MEALS
from nutrition_registry import REFERENCE_RECORDS, make_food_entry
from exchange_foods import EXCHANGE_RECORDS
from tracker_storage import save_day, load_day, HEADERS
from test_tracker_storage import Sheet


def test_myfcd_batch_keeps_per_100g_source_and_edible_portions_together():
    data=json.loads((Path(__file__).parent/'data/foods_myfcd_ingredients.json').read_text())
    assert len(data['records'])==39
    assert len({r['food_code'] for r in data['records']})==39
    database=build_food_database()
    for r in data['records']:
        assert r['source_url'].startswith('https://myfcd.moh.gov.my/')
        assert r['data_year']==1997 and r['portion_basis']=='edible_weight'
        for field,raw in [('energy_kcal','Energy'),('protein_g','Protein'),('carbs_g','Carbohydrate'),('fat_g','Fat')]:
            assert r[field]==round(r['per_100g'][raw]*r['weight_g']/100,3)
        entry=make_food_entry(database,r['id'],'Lunch',2)
        assert entry['Source']['region']=='Malaysia'
        assert entry['Source']['per_100g']==r['per_100g']
        assert entry['Source']['food_code']==r['food_code']
        assert entry['Calories']==r['energy_kcal']*2


def test_raw_chicken_reference_is_separate_from_cooked_exchange_and_label_is_explicit():
    database=build_food_database()
    raw=next(r for r in REFERENCE_RECORDS.values() if r.get('food_code')=='108014')
    cooked='Chicken Thigh Meat (30 g cooked, skinless, boneless; exchange)'
    assert raw['weight_g']==40 and raw['preparation']=='raw'
    assert 'skin unspecified' in food_picker_label(raw['id'])
    assert '30g cooked' in food_picker_label(cooked)
    assert make_food_entry(database,raw['id'],'Lunch',2)['Calories']==176
    assert make_food_entry(database,cooked,'Lunch',2)['Calories']==130
    assert database[raw['id']]['Prot']==6.8
    raw_exchange='Chicken Meat (40 g raw, skinless, boneless; exchange)'
    assert make_food_entry(database,raw_exchange,'Lunch',2)['Calories']==130
    assert '40g raw' in food_picker_label(raw_exchange)


def test_atlas_unknown_nutrients_and_milk_volume_are_not_made_into_zeros_or_grams():
    database=build_food_database()
    fruit='Raisins (20g; Atlas exchange)'
    entry=make_food_entry(database,fruit,'Snack',1)
    assert entry['Calories']==60 and entry['Carbs']==15
    assert entry['Protein'] is None and entry['Fat'] is None
    assert entry['Source']['source_type']=='owner_supplied_reference_pages'
    assert entry['Source']['pdf_page'] is None
    milk=make_food_entry(database,'Low fat milk (240ml; Atlas exchange)','Breakfast',1)
    assert milk['Calories']==125 and milk['Source']['portion_unit']=='ml'
    assert milk['Source']['weight_g_per_serving'] is None


def test_economy_rice_components_are_searchable_saveable_and_remain_separate_from_ready_meals():
    database=build_food_database()
    for query in ['菜心','空心菜','长豆','秋葵','豆腐','天贝','kembung','巴当马鲛鱼']:
        assert filter_foods(database,query=query,mode=BUILD_MEAL), query
    cabbage=next(r['id'] for r in REFERENCE_RECORDS.values() if r.get('food_code')=='105017')
    fish=next(r['id'] for r in REFERENCE_RECORDS.values() if r.get('food_code')=='110053')
    keys=['Rice (1/2 cup)',cabbage,fish,'Cooking Oil (1 tsp)']
    entries=[make_food_entry(database,k,'Lunch',1) for k in keys]
    sheet=Sheet([HEADERS])
    total=sum(r['Calories'] for r in entries)
    save_day(sheet,'student','2026-10-23',entries,[],total,'composed meal','None')
    assert load_day(sheet,'student','2026-10-23')['food_log']==entries
    ready=filter_foods(database,mode=READY_MEALS)
    assert all(k not in ready for k in keys)
    assert any('Wantan Mee Dry' in k for k in ready)
