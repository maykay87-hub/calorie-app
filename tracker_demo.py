"""Public, session-only product demonstration: never opens a worksheet."""
import streamlit as st
from food_catalogue import food_picker_label, filter_foods
from nutrition_registry import reference_database, make_food_entry
from tracker_ui import MAY_BLOOM_CSS, calorie_summary, remaining_panel


def render_demo():
    st.markdown(MAY_BLOOM_CSS, unsafe_allow_html=True)
    st.markdown('<h1 class="mb-title"><span>🌸 May Bloom</span> Lifestyle Tracker</h1>', unsafe_allow_html=True)
    st.info('公开体验 · Demo — 以下使用示范资料，不会保存到学员账号。')
    database = reference_database()
    foods = filter_foods(database)
    entries = st.session_state.setdefault('demo_foods', [])
    burned = st.session_state.setdefault('demo_burned', 0)
    intake = sum(item['Calories'] for item in entries)
    target = 1800
    remaining = target - intake + burned
    st.caption('示范目标 1,800 kcal，仅用于展示操作 · Sample target, not a personal recommendation')
    st.markdown(calorie_summary(intake, burned, intake - burned, remaining), unsafe_allow_html=True)
    st.markdown('<p class="mb-progress-title">Daily Energy Progress · 今日热量进度</p>', unsafe_allow_html=True)
    st.progress(max(0.0, min(1.0, (intake - burned) / target)))
    st.markdown(remaining_panel(remaining), unsafe_allow_html=True)
    food_tab, exercise_tab, review_tab = st.tabs(['🍽️ 记录饮食 · Food', '🔥 记录运动 · Exercise', '💌 真人反馈 · Review'])
    with food_tab:
        with st.form('demo_food_form'):
            a, b, c, d = st.columns([1.2, 3.5, 1, 1.3], vertical_alignment='bottom')
            meal = a.selectbox('餐次 · Meal', ['Breakfast', 'Lunch', 'Dinner', 'Snack'])
            food = b.selectbox('食物 · Food Item', foods, format_func=food_picker_label)
            qty = c.number_input('份数 · Servings', min_value=.01, value=1.0, step=.25)
            add = d.form_submit_button('Add Meal ＋', type='primary', use_container_width=True)
        if add:
            entries.append(make_food_entry(database, food, meal, qty))
            st.rerun()
        if entries:
            st.dataframe([{'餐次 Meal': f['Meal'], '食物 Food': food_picker_label(f['Food']),
                           '份数': f['Qty'], 'kcal': f['Calories']} for f in entries],
                         use_container_width=True, hide_index=True)
        if st.button('体验保存 · Try save', type='primary'):
            st.success('操作完成！正式版登入后可保存并回看记录。此演示不写入云端。 Demo only; sign in to keep real records.')
    with exercise_tab:
        st.write('体验加入一笔示范运动 · Add a sample exercise entry')
        if st.button('加入示范运动 · Add sample exercise (100 kcal)'):
            st.session_state['demo_burned'] += 100
            st.rerun()
    with review_tab:
        st.subheader('💌 May 的饮食记录反馈')
        st.caption('以下为示范文字，不是对你的个人评估 · Sample feedback')
        st.write('这周有持续记录，是很好的开始。午餐可以多留意蔬菜的搭配；下周先从三个午餐各加一份蔬菜开始。')
        st.write('课程支持方案：前 12 周每周一次真人记录点评，其后 9 个月每月一次。点评在 Tracker 内查看。')
    left, right = st.columns(2)
    if left.button('重新体验 · Reset demo'):
        st.session_state.pop('demo_foods', None)
        st.session_state.pop('demo_burned', None)
        st.rerun()
    if right.button('学员登入 · Student login'):
        st.query_params.pop('demo', None)
        st.rerun()
