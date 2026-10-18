import streamlit as st
import pandas as pd
import gspread
import logging
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime
from zoneinfo import ZoneInfo
from time import monotonic
from tracker_state import logout, select_draft, daily_signature, change_entries, undo_entries
from entry_editor import rescale_food, rescale_exercise, nutrient_coverage
from label_entry import make_label_entry, entry_amount_label
from label_library import load_personal_labels, remember_label, template_key, reuse_label
from tracker_storage import load_day, save_day, day_snapshot, SaveConflictError
from tracker_history import load_history
from tracker_export import export_history_csv, export_draft
from profile_storage import ACTIVITIES, load_profile, save_profile
from nutrition_registry import SOURCE, SG_SOURCE, REFERENCE_RECORDS, reference_database, reference_portion, make_food_entry, format_energy
from food_catalogue import ALL_FOODS, RECENT_FOODS, CATEGORIES, MEAL_LABELS, food_label, filter_foods, remember_food

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="May Bloom Advanced", page_icon="🌸", layout="wide")

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
    elif type == "feedback":
        try:
            sheet = spreadsheet.worksheet("feedback")
        except gspread.WorksheetNotFound:
            return None # Feedback tab doesn't exist
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
        st.caption("首次使用：请确认身高、体重和活动水平，再保存。 First visit: check the default values and save.")
    elif current_profile != baseline:
        st.caption("有未保存的个人资料修改。 Unsaved profile changes.")
    else:
        st.caption("个人资料已保存，重新登入会自动载入。 Saved profile loads after sign-in.")
    st.caption("饮食和运动记录请使用主页面的「保存当天记录」。 Save daily food and exercise separately on the main page.")
    st.divider()
    return current_profile

# --- 3. SECURE LOGIN SYSTEM ---
def check_password():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if st.session_state["logged_in"]:
        return True

    st.markdown("<h1 style='text-align: center; color: #9B3E59;'>🌸 May Bloom Login</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.info("Please sign in to access your tracker.")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        
        if st.button("🌸 Log In", key="login_btn", use_container_width=True):
            if username in st.secrets["passwords"] and password == st.secrets["passwords"][username]:
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.rerun()
            else:
                st.error("Incorrect username or password.")
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
        
        # Admin Feedback Check (To test if the blue box works)
        try:
            feedback_sheet = get_sheet_connection("feedback")
            if feedback_sheet:
                fb_data = feedback_sheet.get_all_records()
                fb_df = pd.DataFrame(fb_data)
                
                if not fb_df.empty and "username" in fb_df.columns:
                    # Check if 'admin' has a note
                    user_fb = fb_df[fb_df["username"] == "admin"]
                    if not user_fb.empty:
                        last_note = user_fb.iloc[-1]
                        st.info(f"💌 **Test Note ({last_note['month']}):**\n\n{last_note['note']}")
        except:
            pass

        st.divider()
        if st.button("Log Out Admin"):
            logout(st.session_state)
            st.rerun()
    # --- ADMIN SIDEBAR END ---

    st.title("👑 Admin Dashboard")
    st.success("Welcome, Coach! Here is the master view.")
    
    try:
        sheet = get_sheet_connection("main")
        data = sheet.get_all_records()
        df_master = pd.DataFrame(data)
        
        if df_master.empty:
            st.warning("⚠️ Google Sheet is empty.")
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Entries", len(df_master))
            col2.metric("Total Clients", df_master['username'].nunique())
            col3.metric("Latest Entry", df_master.iloc[-1]['Date'] if 'Date' in df_master.columns else "N/A")
            
            st.subheader("📋 Client Logs")
            st.dataframe(df_master.drop(columns=["Food_JSON", "Exercise_JSON"], errors="ignore"), use_container_width=True)
            
            st.info("💡 Tip: To give feedback, go to the 'feedback' tab in Google Sheets and add a row for your client!")

    except Exception as e:
        st.error(f"System Error: {e}")
        
    st.stop() 

# ==========================================
# PART 5: REGULAR CLIENT APP
# ==========================================

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .block-container { max-width: 960px; padding-top: 5rem; padding-bottom: 3rem; }
    .mb-brand { display:flex; align-items:center; gap:.55rem; margin:0 0 .15rem; }
    .mb-brand-name { font-size:1.65rem; font-weight:700; color:var(--text-color, #49333c); line-height:1.3; }
    .mb-brand-mark { color:#a54460; font-size:1.5rem; }
    .mb-subtitle { color:var(--text-color, #68585f); font-size:.9rem; margin:0 0 .75rem; }
    .mb-summary { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.55rem; margin:.2rem 0; }
    .mb-stat { margin:0; padding:.75rem .6rem; border:1px solid #edd7de; border-radius:14px; background:#fcf5f7; min-width:0; }
    .mb-stat dt { font-size:.8rem; color:#68515b; margin:0 0 .25rem; }
    .mb-stat dd { font-size:clamp(1.05rem,4.8vw,1.8rem); font-weight:700; color:#49333c; margin:0; overflow-wrap:anywhere; }
    .mb-stat small { display:block; font-size:.72rem; font-weight:400; color:#68515b; margin-top:.1rem; }
    .mb-stat-net { background:#f5e6ec; border-color:#dba6b6; }
    [data-testid="stButton"] button,
    [data-testid="stFormSubmitButton"] button { min-height:44px; border-radius:10px; }
    [data-testid="stButton"] button[kind="primary"],
    button[data-testid="baseButton-primary"],
    [data-testid="stFormSubmitButton"] button {
        background:#9b3e59 !important; border-color:#9b3e59 !important; color:#fff !important;
    }
    [data-testid="stButton"] button[kind="primary"]:hover,
    button[data-testid="baseButton-primary"]:hover,
    [data-testid="stFormSubmitButton"] button:hover {
        background:#803249 !important; border-color:#803249 !important; color:#fff !important;
    }
    [data-testid="stButton"] button[kind="primary"]:disabled,
    button[data-testid="baseButton-primary"]:disabled,
    [data-testid="stFormSubmitButton"] button:disabled {
        background:#eee5e8 !important; border-color:#ddd0d5 !important; color:#71636a !important;
    }
    @media (max-width:640px) {
        .block-container { padding-left:1rem; padding-right:1rem; padding-top:5rem; }
        .mb-brand-name { font-size:1.4rem; }
        [data-testid="stForm"] { padding:.8rem; }
        [data-testid="stTabs"] [role="tab"] { min-height:44px; padding-left:.4rem; padding-right:.4rem; }
    }

</style>
""", unsafe_allow_html=True)

# --- DAILY DRAFT ---
st.subheader("✿ May Bloom")
st.caption("Lifestyle Tracker · 生活记录")
entry_date = st.date_input("日期 · Date of entry", datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).date(), key="entry_date")
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
    st.write("已保存的记录会在登入后载入。修改后请保存；未保存的修改可能在离开后丢失。 Saved records load after sign-in. Save after editing; unsaved changes may be lost when you leave.")
    st.caption("本次会话可分别撤销最近20次饮食和运动修改，包括删除和清空。 Undo supports the last 20 food and exercise changes in this session.")
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
    st.image("https://cdn-icons-png.flaticon.com/512/3050/3050484.png", width=80)
    st.header(f"👤 {st.session_state['username'].title()}")
    
    # --- 💌 COACH FEEDBACK ---
    try:
        feedback_sheet = get_sheet_connection("feedback")
        if feedback_sheet:
            fb_data = feedback_sheet.get_all_records()
            fb_df = pd.DataFrame(fb_data)
            
            if not fb_df.empty and "username" in fb_df.columns:
                user_fb = fb_df[fb_df["username"] == st.session_state["username"]]
                if not user_fb.empty:
                    last_note = user_fb.iloc[-1]
                    st.info(f"💌 **Coach's Note ({last_note['month']}):**\n\n{last_note['note']}")
    except:
        pass 
    # -------------------------

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

st.markdown(
    f'<div class="mb-summary" role="group" aria-label="每日热量 Daily calories">'
    f'<dl class="mb-stat"><dt>饮食 Food</dt><dd>{format_energy(total_intake)}<small>kcal</small></dd></dl>'
    f'<dl class="mb-stat"><dt>运动 Exercise</dt><dd>{format_energy(total_burned)}<small>kcal</small></dd></dl>'
    f'<dl class="mb-stat mb-stat-net"><dt>净值 Net</dt><dd>{format_energy(net_calories)}<small>kcal</small></dd></dl>'
    f'</div>',
    unsafe_allow_html=True,
)
if daily_needs is not None:
    progress = min(max(net_calories / daily_needs, 0.0), 1.0)
    st.progress(progress)
    if remaining < 0:
        st.caption(f"高于当前目标 Above target: {format_energy(abs(remaining))} kcal")
    else:
        st.caption(f"距当前目标 Remaining: {format_energy(remaining)} kcal")

else:
    st.caption("个人资料暂不可用，当前不显示热量目标。 Energy target unavailable until your profile loads.")

if st.session_state.food_log:
    protein = nutrient_coverage(st.session_state.food_log, "Protein")
    if protein["missing_entries"] == protein["entry_count"]:
        st.info("蛋白质：这些餐食尚未提供资料 · Protein data unavailable for these foods")
    elif protein["missing_entries"]:
        st.info(f"蛋白质已知部分 · Known protein: {format_energy(protein['known_total'])} g；另有 {protein['missing_entries']} 项未提供 · foods missing data")
    else:
        st.info(f"已记录蛋白质 · Recorded protein: {format_energy(protein['known_total'])} g（参考估算 · estimate）")
    with st.expander("营养合计与完整度 · Nutrient totals"):
        st.caption("以下为已知部分的合计；缺资料时不能视为全天总量。 Totals cover known values only.")
        for nutrient, label in [("Protein", "蛋白质 Protein"), ("Carbs", "碳水 Carbs"), ("Fat", "脂肪 Fat")]:
            coverage = nutrient_coverage(st.session_state.food_log, nutrient)
            amount = format_energy(coverage["known_total"]) + " g" if coverage["missing_entries"] < coverage["entry_count"] else "—"
            st.write(f"{label}: {amount} · {coverage['entry_count'] - coverage['missing_entries']}/{coverage['entry_count']} 项有资料")

if daily_signature(st.session_state.food_log, st.session_state.exercise_log) != draft.get("saved_signature"):
    st.warning("有未保存的修改 · Unsaved changes")
elif st.session_state.pop("daily_save_notice", None) == str(entry_date):
    st.success(f"已保存 Saved · {entry_date}")

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
tab1, tab2, tab3 = st.tabs(["饮食 Food", "运动 Exercise", "历史 History"])

with tab1:
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
    if personal_labels:
        with st.expander("我的包装食品 · My label foods"):
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
    query = st.text_input(
        "吃了什么？ · Search food", placeholder="直接输入：nasi lemak、鸡饭、炒面",
        key="food_search",
    )
    with st.expander("分类与最近使用（可选） · Browse"):
        category = st.selectbox(
            "浏览范围 · Browse", [ALL_FOODS, RECENT_FOODS] + CATEGORIES,
            key="food_browse_category",
        )
    if query.strip():
        st.caption("正在搜索全部食物 · Searching all foods")
    elif category != ALL_FOODS:
        st.caption(f"当前浏览 · Browsing: {category}")
    choices = filter_foods(
        food_database, category, query, st.session_state.get("recent_food_names", [])
    )
    if category == RECENT_FOODS and not query.strip():
        st.caption("本次登入选择或载入过的食物，最多8项。 Up to 8 foods used or loaded during this sign-in.")
    add_meal = False
    if choices:
        if st.session_state.get("selected_food_id") not in choices:
            st.session_state["selected_food_id"] = choices[0]
        food = st.selectbox(
            "食物 · Food", choices, format_func=food_label, key="selected_food_id"
        )
        reference = REFERENCE_RECORDS.get(food)
        personal_food = personal_by_food.get(food)
        if personal_food:
            label_source = personal_food["Source"]
            st.caption(f"我的包装标签 · My package label: {label_source['label_amount']:g} {label_source['label_unit']} · {format_energy(personal_food['Calories'])} kcal")
        if reference:
            amount, unit = reference_portion(reference)
            st.caption(f"参考1份 · Reference serving: {amount:g} {unit} · {reference['energy_kcal']:g} kcal")
            if reference.get("source_id") == "hpb_sgfoodid":
                st.caption("新加坡 HPB 食物参考；品种、品牌和做法可能不同。 Singapore food reference; varieties, brands and recipes vary.")
        selected_protein = food_database[food]["Prot"]
        if selected_protein is None:
            st.caption("每份蛋白质：暂缺资料 · Protein per serving: unavailable")
        else:
            st.caption(f"每份蛋白质 · Protein per serving: {format_energy(selected_protein)} g（参考估算）")
        with st.expander("份量与资料来源 · Portion & source"):
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
        with st.form("add_food_form", clear_on_submit=False):
            meal = st.selectbox(
                "餐次 · Meal", list(MEAL_LABELS), format_func=MEAL_LABELS.get
            )
            if personal_food:
                label_source = personal_food["Source"]
                personal_amount = st.number_input(f"食用量 · Amount eaten ({label_source['label_unit']})",
                    min_value=0.1, value=float(label_source["label_amount"]), step=1.0,
                    key=f"personal_search_amount_{template_key(personal_food)}")
            else:
                qty = st.number_input("份数 · Servings", min_value=0.01, value=1.0, step=0.25, format="%.2f")
                st.caption("1份 = 上方标示份量；半份填0.5，四分之一份填0.25。可直接输入。 One serving follows the portion above; enter the amount eaten.")
            add_meal = st.form_submit_button("添加饮食 · Add meal", type="primary", use_container_width=True)
    elif category == RECENT_FOODS and not query.strip() and not st.session_state.get("recent_food_names"):
        st.info("还没有最近使用的食物，请先选其他分类添加。 No recent foods yet; choose another category to start.")
    else:
        st.info("食物库暂时没有符合的餐食，可换中文、英文或马来文名称再找。 No matching food yet; try another name.")
        
    if add_meal:
        st.session_state["recent_food_names"] = remember_food(
            st.session_state.get("recent_food_names", []), food
        )
        if personal_by_food.get(food):
            added_food = reuse_label(personal_by_food[food], meal, personal_amount)
        else:
            added_food = make_food_entry(food_database, food, meal, qty)
        change_entries(draft, "food", st.session_state.food_log + [added_food])
        st.rerun()

    with st.expander("找不到包装食品？按标签添加 · Add from package label"):
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

    if st.session_state.food_log:
        display_foods = pd.DataFrame(st.session_state.food_log).reindex(
            columns=["Meal", "Food", "Qty", "Calories", "Protein", "Carbs", "Fat"]
        )
        display_foods["Food"] = display_foods["Food"].map(food_label)
        display_foods["Qty"] = [entry_amount_label(entry) for entry in st.session_state.food_log]
        display_foods["Meal"] = display_foods["Meal"].map(lambda value: MEAL_LABELS.get(value, value))
        st.dataframe(display_foods.rename(columns={
            "Meal": "餐次 Meal", "Food": "食物 Food", "Qty": "食用量 Amount", "Calories": "kcal",
            "Protein": "蛋白质 g", "Carbs": "碳水 g", "Fat": "脂肪 g",
        }), use_container_width=True, hide_index=True)
        st.caption(f"饮食合计 Food total: {format_energy(total_intake)} kcal")
        st.caption("— 表示未提供该项营养数值，不代表零。 A dash means not available, not zero.")
        
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

with tab2:
    with st.form("add_exercise_form", clear_on_submit=False):
        ex_name = st.selectbox("运动类型 · Activity", list(exercise_database.keys()))
        ex_minutes = st.number_input("时长（分钟） · Duration", min_value=1, value=30, step=5)
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
    st.subheader("历史记录 · History")
    st.caption("只显示已保存记录；当前未保存的修改不包括在内。 Saved records only; drafts are excluded.")
    refresh_history = st.button("更新历史 · Refresh history")
    try:
        cache = st.session_state.get("history_cache")
        if refresh_history or not cache or cache["username"] != st.session_state["username"] or monotonic() - cache["time"] > 60:
            records = load_history(get_sheet_connection("main"), st.session_state["username"])
            cache = {"username": st.session_state["username"], "time": monotonic(), "records": records}
            st.session_state["history_cache"] = cache
        records = cache["records"]
        if not records:
            st.info("还没有已保存记录。添加饮食或运动后请保存。 No saved history yet.")
        else:
            st.download_button("导出已保存历史 · Export history (CSV)",
                data=export_history_csv(records), file_name="may-bloom-history.csv", mime="text/csv", on_click="ignore")
            history = pd.DataFrame(records)
            display = history[["Date", "Net_Calories"]].copy()
            protein_labels = []
            for row in records:
                if row["status"] != "detailed" or row["missing_protein_entries"] == row["food_entries"] and row["food_entries"]:
                    protein_labels.append("— 未提供")
                elif row["missing_protein_entries"]:
                    protein_labels.append(f"{format_energy(row['known_protein'])} g（部分 · partial）")
                else:
                    protein_labels.append(f"{format_energy(row['known_protein'])} g")
            display["蛋白质 Protein"] = protein_labels
            st.dataframe(display.rename(columns={"Date": "日期 Date", "Net_Calories": "净热量 Net kcal"}),
                         use_container_width=True, hide_index=True)
            chart = history.dropna(subset=["Net_Calories"]).sort_values("Date")
            if not chart.empty:
                chart = chart.assign(Date=pd.to_datetime(chart["Date"]))
                st.line_chart(chart, x="Date", y="Net_Calories")
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
