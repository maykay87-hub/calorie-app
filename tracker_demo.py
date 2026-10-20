"""Public product demo. All profiles, drafts and saves stay in this session."""
from copy import deepcopy
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import streamlit as st
from food_catalogue import food_picker_label, filter_foods, MEAL_LABELS
from nutrition_registry import reference_database, make_food_entry
from profile_storage import ACTIVITIES, validate_profile
from tracker_state import change_entries, undo_entries
from tracker_ui import MAY_BLOOM_CSS, calorie_summary, remaining_panel, brand_header, progress_scale
from student_notes import prepare_note


def _open_day(day):
    st.session_state['demo_date'] = date.fromisoformat(day)


def render_demo():
    st.markdown(MAY_BLOOM_CSS, unsafe_allow_html=True)
    st.markdown(brand_header(), unsafe_allow_html=True)
    st.info('公开体验 · Demo — 示范资料仅留在本次页面，不会进入学员账号。')
    if st.session_state.pop('demo_save_notice', False):
        st.success('演示记录已保存到本次页面，可到 Wellness History 回看；不写入云端。')
    if st.session_state.pop('demo_celebration', False):
        st.balloons()
    profile = st.session_state.setdefault('demo_profile', {'height_cm': 160.0, 'weight_kg': 60.0, 'activity': ACTIVITIES[0]})
    with st.sidebar:
        st.markdown('<div class="mb-profile-kicker">DEMO PROFILE · 示范个人资料</div>', unsafe_allow_html=True)
        st.subheader('个人资料 · Profile')
        with st.form('demo_profile_form'):
            height = st.number_input('身高 Height (cm)', 100.0, 200.0, value=profile['height_cm'], step=.5, key='demo_height')
            weight = st.number_input('体重 Weight (kg)', 30.0, 200.0, value=profile['weight_kg'], step=.1, key='demo_weight')
            activity = st.selectbox('活动水平 Activity level', ACTIVITIES, index=ACTIVITIES.index(profile['activity']), key='demo_activity')
            save_profile = st.form_submit_button('保存示范资料 · Save profile', type='primary', use_container_width=True)
        if save_profile:
            profile = validate_profile(height, weight, activity)
            st.session_state['demo_profile'] = profile
            st.success('示范资料已更新 · Demo profile updated')
        bmi = profile['weight_kg'] / (profile['height_cm'] / 100) ** 2
        ideal_weight = 22 * (profile['height_cm'] / 100) ** 2
        adjusted = ideal_weight + .25 * (profile['weight_kg'] - ideal_weight)
        target = (adjusted if bmi >= 25 else profile['weight_kg']) * (25 if profile['activity'] == ACTIVITIES[0] else 30)
        st.metric('示范每日目标 · Demo target', f'{target:,.0f} kcal')
        st.caption('用于体验操作，不是个人饮食建议 · Sample use only')
    today = datetime.now(ZoneInfo('Asia/Kuala_Lumpur')).date()
    with st.expander('💌 May 的反馈 · 示例 Sample'):
        st.caption('示范点评，不是对你的个人评估 · Sample feedback')
        st.markdown(f'**示范发布日：{today.isoformat()}**')
        st.write('午餐可以多留意蔬菜的搭配；下周先从三个午餐各加一份蔬菜开始。')
        with st.expander('以往示范点评 · Previous sample review'):
            st.markdown(f'**示范发布日：{(today - timedelta(days=7)).isoformat()}**')
            st.write('这周有持续记录，是很好的开始。先试着把饮料也记下来。')
        st.write('课程方案：前 12 周每周一次真人记录点评，其后 9 个月每月一次。')
    selected_day = st.date_input('📅 Date of Entry · 记录日期', today, key='demo_date')
    days = st.session_state.setdefault('demo_days', {})
    draft = days.setdefault(str(selected_day), {'food_log': [], 'exercise_log': []})
    entries = draft['food_log']
    notes = draft.setdefault('notes', [])
    burned = sum(row['Calories Burned'] for row in draft['exercise_log'])
    st.session_state['demo_foods'] = entries
    st.session_state['demo_burned'] = burned
    intake = sum(item['Calories'] for item in entries)
    remaining = target - intake + burned
    pending_count = sum(1 for note in notes if note['needs_calories'])
    st.markdown(calorie_summary(intake, burned, intake - burned, None if pending_count else remaining), unsafe_allow_html=True)
    if pending_count:
        st.markdown(remaining_panel(remaining, provisional=True), unsafe_allow_html=True)
        st.info(f'另有 {pending_count} 笔食物尚未计入；余额仅按已填记录暂估 · Provisional remaining')
    else:
        st.markdown('<p class="mb-progress-title">Daily Energy Progress · 今日热量进度</p>', unsafe_allow_html=True)
        st.progress(max(0.0, min(1.0, (intake - burned) / target)))
        st.markdown(progress_scale(intake - burned, target), unsafe_allow_html=True)
        st.markdown(remaining_panel(remaining), unsafe_allow_html=True)
    database = reference_database()
    foods = filter_foods(database)
    saved = st.session_state.setdefault('demo_saved', {})
    food_tab, exercise_tab, history_tab = st.tabs(
        ['🍽️ Food Log · 饮食', '🔥 Exercise Log · 运动', '📜 Wellness History · 历史'],
        key='demo_tracker_tabs', on_change='rerun')
    with food_tab:
        with st.form('demo_food_form'):
            a, b, c, d = st.columns([1.2, 3.5, 1, 1.3], vertical_alignment='bottom')
            meal = a.selectbox('餐次 · Meal', list(MEAL_LABELS), format_func=MEAL_LABELS.get)
            food = b.selectbox('食物 · Food Item', foods, format_func=food_picker_label)
            qty = c.number_input('份数 · Servings', min_value=.01, value=1.0, step=.25)
            add = d.form_submit_button('Add Meal ＋', type='primary', use_container_width=True)
        if add:
            change_entries(draft, 'food', entries + [make_food_entry(database, food, meal, qty)])
            st.rerun()
        if entries:
            st.dataframe([{'餐次 Meal': MEAL_LABELS.get(f['Meal'], f['Meal']), '食物 Food': food_picker_label(f['Food']),
                           '份数': f['Qty'], 'kcal': f['Calories']} for f in entries], use_container_width=True, hide_index=True)
        a, b = st.columns(2)
        if a.button('撤销上一笔 · Undo', disabled=not draft.get('food_undo'), use_container_width=True):
            undo_entries(draft, 'food')
            st.rerun()
        if b.button('清空饮食 · Clear food', disabled=not entries, use_container_width=True):
            change_entries(draft, 'food', [])
            st.rerun()
        with st.expander('找不到食物？写备注／附上文件 · Remarks & attachments'):
            st.caption('仅体验用途，请只上传示范文件；不会写入学员数据库。')
            generation = st.session_state.get('demo_note_version', 0)
            with st.form(f'demo_remark_{selected_day}_{generation}'):
                note_meal = st.selectbox('餐次 · Meal', list(MEAL_LABELS), format_func=MEAL_LABELS.get)
                remark = st.text_area('备注 · Remarks', max_chars=2000)
                files = st.file_uploader('照片或文件（选填） · Photos or files', type=['jpg', 'jpeg', 'png', 'webp', 'pdf'],
                                        accept_multiple_files=True, max_upload_size=2)
                uncounted = st.checkbox('这笔食物尚未计入热量 · Food not counted yet', value=True)
                add_note = st.form_submit_button('保存示范备注 · Save demo remarks')
            if add_note:
                try:
                    if len(notes) >= 5:
                        raise ValueError('演示每个日期最多五笔备注，可按重新体验清空。')
                    note = prepare_note('demo', selected_day, note_meal, remark,
                                        [(file.name, file.getvalue()) for file in files], uncounted)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    if not any(n['note_id'] == note['note_id'] for n in notes):
                        notes.append(note)
                    st.session_state['demo_note_version'] = generation + 1
                    st.rerun()
            for note in notes:
                st.text(note['Remarks'])
                for index, file in enumerate(note['files']):
                    st.download_button(file['name'], file['data'], file_name=file['name'], mime=file['mime'],
                                       key=f"demo_file_{note['note_id']}_{index}", on_click='ignore')
                if note['needs_calories']:
                    st.caption('热量待补充 · Not counted yet')
                    if st.button('已补齐饮食热量 · Mark counted', key=f"demo_counted_{note['note_id']}"):
                        if not saved.get(str(selected_day), {}).get('food_log'):
                            st.error('请先添加并保存当天饮食 · Add and save the food first')
                        else:
                            note['needs_calories'] = False
                            st.rerun()
    with exercise_tab:
        activities = {'Yoga': 100, 'Walking (Brisk)': 130, 'Jogging': 240}
        with st.form('demo_exercise_form'):
            a, b, c = st.columns([3.2, 1, 1.25], vertical_alignment='bottom')
            activity_name = a.selectbox('运动类型 · Activity', list(activities))
            minutes = b.number_input('时长（分钟） · Duration', min_value=1, value=30, step=5)
            add_exercise = c.form_submit_button('添加运动 · Add activity', type='primary', use_container_width=True)
        if add_exercise:
            change_entries(draft, 'exercise', draft['exercise_log'] + [{'Activity': activity_name, 'Duration': minutes, 'Calories Burned': activities[activity_name] * minutes / 30}])
            st.rerun()
        if draft['exercise_log']:
            st.dataframe(draft['exercise_log'], use_container_width=True, hide_index=True)
        if st.button('撤销上一笔运动 · Undo activity', disabled=not draft.get('exercise_undo')):
            undo_entries(draft, 'exercise')
            st.rerun()
    with history_tab:
        st.markdown('<h2 class="mb-section-title">📜 Your Wellness History</h2>', unsafe_allow_html=True)
        st.caption('仅显示本次体验中按保存的记录 · Saved in this demo session only')
        history = [{'Date': day, 'Food Intake': sum(f['Calories'] for f in snap['food_log']),
                    'Exercise Burn': sum(e['Calories Burned'] for e in snap['exercise_log'])}
                   for day, snap in sorted(saved.items(), reverse=True)]
        if history:
            for row in history:
                row['Net Calories'] = row['Food Intake'] - row['Exercise Burn']
            st.dataframe(history, use_container_width=True, hide_index=True)
            history_day = st.selectbox('已保存日期 · Saved date', [r['Date'] for r in history])
            st.button('打开这一天 · Open day', on_click=_open_day, args=(history_day,))
        else:
            st.write('添加饮食或运动后，按下方保存即可在这里查看。')
    if st.button('体验保存 · Try save', type='primary', use_container_width=True):
        celebrated = st.session_state.setdefault('demo_celebrated_days', set())
        if (draft['food_log'] or draft['exercise_log']) and str(selected_day) not in celebrated:
            celebrated.add(str(selected_day))
            st.session_state['demo_celebration'] = True
        saved[str(selected_day)] = deepcopy(draft)
        st.session_state['demo_save_notice'] = True
        st.rerun()
    left, right = st.columns(2)
    if left.button('重新体验 · Reset demo'):
        for key in ('demo_days', 'demo_saved', 'demo_foods', 'demo_burned', 'demo_celebrated_days', 'demo_celebration'):
            st.session_state.pop(key, None)
        st.rerun()
    if right.button('学员登入 · Student login'):
        st.query_params.pop('demo', None)
        st.rerun()
