import streamlit as st
import pandas as pd
import gspread
import logging
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date
from tracker_state import logout, select_draft
from tracker_storage import load_day, save_day
from profile_storage import ACTIVITIES, load_profile, save_profile

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
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["service_account"]), scope)
    client = gspread.authorize(creds)
    
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    
    if type == "profiles":
        try:
            return spreadsheet.worksheet("profiles")
        except gspread.WorksheetNotFound:
            if create:
                return spreadsheet.add_worksheet(title="profiles", rows=100, cols=5)
            return None
    if type == "feedback":
        try:
            return spreadsheet.worksheet("feedback")
        except:
            return None # Feedback tab doesn't exist
    else:
        # "get_worksheet(0)" always grabs the first tab
        return spreadsheet.get_worksheet(0)

def format_log_to_string(log_list, type="food"):
    if not log_list: return "None"
    text_summary = []
    for item in log_list:
        if type == "food":
            text_summary.append(f"{item['Meal']}: {item['Food']} (x{item['Qty']})")
        else:
            text_summary.append(f"{item['Activity']} ({item['Duration']} mins)")
    return ", ".join(text_summary)

def save_daily_summary(selected_date, food_log, exercise_log, net_calories):
    try:
        sheet = get_sheet_connection("main")
        save_day(
            sheet, st.session_state["username"], selected_date,
            food_log, exercise_log, net_calories,
            format_log_to_string(food_log, type="food"),
            format_log_to_string(exercise_log, type="exercise"),
            replace_legacy=st.session_state.get("replace_legacy", False),
        )
        st.session_state["daily_drafts"][(st.session_state["username"], str(selected_date))]["legacy"] = False
        return True
    except Exception as e:
        st.error(f"Error saving to cloud: {e}")
        return False

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

    st.markdown("<h1 style='text-align: center; color: #FF69B4;'>🌸 May Bloom Login</h1>", unsafe_allow_html=True)
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
entry_date = st.date_input("📅 Date of Entry", date.today())
draft = select_draft(st.session_state, st.session_state["username"], entry_date)
if not draft.get("loaded"):
    try:
        saved = load_day(get_sheet_connection("main"), st.session_state["username"], entry_date)
        draft["food_log"][:] = saved["food_log"]
        draft["exercise_log"][:] = saved["exercise_log"]
        draft["legacy"] = saved["legacy"]
        draft["summary"] = saved.get("summary")
        draft["loaded"] = True
    except Exception:
        st.error("Could not load saved records. Check your connection and try again. Editing is paused to protect existing records.")
        if st.button("Retry loading records"):
            st.rerun()
        st.stop()
with st.expander("使用提示 · How to use"):
    st.write("已保存的记录会在登入后载入。修改后请保存；未保存的修改可能在离开后丢失。 Saved records load after sign-in. Save after editing; unsaved changes may be lost when you leave.")
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
    total_intake = f_df["Calories"].sum()
else:
    total_intake = 0

if st.session_state.exercise_log:
    e_df = pd.DataFrame(st.session_state.exercise_log)
    total_burned = e_df["Calories Burned"].sum()
else:
    total_burned = 0

net_calories = total_intake - total_burned
remaining = daily_needs - net_calories if daily_needs is not None else None

st.markdown(
    f'<div class="mb-summary" role="group" aria-label="每日热量 Daily calories">'
    f'<dl class="mb-stat"><dt>饮食 Food</dt><dd>{int(total_intake):,}<small>kcal</small></dd></dl>'
    f'<dl class="mb-stat"><dt>运动 Exercise</dt><dd>{int(total_burned):,}<small>kcal</small></dd></dl>'
    f'<dl class="mb-stat mb-stat-net"><dt>净值 Net</dt><dd>{int(net_calories):,}<small>kcal</small></dd></dl>'
    f'</div>',
    unsafe_allow_html=True,
)
if daily_needs is not None:
    progress = min(max(net_calories / daily_needs, 0.0), 1.0)
    st.progress(progress)
    if remaining < 0:
        st.caption(f"高于当前目标 Above target: {abs(int(remaining)):,} kcal")
    else:
        st.caption(f"距当前目标 Remaining: {int(remaining):,} kcal")

else:
    st.caption("个人资料暂不可用，当前不显示热量目标。 Energy target unavailable until your profile loads.")

# --- SAVE TO CLOUD BUTTON ---
replace_legacy = False
if draft.get("legacy"):
    replace_legacy = st.checkbox(
        "确认用当前输入替换旧摘要 · Replace older summary",
        key=f"replace_legacy_{entry_date}",
    )
st.session_state["replace_legacy"] = replace_legacy
if st.button("保存当天记录 · Save", type="primary", use_container_width=True,
             disabled=bool(draft.get("legacy")) and not replace_legacy):
    if save_daily_summary(entry_date, st.session_state.food_log, st.session_state.exercise_log, net_calories):
        st.success(f"已保存 Saved · {entry_date}")

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["饮食 Food", "运动 Exercise", "历史 History"])

with tab1:
    with st.form("add_food_form", clear_on_submit=False):
        meal = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snack"])
        food = st.selectbox("Food Item", list(food_database.keys()))
        qty = st.selectbox("Serving", [0.5, 1.0, 1.5, 2.0, 2.5, 3.0], index=1)
        add_meal = st.form_submit_button("添加饮食 · Add meal", type="primary", use_container_width=True)
        
    if add_meal:
        st.session_state.food_log.append({
            "Meal": meal, "Food": food, "Qty": qty, 
            "Calories": food_database[food]["Cals"] * qty,
            "Protein": food_database[food]["Prot"] * qty,
            "Carbs": food_database[food]["Carbs"] * qty,
            "Fat": food_database[food]["Fat"] * qty
        })
        st.rerun()

    if st.session_state.food_log:
        st.dataframe(pd.DataFrame(st.session_state.food_log), use_container_width=True)
        st.caption(f"饮食合计 Food total: {int(total_intake):,} kcal")
        
        col_undo, col_clear = st.columns(2)
        with col_undo:
            if st.button("Undo Last Entry ↩️", use_container_width=True):
                st.session_state.food_log.pop()
                st.rerun()
        with col_clear:
            if st.button("Clear All Food 🗑️", use_container_width=True):
                st.session_state.food_log.clear()
                st.rerun()

with tab2:
    with st.form("add_exercise_form", clear_on_submit=False):
        ex_name = st.selectbox("Activity Type", list(exercise_database.keys()))
        ex_minutes = st.selectbox("Duration (minutes)", [15, 30, 45, 60, 75, 90], index=1)
        add_activity = st.form_submit_button("添加运动 · Add activity", type="primary", use_container_width=True)

    if add_activity:
        st.session_state.exercise_log.append({
            "Activity": ex_name, 
            "Duration": ex_minutes,
            "Calories Burned": exercise_database[ex_name] * ex_minutes / 30
        })
        st.rerun()
        
    if st.session_state.exercise_log:
        st.dataframe(pd.DataFrame(st.session_state.exercise_log), use_container_width=True)
        st.caption(f"运动合计 Exercise total: {int(total_burned):,} kcal")
        
        col_undo, col_clear = st.columns(2)
        with col_undo:
            if st.button("Undo Last Activity ↩️", use_container_width=True):
                st.session_state.exercise_log.pop()
                st.rerun()
        with col_clear:
            if st.button("Clear All Exercise 🗑️", use_container_width=True):
                st.session_state.exercise_log.clear()
                st.rerun()

with tab3:
    st.subheader("历史记录 · History")
    try:
        sheet = get_sheet_connection("main")
        data = sheet.get_all_records()
        df_history = pd.DataFrame(data)
        
        if df_history.empty:
            st.info("No history found yet. Save your first entry!")
        elif "username" in df_history.columns:
            my_history = df_history[df_history["username"] == st.session_state["username"]]
            if my_history.empty:
                st.warning("No records found for your username.")
            else:
                st.dataframe(my_history.drop(columns=["username", "Food_JSON", "Exercise_JSON"], errors="ignore"), use_container_width=True)
                if not my_history.empty:
                    st.line_chart(my_history, x="Date", y="Net_Calories")
    except Exception as e:
        st.error(f"Could not load history: {e}")
