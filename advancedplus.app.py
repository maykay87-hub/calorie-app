import streamlit as st
import pandas as pd
import gspread
import logging
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime
from zoneinfo import ZoneInfo
from time import monotonic
from tracker_state import logout, select_draft, daily_signature, change_entries, undo_entries, pending_dates
from entry_editor import rescale_food, rescale_exercise, nutrient_coverage
from label_entry import make_label_entry, entry_amount_label
from label_library import load_personal_labels, remember_label, template_key, reuse_label
from tracker_storage import load_day, save_day, day_snapshot, SaveConflictError
from tracker_history import load_history, load_coach_history
from coach_feedback import load_feedback, publish_feedback, review_period
from student_notes_ui import render_student_notes, render_note_history
from student_notes import load_notes, annotate_energy_status
from tracker_export import export_history_csv, export_draft
from profile_storage import ACTIVITIES, load_profile, save_profile
from nutrition_registry import SOURCE, SG_SOURCE, REFERENCE_RECORDS, reference_database, reference_portion, make_food_entry, format_energy
from food_catalogue import ALL_FOODS, RECENT_FOODS, CATEGORIES, MEAL_LABELS, food_label, food_picker_label, filter_foods, remember_food

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="May Bloom Advanced", page_icon="🌸", layout="wide")

# Public preview is deliberately before secrets, sign-in and all worksheet access.
if st.query_params.get("demo") == "1":
    from tracker_demo import render_demo
    render_demo()
    st.stop()

# --- 2. GOOGLE SHEETS CONNECTION ---
# This test branch requires an explicit spreadsheet ID; never fall back to the live database.
SPREADSHEET_ID = st.secrets["spreadsheet_id"]

def get_sheet_connection(type="main", create=False):
    """
    Connects to Google Sheets.
    type="main" -> Returns the FIRST tab (your data logs)
    type="feedback" -> Returns the 'feedback' tab
    """
    # Reuse this sign-in's connection rather than authenticating on each widget
    # change. Logout clears it; a short TTL also picks up updated configuration.
    connection = st.session_state.get("sheet_connection")
    if not connection or connection["id"] != SPREADSHEET_ID or monotonic() - connection["time"] > 300:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["service_account"]), scope)
        client = gspread.authorize(creds)
        connection = {"id": SPREADSHEET_ID, "time": monotonic(),
                      "spreadsheet": client.open_by_key(SPREADSHEET_ID), "worksheets": {}}
        st.session_state["sheet_connection"] = connection
    spreadsheet = connection["spreadsheet"]
    if type in connection["worksheets"]:
        return connection["worksheets"][type]
    
    if type == "profiles":
        try:
            sheet = spreadsheet.worksheet("profiles")
        except gspread.WorksheetNotFound:
            if create:
                sheet = spreadsheet.add_worksheet(title="profiles", rows=100, cols=5)
            else:
                return None
    elif type in {"student_notes", "student_attachments"}:
        try:
            sheet = spreadsheet.worksheet(type)
        except gspread.WorksheetNotFound:
            if create:
                sheet = spreadsheet.add_worksheet(title=type, rows=100, cols=8 if type == "student_notes" else 5)
            else:
                return None
    elif type == "feedback":
        try:
            sheet = spreadsheet.worksheet("feedback")
        except gspread.WorksheetNotFound:
            if create:
                sheet = spreadsheet.add_worksheet(title="feedback", rows=100, cols=3)
            else:
                return None
    else:
        # "get_worksheet(0)" always grabs the first tab
        sheet = spreadsheet.get_worksheet(0)
    connection["worksheets"][type] = sheet
    return sheet

def format_log_to_string(log_list, type="food"):
    if not log_list: return "None"
    text_summary = []
    for item in log_list:
        if type == "food":
            text_summary.append(f"{item['Meal']}: {food_label(item['Food'])} (x{item['Qty']})")
        else:
            text_summary.append(f"{item['Activity']} ({item['Duration']} mins)")
    return ", ".join(text_summary)

def save_daily_summary(selected_date, food_log, exercise_log, net_calories):
    draft_saved = st.session_state["daily_drafts"][(st.session_state["username"], str(selected_date))]
    food_summary = format_log_to_string(food_log, type="food")
    exercise_summary = format_log_to_string(exercise_log, type="exercise")
    try:
        sheet = get_sheet_connection("main")
        save_day(
            sheet, st.session_state["username"], selected_date,
            food_log, exercise_log, net_calories,
            food_summary, exercise_summary,
            replace_legacy=st.session_state.get("replace_legacy", False),
            expected_snapshot=draft_saved.get("baseline"),
        )
        st.session_state["daily_drafts"][(st.session_state["username"], str(selected_date))]["legacy"] = False
        draft_saved["baseline"] = day_snapshot(st.session_state["username"], selected_date,
            food_log, exercise_log, net_calories, food_summary, exercise_summary)
        draft_saved.pop("conflict", None)
        draft_saved["saved_signature"] = daily_signature(food_log, exercise_log)
        st.session_state["daily_save_notice"] = str(selected_date)
        st.session_state.pop("history_cache", None)
        return True
    except SaveConflictError as exc:
        draft_saved["conflict"] = {"current": exc.current}
        st.rerun()
    except Exception:
        logging.getLogger(__name__).exception("Daily save failed")
        st.error("保存未确认，输入仍留在本次会话。请重试保存，暂时不要关闭或刷新页面。 Save was not confirmed. Your draft remains here; retry before closing or refreshing.")
        return False


def open_history_day(day):
    st.session_state["entry_date"] = date.fromisoformat(day)

def report_profile_error(exc, stage):
    logging.getLogger(__name__).exception("Profile failed at %s", stage)
    response = getattr(exc, "response", None)
    http_status = getattr(response, "status_code", None)
    detail = f"{stage} / {exc.__class__.__name__}"
    if http_status is not None:
        detail += f" / HTTP {http_status}"
    st.error(f"个人资料暂不可用，请提供以下错误编号。 Profile error: {detail}")
    if isinstance(exc, (ValueError, TypeError, AttributeError, NameError)):
        st.caption(str(exc))


def render_profile_panel():
    st.subheader("个人资料 · Profile")
    if st.session_state.get("profile_loaded_user") != st.session_state["username"]:
        profile_stage = "open_profiles"
        try:
            profile_sheet = get_sheet_connection("profiles")
            profile_stage = "read_profile"
            saved_profile = load_profile(profile_sheet, st.session_state["username"])
        except Exception as exc:
            report_profile_error(exc, profile_stage)
            st.caption("已保存的饮食和运动仍可使用；个人资料恢复前暂停显示热量目标。 Food and exercise remain available; the energy target is paused.")
            if st.button("重试读取资料 · Retry profile"):
                st.rerun()
            return None
        initial = saved_profile or {
            "height_cm": 160.0, "weight_kg": 70.0, "activity": ACTIVITIES[0]
        }
        st.session_state["profile_height_cm"] = initial["height_cm"]
        st.session_state["profile_weight_kg"] = initial["weight_kg"]
        st.session_state["profile_activity"] = initial["activity"]
        st.session_state["profile_baseline"] = saved_profile
        st.session_state["profile_loaded_user"] = st.session_state["username"]

    height_cm = st.number_input("身高 Height (cm)", 100.0, 200.0, step=0.5, key="profile_height_cm")
    weight_kg = st.number_input("体重 Weight (kg)", 30.0, 200.0, step=0.1, key="profile_weight_kg")
    activity = st.selectbox("活动水平 Activity level", ACTIVITIES, key="profile_activity")
    current_profile = {"height_cm": height_cm, "weight_kg": weight_kg, "activity": activity}
    if st.button("保存个人资料 · Save profile", type="primary", use_container_width=True):
        profile_stage = "open_profiles"
        try:
            profile_sheet = get_sheet_connection("profiles", create=True)
            profile_stage = "write_profile"
            stored_profile = save_profile(
                profile_sheet, st.session_state["username"], height_cm, weight_kg, activity,
            )
            st.session_state["profile_baseline"] = stored_profile
            st.success("个人资料已保存 · Profile saved")
        except Exception as exc:
            report_profile_error(exc, profile_stage)
    baseline = st.session_state.get("profile_baseline")
    if baseline is None:
        st.caption("确认资料后按保存，即可显示每日热量目标。 Save your profile to set your daily target.")
    elif current_profile != baseline:
        st.caption("个人资料修改尚未保存；热量目标仍按已保存资料计算。 Save profile changes to update your energy target.")
    st.divider()
    return baseline

# --- 3. SECURE LOGIN SYSTEM ---
def check_password():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if st.session_state["logged_in"]:
        return True

    st.markdown("<h1 style='text-align: center; color: #9B3E59;'>🌸 May Bloom Login</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.info("请使用老师提供的账号登入 · Sign in with the account provided by your coach.")
        with st.form("login_form"):
            username = st.text_input("账号 · Username", key="login_user")
            password = st.text_input("密码 · Password", type="password", key="login_pass")
            submitted = st.form_submit_button("登入 · Log in", use_container_width=True, type="primary", key="login_btn")
        if submitted:
            username = username.strip()
            if username in st.secrets["passwords"] and password == st.secrets["passwords"][username]:
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.session_state.pop("login_pass", None)
                st.session_state.pop("login_user", None)
                st.rerun()
            else:
                st.error("账号或密码不正确，请重新输入。 Incorrect username or password; please retry.")
        st.caption("账号由老师提供。如忘记密码，请联系老师。 Accounts are provided by your coach; contact your coach if you forget your password.")
    return False

if not check_password():
    st.stop()

# ==========================================
# PART 4: ADMIN DASHBOARD
# ==========================================
if st.session_state["username"] == "admin":
    
    # --- ADMIN SIDEBAR START ---
    with st.sidebar:
        st.header("👑 Admin Panel")
        
        st.divider()
        if st.button("Log Out Admin"):
            logout(st.session_state)
            st.rerun()
    # --- ADMIN SIDEBAR END ---

    st.title("学生记录 · Coach dashboard")
    st.caption("按学生与日期显示最新保存版本；未保存的学生草稿不会出现在这里。 Latest saved record per student and day; unsaved drafts are not included.")
    try:
        records = load_coach_history(get_sheet_connection("main"))
        if not records:
            st.info("暂无可显示的学生记录 · No saved student records yet")
        else:
            users = sorted({row["username"] for row in records})
            col1, col2, col3 = st.columns(3)
            col1.metric("已记录天数 · Saved days", len(records))
            col2.metric("学生人数 · Students", len(users))
            col3.metric("最新日期 · Latest date", max(row["Date"] for row in records))
            chosen_user = st.selectbox("查看学生 · Student", users, key="coach_student")
            student_records = [row for row in records if row["username"] == chosen_user]
            try:
                coach_notes = load_notes(get_sheet_connection('student_notes'), chosen_user)
            except Exception:
                coach_notes = None
            student_records = annotate_energy_status(student_records, coach_notes)
            view = []
            for row in student_records:
                if row["Protein"] is not None:
                    protein_text = f"{format_energy(row['Protein'])} g"
                elif row["known_protein"] is not None and row["missing_protein_entries"] < row["food_entries"]:
                    protein_text = f"{format_energy(row['known_protein'])} g（部分 · partial）"
                else:
                    protein_text = "— 未提供"
                status_text = {"detailed": "明细记录 · Detailed", "legacy": "旧摘要 · Older summary",
                               "invalid_details": "明细需检查 · Details need review"}[row["status"]]
                if row['Energy_complete'] is not True:
                    status_text += ' · 热量待补充／检查'
                view.append({"日期 Date": row["Date"], "净热量 Net kcal": row["Net_Calories"],
                             "蛋白质 Protein": protein_text, "记录类型 Status": status_text,
                             "饮食 Food": row["Food_Log"], "运动 Exercise": row["Exercise_Log"]})
            st.dataframe(pd.DataFrame(view), use_container_width=True, hide_index=True)
            st.caption("部分蛋白质仅为有资料食物的合计，不是全天总量。 Partial protein counts known foods only.")
            chart = pd.DataFrame([r for r in student_records if r['Energy_complete'] is True],
                                 columns=['Date', 'Net_Calories']).dropna(subset=["Net_Calories"]).sort_values("Date")
            if not chart.empty:
                st.line_chart(chart.assign(Date=pd.to_datetime(chart["Date"])), x="Date", y="Net_Calories")

    except Exception:
        logging.getLogger(__name__).exception("Coach history unavailable")
        st.error("暂时无法读取学生记录，请稍后重试。 Could not load student records; please retry.")

    # Human reviews are posted only by the signed-in coach.
    review_users = sorted(set(st.secrets["passwords"].keys()) - {"admin"})
    if review_users:
        if "coach_student" in st.session_state:
            review_user = st.session_state["coach_student"]
        else:
            review_user = st.selectbox("查看学生 · Student", review_users, key="coach_student")
        st.subheader("学员补充记录 · Student remarks")
        render_note_history(get_sheet_connection, review_user, prefix="coach_notes")
        st.subheader("💌 发布个别反馈 · Dietitian review")
        st.write(f"接收学员 · Recipient: {review_user}")
        with st.form(f"coach_review_{review_user}"):
            kind = st.radio("点评周期 · Review type", ["每周 Weekly", "每月 Monthly"], horizontal=True)
            period_day = st.date_input("选择点评所属周／月 · Review period", datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).date())
            body = st.text_area("给学员的反馈 · Your feedback", height=170, max_chars=6000,
                                placeholder="做得好的地方、一个改善重点、下阶段的行动。", key=f"review_body_{review_user}")
            publish = st.form_submit_button("发布给这位学员 · Publish review", type="primary")
        if publish:
            try:
                if not body.strip():
                    raise ValueError("Enter a review before publishing.")
                period = review_period('weekly' if kind.startswith('每周') else 'monthly', period_day)
                publish_feedback(get_sheet_connection("feedback", create=True), review_user, period, body)
                st.success(f"已发布给 {review_user} · Review published ({period})")
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                logging.getLogger(__name__).exception("Review publication unavailable")
                st.error("未能确认发布，文字已保留，请重试。 Publication was not confirmed; your text is kept. Please retry.")
        try:
            previous = load_feedback(get_sheet_connection("feedback"), review_user)
            with st.expander("查看已发布点评 · Published reviews"):
                if not previous:
                    st.write("暂无点评 · No reviews yet")
                for review in previous:
                    st.markdown(f"**{review['period']}**")
                    st.caption(f"发布时间 · Posted (MYT): {review['published_at']}" if review['published_at'] else "原有点评 · Original review (publication time unavailable)")
                    st.text(review['note'])
        except Exception:
            st.warning("暂时无法读取已发布点评 · Could not load published reviews")

    st.stop() 

# ==========================================
# PART 5: REGULAR CLIENT APP
# ==========================================

# --- MAY BLOOM PRESENTATION ---
from tracker_ui import MAY_BLOOM_CSS, calorie_summary, remaining_panel
st.markdown(MAY_BLOOM_CSS, unsafe_allow_html=True)

# --- DAILY DRAFT ---
st.markdown('<h1 class="mb-title"><span>🌸 May Bloom</span> Lifestyle Tracker</h1>', unsafe_allow_html=True)
# Reviews belong to the signed-in account, independent of the selected log date.
try:
    reviews = load_feedback(get_sheet_connection("feedback"), st.session_state["username"])
    review_error = False
except Exception:
    logging.getLogger(__name__).exception("Student feedback unavailable")
    reviews, review_error = [], True
review_title = (f"💌 May 的最新反馈 · {reviews[0]['period']}" if reviews
                else "💌 May 的反馈 · Dietitian feedback")
with st.expander(review_title):
    st.button("更新点评 · Refresh feedback", key="refresh_feedback")
    if review_error:
        st.warning("暂时无法读取点评，请按更新重试。 Could not load feedback; please refresh. Your food records are unaffected.")
    elif reviews:
        st.markdown(f"**最新反馈 · Latest review — {reviews[0]['period']}**")
        st.caption(f"发布时间 · Posted (MYT): {reviews[0]['published_at']}" if reviews[0]['published_at'] else "原有点评 · Original review (publication time unavailable)")
        st.text(reviews[0]['note'])
        if len(reviews) > 1:
            previous_reviews = {r['key']: r for r in reviews[1:]}
            previous_key = st.selectbox("以往点评 · Previous reviews", list(previous_reviews),
                format_func=lambda key: f"{previous_reviews[key]['published_at'] or '原有点评'} · {previous_reviews[key]['period']} · {previous_reviews[key]['note'][:24]}", key="previous_review")
            previous_review = previous_reviews[previous_key]
            st.caption(f"发布时间 · Posted (MYT): {previous_review['published_at']}" if previous_review['published_at'] else "原有点评 · Original review (publication time unavailable)")
            st.text(previous_review['note'])
    else:
        st.write("收到点评后会显示在这里 · Your dietitian's reviews will appear here.")

entry_date = st.date_input("📅 Date of Entry · 记录日期", datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).date(), key="entry_date")
draft = select_draft(st.session_state, st.session_state["username"], entry_date)
if not draft.get("loaded"):
    try:
        saved = load_day(get_sheet_connection("main"), st.session_state["username"], entry_date)
        draft["food_log"][:] = saved["food_log"]
        draft["exercise_log"][:] = saved["exercise_log"]
        for item in saved["food_log"]:
            st.session_state["recent_food_names"] = remember_food(
                st.session_state.get("recent_food_names", []), item["Food"]
            )
        draft["legacy"] = saved["legacy"]
        draft["summary"] = saved.get("summary")
        draft["baseline"] = saved.get("baseline")
        draft["saved_signature"] = daily_signature(draft["food_log"], draft["exercise_log"])
        draft["loaded"] = True
    except Exception:
        st.error("Could not load saved records. Check your connection and try again. Editing is paused to protect existing records.")
        if st.button("Retry loading records"):
            st.rerun()
        st.stop()
with st.expander("使用提示 · How to use"):
    st.markdown("1. **饮食 Food Log：**选日期、餐次、食物与份量 → **Add Meal**。\n"
                "2. **运动 Exercise Log：**选运动、填分钟 → **添加运动 Add activity**。\n"
                "3. 记录后按 **保存当天记录 Save**；到 **Wellness History** 回看或打开某天修改。\n\n"
                "找不到食物时，可用「备注／附上文件」保存；热量待补充时，余额暂不显示。\n\n"
                "**Remaining = 今日目标 − 饮食摄入 + 运动消耗。**负数代表高于当前目标。")
if draft.get("legacy"):
    st.caption("此日期是旧版摘要。可查看原记录；如需重新填写，请先添加完整记录再确认替换。 Older summary: view below, or enter a complete replacement.")
    with st.expander("查看旧记录 · Previous summary"):
        summary = draft.get("summary") or {}
        st.write(f"Food: {summary.get('Food_Log', '')}")
        st.write(f"Exercise: {summary.get('Exercise_Log', '')}")
        st.write(f"Net: {summary.get('Net_Calories', '')} kcal")


# --- DATABASES ---
food_database = {
    "Rice (1/2 cup)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 0},
    "Whole Meal Bread (1 slice)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 1},
    "Oats (3 tablespoons)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 2},
    "Mee / Noodle (1/2 cup)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 1},
    "Potato/ Carrot (1/2 cup)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 0},
    "Corn / Jagung (1/2 cup)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 1},
    "Yam / Keladi (1/2 cup)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 0},
    "Cream Crackers (3 pieces)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 2},
    "Plain Biscuits / Marie (3 pieces)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 2},
    "Bun (1 small plain)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 2},
    "Spaghetti (1/2 cup)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 1},
    "Baked beans,canned/ Lentils (1/3 cup)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 1},
    "Apple (1 small)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Orange (1 small)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Pear (1/2 medium)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Kiwi (1 large)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Ciku (2 medium)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Pineapple (1 slice)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Honeydew (1 slice)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Jackfruit / Nangka (4 pieces)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Plum (2 medium)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Mango (1/2 small)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Guava (1/2 medium)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Banana (1 small)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Papaya (1 slice)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Watermelon (1 slice)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Ulam (Cucumber/Raw Greens)":   {"Cals": 0,  "Prot": 0,  "Carbs": 0,  "Fat": 0},
    "Bayam Soup (Spinach)":         {"Cals": 45,  "Prot": 0,  "Carbs": 0,  "Fat": 5},
    "Sawi / Choy Sum (Blanched)":   {"Cals": 0,  "Prot": 0,  "Carbs": 0,  "Fat": 0},
    "Steamed Broccoli/ cauliflower": {"Cals": 0,  "Prot": 0,  "Carbs": 0,  "Fat": 0},
    "Stir fry vegetables":          {"Cals": 45,  "Prot": 0,  "Carbs": 0,  "Fat": 5},
    "Chicken Drumstick (1 piece)": {"Cals": 130, "Prot": 14, "Carbs": 0, "Fat": 8},
    "Meat / Beef / Mutton (Lean - 2 matchbox size)": {"Cals": 130, "Prot": 14, "Carbs": 0, "Fat": 8},
    "Prawns (6 medium)": {"Cals": 50, "Prot": 7, "Carbs": 0, "Fat": 2},
    "Egg (1 whole)": {"Cals": 65, "Prot": 7, "Carbs": 0, "Fat": 5},
    "Fish (1 medium piece)": {"Cals": 70, "Prot": 14, "Carbs": 0, "Fat": 2},
    "Taukua (1 piece)": {"Cals": 130, "Prot": 14, "Carbs": 0, "Fat": 8},
    "Ikan Bilis (2 tbsp)": {"Cals": 65, "Prot": 7, "Carbs": 0, "Fat": 2},
    "Yogurt (Natural - 1 cup)": {"Cals": 100, "Prot": 8, "Carbs": 12, "Fat": 2},
    "Low Fat Milk (1 glass)": {"Cals": 125, "Prot": 8, "Carbs": 12, "Fat": 5},
    "Full Cream Milk (1 glass)": {"Cals": 150, "Prot": 8, "Carbs": 10, "Fat": 9},
    "Skim Milk (1 glass)": {"Cals": 90, "Prot": 8, "Carbs": 15, "Fat": 0},
    "Cooking Oil (1 tsp)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},
    "Butter / Margarine / Mayonnaise (1 tsp)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},
    "Peanut (20 small)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},
    "Walnut (1 whole)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},
    "Almond/ Cashew nut (6 whole)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},
    "Sesame seed (1 level tablespoon)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},
    "Coconut milk (santan) (2 level tablespoons)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},
    "Nasi Lemak (Standard Hawker)": {"Cals": 440, "Prot": 11, "Carbs": 30, "Fat": 25},
    "Chicken Rice (Roasted - 1 plate)": {"Cals": 600, "Prot": 25, "Carbs": 60, "Fat": 28},
    "Mee Goreng / Fried Mee (1 plate)": {"Cals": 500, "Prot": 15, "Carbs": 60, "Fat": 22},
    "Noodle Soup / Mee Soup (1 bowl)": {"Cals": 350, "Prot": 15, "Carbs": 45, "Fat": 12},
    "Curry Mee (1 bowl)": {"Cals": 550, "Prot": 18, "Carbs": 50, "Fat": 30},
    "Char Kuey Teow (1 plate)": {"Cals": 740, "Prot": 15, "Carbs": 70, "Fat": 40},
    "Roti Canai (1 piece + dhal)": {"Cals": 300, "Prot": 6, "Carbs": 35, "Fat": 15},
    "Tosai (1 piece)": {"Cals": 200, "Prot": 4, "Carbs": 35, "Fat": 4},
    "Sandwich (Egg Mayo - 2 slices)": {"Cals": 300, "Prot": 10, "Carbs": 30, "Fat": 15},
    "Satay (Chicken - 5 sticks)": {"Cals": 185, "Prot": 15, "Carbs": 5, "Fat": 12},
    "Teh Tarik (1 glass)": {"Cals": 180, "Prot": 4, "Carbs": 25, "Fat": 6},
    "Kopi O (Black with Sugar)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Kopi Susu (Coffee with Milk)": {"Cals": 140, "Prot": 3, "Carbs": 20, "Fat": 5},
    "Milo (1 cup)": {"Cals": 150, "Prot": 3, "Carbs": 25, "Fat": 4},
    "Syrup Bandung (1 glass)": {"Cals": 150, "Prot": 2, "Carbs": 25, "Fat": 5},
    "Plain Water": {"Cals": 0, "Prot": 0, "Carbs": 0, "Fat": 0}
}

food_database.update(reference_database())

exercise_database = {
    "Zumba / Aerobics": 250, "Pound (Cardio Drumming)": 240, "Jogging": 240,
    "Swimming (Laps)": 230, "Badminton (Competitive)": 220, "Cycling": 200,
    "Badminton / Pickleball (Casual)": 150, "Walking (Brisk)": 130, "Gardening": 140,
    "Yoga": 100, "Pilates": 110, "House Chores": 90,
}

# --- SIDEBAR (UPDATED) ---
with st.sidebar:
    st.markdown('<div class="mb-profile-kicker">MY PROFILE · 个人资料</div>', unsafe_allow_html=True)
    st.header(f"👤 {st.session_state['username'].title()}")
    
    st.divider()
    
    profile = render_profile_panel()
    daily_needs = None
    if profile is not None:
        height_cm = profile["height_cm"]
        weight_kg = profile["weight_kg"]
        activity = profile["activity"]
        height_m = height_cm / 100
        bmi = weight_kg / (height_m ** 2)
        
        if bmi < 18.5:
            st.info(f"BMI: {bmi:.1f} (Underweight)")
            calc_weight = weight_kg
        elif 18.5 <= bmi < 23:
            st.success(f"BMI: {bmi:.1f} (Normal)")
            calc_weight = weight_kg
        elif 23 <= bmi < 25:
            st.warning(f"BMI: {bmi:.1f} (Overweight)")
            calc_weight = weight_kg
        else:
            st.error(f"BMI: {bmi:.1f} (Obese)")
            ideal_weight = 22 * (height_m ** 2)
            adj_weight = ideal_weight + 0.25 * (weight_kg - ideal_weight)
            calc_weight = adj_weight
            st.caption(f"⚠️ Adjusted Weight: {adj_weight:.1f}kg")

        daily_needs = calc_weight * (25 if "Sedentary" in activity else 30)
        st.metric("🔥 Daily Target", f"{int(daily_needs)} kcal")
        
    if st.button("Log Out"):
        logout(st.session_state)
        st.rerun()

# --- MAIN DASHBOARD ---
# Calculate Totals
if st.session_state.food_log:
    f_df = pd.DataFrame(st.session_state.food_log)
    total_intake = float(f_df["Calories"].sum())
else:
    total_intake = 0

if st.session_state.exercise_log:
    e_df = pd.DataFrame(st.session_state.exercise_log)
    total_burned = float(e_df["Calories Burned"].sum())
else:
    total_burned = 0

net_calories = total_intake - total_burned
remaining = daily_needs - net_calories if daily_needs is not None else None

supplementary_notes, notes_available, all_student_notes = render_student_notes(get_sheet_connection, st.session_state["username"], entry_date)
pending_foods = sum(1 for note in supplementary_notes if note["needs_calories"])
incomplete_energy = pending_foods > 0 or not notes_available
st.markdown(calorie_summary(total_intake, total_burned, net_calories,
    None if incomplete_energy else remaining), unsafe_allow_html=True)
if incomplete_energy:
    st.info(f"当前只显示已计热量；另有 {pending_foods} 笔食物热量待补充，暂不显示今日余额。 Food calories are incomplete; Remaining is paused."
            if notes_available else "补充记录暂时无法读取，暂不显示今日余额。 Remaining is paused until supplementary records load.")
elif daily_needs is not None:
    st.markdown('<div class="mb-progress-title">Daily Energy Progress · 今日热量进度</div>', unsafe_allow_html=True)
    st.progress(min(max(net_calories / daily_needs, 0.0), 1.0))
    st.markdown(remaining_panel(remaining), unsafe_allow_html=True)
else:
    st.info("填写并保存左侧个人资料，即可显示每日热量目标。 Save your profile to see your daily target.")

if daily_signature(st.session_state.food_log, st.session_state.exercise_log) != draft.get("saved_signature"):
    st.warning("有未保存的修改 · Unsaved changes")
elif st.session_state.pop("daily_save_notice", None) == str(entry_date):
    st.success(f"已保存 Saved · {entry_date}")

pending = pending_dates(st.session_state, st.session_state["username"])
if pending:
    with st.expander(f"待保存日期 · Unsaved days ({len(pending)})"):
        st.caption("仅保留在本次登入中。请分别打开日期并保存，离开或刷新前完成。 These drafts are kept only in this session; open each day and save before leaving or refreshing.")
        for pending_day in pending:
            st.button(f"继续填写 · Continue {pending_day}", key=f"pending_day_{pending_day}",
                      on_click=open_history_day, args=(pending_day,),
                      disabled=pending_day == str(entry_date), use_container_width=True)

# --- SAVE TO CLOUD BUTTON ---
if draft.get("conflict"):
    st.error("此日记录已在另一处更新，本次输入未写入。请先备份当前输入，再载入云端最新版。 This day changed elsewhere. Your draft was not written; back it up before loading the latest saved version.")
    st.download_button("备份当前输入 · Back up current entries",
        data=export_draft(st.session_state["username"], entry_date, st.session_state.food_log, st.session_state.exercise_log),
        file_name=f"may-bloom-draft-{entry_date}.json", mime="application/json", on_click="ignore")
    with st.expander("云端当前摘要 · Current saved summary"):
        current = draft["conflict"]["current"]
        if current is None:
            st.write("云端目前没有此日记录 · No saved record for this day")
        else:
            st.write("Food: " + str(current["Food_Log"]))
            st.write("Exercise: " + str(current["Exercise_Log"]))
            st.write(f"Net: {current['Net_Calories']} kcal")
    discard_local = st.checkbox("确认放弃此页未保存修改，载入云端记录 · Discard this draft and load saved entries", key=f"reload_conflict_{entry_date}")
    if st.button("载入云端最新版 · Load latest saved entries", disabled=not discard_local):
        del st.session_state["daily_drafts"][(st.session_state["username"], str(entry_date))]
        st.session_state.pop("history_cache", None)
        st.session_state.pop("daily_save_notice", None)
        st.rerun()
replace_legacy = False
if draft.get("legacy"):
    replace_legacy = st.checkbox(
        "确认用当前输入替换旧摘要 · Replace older summary",
        key=f"replace_legacy_{entry_date}",
    )
st.session_state["replace_legacy"] = replace_legacy
if st.button("保存当天记录 · Save", type="primary", use_container_width=True,
             disabled=(bool(draft.get("legacy")) and not replace_legacy) or bool(draft.get("conflict"))):
    if save_daily_summary(entry_date, st.session_state.food_log, st.session_state.exercise_log, net_calories):
        st.rerun()

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["🍽️ Food Log · 饮食", "🔥 Exercise Log · 运动", "📜 Wellness History · 历史"])

with tab1:
    st.markdown('<h2 class="mb-section-title">🍽️ Food Log <small>饮食记录</small></h2>', unsafe_allow_html=True)
    if st.session_state.get("label_library_user") != st.session_state["username"]:
        try:
            personal_labels = load_personal_labels(get_sheet_connection("main"), st.session_state["username"])
        except Exception:
            logging.getLogger(__name__).exception("Optional personal labels unavailable")
            personal_labels = st.session_state.get("personal_labels", [])
        else:
            st.session_state["label_library_user"] = st.session_state["username"]
        for entry in st.session_state.food_log:
            personal_labels = remember_label(personal_labels, entry)
        st.session_state["personal_labels"] = personal_labels
    personal_labels = st.session_state.get("personal_labels", [])
    personal_by_food = {item["Food"]: item for item in personal_labels}
    food_database.update({name: {"Cals": item["Calories"], "Prot": item["Protein"],
                                "Carbs": item["Carbs"], "Fat": item["Fat"]}
                          for name, item in personal_by_food.items()})
    category = st.session_state.get("food_browse_category", ALL_FOODS)
    query = st.session_state.get("food_search", "")
    choices = filter_foods(food_database, category, query, st.session_state.get("recent_food_names", []))
    add_meal = False
    reference = personal_food = None
    if choices:
        if st.session_state.get("selected_food_id") not in choices:
            st.session_state["selected_food_id"] = choices[0]
        with st.form("add_food_form", clear_on_submit=False):
            meal_col, food_col, amount_col, add_col = st.columns([1.2, 3.2, 1, 1.25], vertical_alignment="bottom")
            with meal_col:
                meal = st.selectbox("餐次 · Meal", list(MEAL_LABELS), format_func=MEAL_LABELS.get)
            with food_col:
                food = st.selectbox("食物 · Food Item", choices, format_func=food_picker_label,
                                   key="selected_food_id", help="点击后可输入食物名称 · Type a food name to search")
            with amount_col:
                qty = st.number_input("份数 · Servings", min_value=0.01, value=1.0, step=0.25, format="%.2f")
            with add_col:
                add_meal = st.form_submit_button("Add Meal ＋", type="primary", use_container_width=True)
        reference = REFERENCE_RECORDS.get(food)
        personal_food = personal_by_food.get(food)
    else:
        st.info("没有找到这项食物。请在下方「更多选项」清除筛选或换个名称。 No matching food; clear the filter in More options.")

    if add_meal:
        st.session_state["recent_food_names"] = remember_food(st.session_state.get("recent_food_names", []), food)
        if personal_food:
            added_food = reuse_label(personal_food, meal, personal_food["Source"]["label_amount"] * qty)
        else:
            added_food = make_food_entry(food_database, food, meal, qty)
        change_entries(draft, "food", st.session_state.food_log + [added_food])
        st.rerun()

    if st.session_state.food_log:
        display_foods = pd.DataFrame(st.session_state.food_log).reindex(
            columns=["Meal", "Food", "Qty", "Calories"]
        )
        display_foods["Food"] = display_foods["Food"].map(food_picker_label)
        display_foods["Qty"] = [entry_amount_label(entry) for entry in st.session_state.food_log]
        display_foods["Meal"] = display_foods["Meal"].map(lambda value: MEAL_LABELS.get(value, value))
        st.dataframe(display_foods.rename(columns={
            "Meal": "餐次 Meal", "Food": "食物 Food", "Qty": "食用量 Amount", "Calories": "kcal",
            "Protein": "蛋白质 g", "Carbs": "碳水 g", "Fat": "脂肪 g",
        }), use_container_width=True, hide_index=True)
        st.caption(f"饮食合计 Food total: {format_energy(total_intake)} kcal")
        
        with st.expander("修改或删除一笔 · Edit food entry"):
            food_rows = st.session_state.food_log
            edit_index = st.selectbox("选择记录 · Entry", range(len(food_rows)),
                format_func=lambda i: f"{i + 1}. {MEAL_LABELS.get(food_rows[i]['Meal'], food_rows[i]['Meal'])} · {food_label(food_rows[i]['Food'])} · {entry_amount_label(food_rows[i])}",
                key=f"food_edit_index_{entry_date}")
            selected = food_rows[edit_index]
            meal_options = list(MEAL_LABELS)
            if selected["Meal"] not in meal_options:
                meal_options.append(selected["Meal"])
            selected_source = selected.get("Source", {})
            label_basis = selected_source.get("label_amount", 1.0) if selected_source.get("status") == "user_entered_package_label" else 1.0
            label_unit = selected_source.get("label_unit", "serving")
            amount_label = f"实际食用量 · Amount eaten ({label_unit})" if label_unit in {"g", "ml"} else "修改份数 · Servings"
            with st.form(f"food_edit_{entry_date}_{edit_index}_{selected['Qty']}"):
                updated_meal = st.selectbox("修改餐次 · Meal", meal_options,
                    index=meal_options.index(selected["Meal"]), format_func=lambda value: MEAL_LABELS.get(value, value))
                new_amount = st.number_input(amount_label, min_value=0.0,
                    value=float(selected["Qty"] * label_basis), step=0.5)
                update_food = st.form_submit_button("更新这一笔 · Update entry", use_container_width=True)
                delete_food = st.form_submit_button("删除这一笔 · Delete entry", use_container_width=True)
            if update_food:
                try:
                    updated = rescale_food(selected, new_amount / label_basis)
                    updated["Meal"] = updated_meal
                    changed = food_rows.copy()
                    changed[edit_index] = updated
                    change_entries(draft, "food", changed)
                except ValueError:
                    st.error("食用量必须大于零 · Enter an amount greater than zero.")
                else:
                    st.rerun()
            if delete_food:
                change_entries(draft, "food", food_rows[:edit_index] + food_rows[edit_index + 1:])
                st.session_state.pop(f"food_edit_index_{entry_date}", None)
                st.rerun()

    if st.session_state.food_log or draft.get("food_undo"):
        col_undo, col_clear = st.columns(2)
        with col_undo:
            if st.button("撤销上一笔 · Undo", use_container_width=True, disabled=not draft.get("food_undo")):
                undo_entries(draft, "food")
                st.rerun()
        with col_clear:
            if st.button("清空当天饮食 · Clear food", use_container_width=True, disabled=not st.session_state.food_log):
                change_entries(draft, "food", [])
                st.rerun()

    if st.button("保存当天记录 · Save day", key="save_bottom_food", type="primary", use_container_width=True,
                 disabled=(bool(draft.get("legacy")) and not replace_legacy) or bool(draft.get("conflict"))):
        if save_daily_summary(entry_date, st.session_state.food_log, st.session_state.exercise_log, net_calories):
            st.rerun()

    with st.expander("更多选项 · More options"):
        st.markdown("**搜索与分类 · Search & browse**")
        st.text_input("搜索食物 · Search food", placeholder="nasi lemak、鸡饭、炒面", key="food_search")
        st.selectbox("浏览范围 · Browse", [ALL_FOODS, RECENT_FOODS] + CATEGORIES, key="food_browse_category")
        if query.strip():
            st.caption("正在搜索全部食物 · Searching all foods")
        st.markdown("**我的食品 · My foods**")
        if personal_labels:
            st.caption("从你已保存的饮食记录恢复；当前新填标签在保存当天记录后可于下次登入使用。 Reuse your own labels. Save the day to keep new labels for your next sign-in.")
            templates = {template_key(item): item for item in personal_labels}
            if st.session_state.get("personal_label_choice") not in templates:
                st.session_state["personal_label_choice"] = next(iter(templates))
            personal_choice = st.selectbox("选择我的食品 · My food", list(templates),
                format_func=lambda key: templates[key]["Food"], key="personal_label_choice")
            template = templates[personal_choice]
            label_source = template["Source"]
            unit_label = "份 · Serving" if label_source["label_unit"] == "serving" else label_source["label_unit"]
            with st.form(f"reuse_label_{entry_date}_{personal_choice}"):
                reuse_meal = st.selectbox("餐次 · Meal", list(MEAL_LABELS), format_func=MEAL_LABELS.get)
                reuse_amount = st.number_input(f"这次食用量 · Amount eaten ({unit_label})", min_value=0.1,
                    value=float(label_source["label_amount"]), step=1.0)
                reuse_add = st.form_submit_button("添加我的食品 · Add my food", use_container_width=True)
            if reuse_add:
                change_entries(draft, "food", st.session_state.food_log + [reuse_label(template, reuse_meal, reuse_amount)])
                st.rerun()

        st.markdown("**自订食品（可选） · Custom food**")
        st.caption("填写同一栏的营养值，例如全部按每100g或每份；实际食用量使用相同单位。 Enter all nutrients from the same label column, using the same unit for the amount eaten.")
        label_unit = st.selectbox("标签单位 · Label unit", ["serving", "g", "ml"],
            format_func=lambda value: {"serving": "份 · Serving", "g": "克 · g", "ml": "毫升 · ml"}[value], key="label_unit")
        with st.form(f"package_label_{entry_date}_{label_unit}"):
            label_name = st.text_input("产品名称与口味 · Product & flavour", max_chars=120)
            label_meal = st.selectbox("餐次 · Meal", list(MEAL_LABELS), format_func=MEAL_LABELS.get, key="label_meal")
            label_basis = st.number_input("标签所列份量 · Label amount", min_value=0.1,
                value=1.0 if label_unit == "serving" else 100.0, step=1.0)
            label_eaten = st.number_input("实际食用量（相同单位） · Amount eaten", min_value=0.1,
                value=1.0 if label_unit == "serving" else 100.0, step=1.0)
            label_kcal = st.number_input("标签热量 · kcal（必填 · required）", min_value=0.0, value=None, step=1.0)
            st.caption("以下可留空；只有标签写明0才填写0。 Leave unknown values blank; enter zero only when stated on the label.")
            label_protein = st.number_input("标签蛋白质 · Protein g", min_value=0.0, value=None, step=0.1)
            label_carbs = st.number_input("标签碳水 · Carbohydrate g", min_value=0.0, value=None, step=0.1)
            label_fat = st.number_input("标签脂肪 · Fat g", min_value=0.0, value=None, step=0.1)
            label_add = st.form_submit_button("添加标签记录 · Add label entry", use_container_width=True)
        if label_add:
            try:
                label_entry = make_label_entry(label_name, label_meal, label_unit, label_basis,
                    label_eaten, label_kcal, label_protein, label_carbs, label_fat)
            except ValueError as exc:
                st.error(str(exc))
            else:
                change_entries(draft, "food", st.session_state.food_log + [label_entry])
                st.session_state["personal_labels"] = remember_label(st.session_state.get("personal_labels", []), label_entry)
                st.rerun()


        st.markdown("**食物资料 · Food details**")
        if choices:
            if personal_food:
                st.caption("你填写的包装标签资料，尚未独立核实。 Your own package-label values; not independently verified.")
            elif reference and reference.get("source_id") == "hpb_sgfoodid":
                st.markdown(f"[{SG_SOURCE['title']}]({reference['source_url']})")
                st.write(reference["original_name"])
                st.write(reference["description"])
                method_label = {"Lab Analysis": "实测资料 · Lab Analysis", "Derived": "推算资料 · Derived",
                                "Borrowed": "引用资料 · Borrowed", "NIP": "标签资料 · NIP"}.get(reference["method"], reference["method"])
                st.caption(f"食物编号 · Food code: {reference['food_code']} · Data year: {reference['data_year']} · {method_label}")
                st.caption("热量与营养值来自同一食物记录。 Energy and nutrients use the same source record.")
                if reference.get("portion_basis") == "edible_100g":
                    st.caption("此项采用来源公布的每100g可食部数值。 This entry uses the published 100g edible basis.")
                if reference["edible_portion_percent"] < 100:
                    st.caption("来源重量包括不可食部；营养值已按来源的可食部分计算。 Source weight includes inedible parts; published nutrients already account for the edible portion.")
            elif reference:
                source_url = SOURCE["url"] + f"#page={reference['pdf_page']}"
                st.markdown(f"[KKM Bank Kalori · PDF 第{reference['pdf_page']}页]({source_url})")
                st.write(reference["original_name"])
                code = reference["reference_code"]
                st.caption(f"原始参考 · Original reference: {code} — {SOURCE['reference_codes'][code]}")
                st.caption("这是指定份量的参考热量，摊位配方和实际份量会影响结果。 Reference energy is portion-specific; recipes and actual portions vary.")
                macro_source = reference.get("macronutrient_source")
                if macro_source:
                    st.markdown(f"[蛋白质、碳水与脂肪 · {macro_source['title']}]({macro_source['url']})")
                    st.caption("同名做法的每100g营养值按参考份量重量换算；不同配方仍有差异。 Matched preparation scaled by weight; recipes vary.")
                else:
                    st.caption("来源未提供蛋白质、碳水和脂肪；表格以 — 显示。 Macronutrients are not supplied by this source.")
            else:
                st.caption("原有交换份估算，逐项来源和重量待复核。 Original exchange estimate; item-level source and weight remain under review.")

        if st.session_state.food_log:
            st.markdown("**营养详情 · Nutrition details**")
            for nutrient, label in [("Protein", "蛋白质 Protein"), ("Carbs", "碳水 Carbs"), ("Fat", "脂肪 Fat")]:
                coverage = nutrient_coverage(st.session_state.food_log, nutrient)
                amount = format_energy(coverage["known_total"]) + " g" if coverage["missing_entries"] < coverage["entry_count"] else "—"
                suffix = "（部分资料 · partial）" if coverage["missing_entries"] else ""
                st.write(f"{label}: {amount} {suffix}")

with tab2:
    st.markdown('<h2 class="mb-section-title">🔥 Exercise Log <small>运动记录</small></h2>', unsafe_allow_html=True)
    with st.form("add_exercise_form", clear_on_submit=False):
        activity_col, time_col, action_col = st.columns([3.2, 1, 1.25], vertical_alignment="bottom")
        with activity_col:
            ex_name = st.selectbox("运动类型 · Activity", list(exercise_database.keys()))
        with time_col:
            ex_minutes = st.number_input("时长（分钟） · Duration", min_value=1, value=30, step=5)
        with action_col:
            add_activity = st.form_submit_button("添加运动 · Add activity", type="primary", use_container_width=True)

    if add_activity:
        change_entries(draft, "exercise", st.session_state.exercise_log + [{
            "Activity": ex_name, 
            "Duration": ex_minutes,
            "Calories Burned": exercise_database[ex_name] * ex_minutes / 30
        }])
        st.rerun()
        
    if st.session_state.exercise_log:
        st.dataframe(pd.DataFrame(st.session_state.exercise_log), use_container_width=True)
        st.caption(f"运动合计 Exercise total: {format_energy(total_burned)} kcal")
        
        with st.expander("修改或删除一笔 · Edit exercise entry"):
            exercise_rows = st.session_state.exercise_log
            edit_index = st.selectbox("选择运动 · Activity entry", range(len(exercise_rows)),
                format_func=lambda i: f"{i + 1}. {exercise_rows[i]['Activity']} · {exercise_rows[i]['Duration']:g} min",
                key=f"exercise_edit_index_{entry_date}")
            selected = exercise_rows[edit_index]
            with st.form(f"exercise_edit_{entry_date}_{edit_index}_{selected['Duration']}"):
                new_minutes = st.number_input("运动分钟 · Minutes", min_value=1.0, value=float(selected["Duration"]), step=5.0)
                update_activity = st.form_submit_button("更新时长 · Update duration", use_container_width=True)
                delete_activity = st.form_submit_button("删除这一笔运动 · Delete activity", use_container_width=True)
            if update_activity:
                changed = exercise_rows.copy()
                changed[edit_index] = rescale_exercise(selected, new_minutes)
                change_entries(draft, "exercise", changed)
                st.rerun()
            if delete_activity:
                change_entries(draft, "exercise", exercise_rows[:edit_index] + exercise_rows[edit_index + 1:])
                st.session_state.pop(f"exercise_edit_index_{entry_date}", None)
                st.rerun()

    if st.session_state.exercise_log or draft.get("exercise_undo"):
        col_undo, col_clear = st.columns(2)
        with col_undo:
            if st.button("撤销上一笔运动 · Undo activity", use_container_width=True, disabled=not draft.get("exercise_undo")):
                undo_entries(draft, "exercise")
                st.rerun()
        with col_clear:
            if st.button("清空当天运动 · Clear exercise", use_container_width=True, disabled=not st.session_state.exercise_log):
                change_entries(draft, "exercise", [])
                st.rerun()

    if st.button("保存当天记录 · Save day", key="save_bottom_exercise", type="primary", use_container_width=True,
                 disabled=(bool(draft.get("legacy")) and not replace_legacy) or bool(draft.get("conflict"))):
        if save_daily_summary(entry_date, st.session_state.food_log, st.session_state.exercise_log, net_calories):
            st.rerun()

with tab3:
    st.markdown('<h2 class="mb-section-title">📜 Your Wellness History <small>我的生活记录</small></h2>', unsafe_allow_html=True)
    render_note_history(get_sheet_connection, st.session_state["username"], notes=all_student_notes)
    refresh_history = st.button("更新历史 · Refresh history")
    try:
        cache = st.session_state.get("history_cache")
        if refresh_history or not cache or cache["username"] != st.session_state["username"] or monotonic() - cache["time"] > 60:
            records = load_history(get_sheet_connection("main"), st.session_state["username"])
            cache = {"username": st.session_state["username"], "time": monotonic(), "records": records}
            st.session_state["history_cache"] = cache
        history_notes = all_student_notes
        if history_notes is None:
            st.warning('补充记录暂时无法核对；下方仅显示已计热量。 Supplementary records could not be checked.')
        records = annotate_energy_status(cache["records"], history_notes)
        if not records:
            st.info("还没有已保存记录。添加饮食或运动后请保存。 No saved history yet.")
        else:
            st.download_button("导出已保存历史 · Export history (CSV)",
                data=export_history_csv(records), file_name="may-bloom-history.csv", mime="text/csv", on_click="ignore")
            history = pd.DataFrame(records)
            display = history[["Date", "Net_Calories"]].copy()
            display['记录状态 Status'] = ['已计入 · Counted' if r['Energy_complete'] is True
                else '热量待补充 · Incomplete' if r['Energy_complete'] is False else '待核对 · Unchecked' for r in records]
            st.dataframe(display.rename(columns={"Date": "日期 Date", "Net_Calories": "净热量 Net kcal"}),
                         use_container_width=True, hide_index=True)
            chart = history[history['Energy_complete'].eq(True)].dropna(subset=["Net_Calories"]).sort_values("Date")
            if not chart.empty:
                chart = chart.assign(Date=pd.to_datetime(chart["Date"]))
                st.line_chart(chart, x="Date", y="Net_Calories", color="#cf6d8b")
            with st.expander("查看某一天 · Daily details"):
                history_day = st.selectbox("已保存日期 · Saved date", [row["Date"] for row in records], key="history_day")
                row = next(row for row in records if row["Date"] == history_day)
                st.write("饮食 Food: " + str(row["Food_Log"]))
                st.write("运动 Exercise: " + str(row["Exercise_Log"]))
                if row["status"] == "legacy":
                    st.caption("旧摘要没有完整营养明细。 Older summaries do not contain full nutrient details.")
                elif row["status"] == "invalid_details":
                    st.warning("此日明细格式需检查；原摘要仍保留。 Detailed data needs review; the summary is preserved.")
                elif row["missing_protein_entries"]:
                    st.caption(f"蛋白质尚有 {row['missing_protein_entries']} 项缺资料 · foods missing protein data")
                st.button("打开这一天 · Open day", on_click=open_history_day, args=(history_day,))
    except Exception:
        logging.getLogger(__name__).exception("History load failed")
        st.error("暂时无法读取历史，当前输入仍保留。请稍后更新历史。 History unavailable; your current draft is preserved.")
