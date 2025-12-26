import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="May Bloom Advanced", page_icon="🌸", layout="wide")

# --- 2. GOOGLE SHEETS CONNECTION ---
SHEET_NAME = "wellness_database"

def get_sheet_connection(type="main"):
    """
    Connects to Google Sheets.
    type="main" -> Returns the FIRST tab (your data logs)
    type="feedback" -> Returns the 'feedback' tab
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["service_account"]), scope)
    client = gspread.authorize(creds)
    
    spreadsheet = client.open(SHEET_NAME)
    
    if type == "feedback":
        try:
            return spreadsheet.worksheet("feedback")
        except:
            return None # Feedback tab doesn't exist
    else:
        # "get_worksheet(0)" always grabs the first tab, no matter if it's named "Sheet1" or "sheet1"
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
        # Save to the main log sheet (First Tab)
        sheet = get_sheet_connection("main")
        food_str = format_log_to_string(food_log, type="food")
        exercise_str = format_log_to_string(exercise_log, type="exercise")
        
        new_row = [str(selected_date), food_str, exercise_str, net_calories, st.session_state["username"]]
        sheet.append_row(new_row)
        return True
    except Exception as e:
        st.error(f"Error saving to cloud: {e}")
        return False

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
            st.dataframe(df_master, use_container_width=True)
            
            st.info("💡 Tip: To give feedback, go to the 'feedback' tab in Google Sheets and add a row for your client!")

    except Exception as e:
        st.error(f"System Error: {e}")
        
    if st.button("Log Out Admin"):
        st.session_state["logged_in"] = False
        st.rerun()
    st.stop() 

# ==========================================
# PART 5: REGULAR CLIENT APP
# ==========================================

# --- CUSTOM CSS ---
st.markdown("""
<style>
    [data-testid="stMetric"] { background-color: #FFF0F5; border-radius: 10px; padding: 10px; border: 1px solid #FFB6C1; }
    div.stButton > button { background-color: #FFB6C1; color: white; border: none; }
</style>
""", unsafe_allow_html=True)

# --- INITIALIZE STATES ---
if 'food_log' not in st.session_state: st.session_state.food_log = []
if 'exercise_log' not in st.session_state: st.session_state.exercise_log = []

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
    
    height_cm = st.number_input("Height (cm)", 100.0, 200.0, 160.0)
    weight_kg = st.number_input("Weight (kg)", 30.0, 200.0, 70.0)
    activity = st.selectbox("Activity Level", ["Sedentary (x25)", "Active (x30)"])
    st.divider()
    
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
        st.session_state["logged_in"] = False
        st.rerun()

# --- MAIN DASHBOARD ---
st.title("🌸 May Bloom Lifestyle Tracker")

entry_date = st.date_input("📅 Date of Entry", date.today())

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
remaining = daily_needs - net_calories

col1, col2, col3 = st.columns(3)
col1.metric("🍽️ Food Intake", f"{int(total_intake)} kcal")
col2.metric("🔥 Exercise Burn", f"-{int(total_burned)} kcal")
col3.metric("⚖️ Net Calories", f"{int(net_calories)} kcal", delta=f"{int(remaining)} left")

st.write("Daily Energy Progress:")
progress = min(max(net_calories / daily_needs, 0.0), 1.0)
st.progress(progress)

if remaining < 0:
    st.error(f"⚠️ Over budget by {abs(int(remaining))} kcal!")
else:
    st.info(f"✅ {int(remaining)} kcal remaining.")

# --- SAVE TO CLOUD BUTTON ---
st.markdown("---")
if st.button("☁️ Save Daily Summary to Cloud", use_container_width=True):
    if save_daily_summary(entry_date, st.session_state.food_log, st.session_state.exercise_log, net_calories):
        st.success(f"Daily summary for {entry_date} saved to Google Sheets!")
        st.balloons()

# --- TABS ---
st.divider()
tab1, tab2, tab3 = st.tabs(["🍽️ Food Log", "🏃‍♀️ Exercise Log", "📅 History"])

with tab1:
    c1, c2, c3 = st.columns([2,2,1])
    with c1:
        meal = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snack"])
    with c2:
        food = st.selectbox("Food Item", list(food_database.keys()))
    with c3:
        qty = st.selectbox("Serving", [0.5, 1.0, 1.5, 2.0, 2.5, 3.0], index=1)
        
    if st.button("Add Meal ➕", use_container_width=True):
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
        st.info(f"🍽️ **Total Calories in this list:** {int(total_intake)} kcal")
        
        col_undo, col_clear = st.columns(2)
        with col_undo:
            if st.button("Undo Last Entry ↩️", use_container_width=True):
                st.session_state.food_log.pop()
                st.rerun()
        with col_clear:
            if st.button("Clear All Food 🗑️", use_container_width=True):
                st.session_state.food_log = []
                st.rerun()

with tab2:
    c1, c2 = st.columns([3,1])
    with c1:
        ex_name = st.selectbox("Activity Type", list(exercise_database.keys()))
    with c2:
        ex_dur = st.selectbox("Duration (30 mins)", [0.5, 1.0, 1.5, 2.0, 2.5, 3.0], index=1)

    if st.button("Add Activity ➕", use_container_width=True):
        st.session_state.exercise_log.append({
            "Activity": ex_name, 
            "Duration": ex_dur * 30, 
            "Calories Burned": exercise_database[ex_name] * ex_dur
        })
        st.rerun()
        
    if st.session_state.exercise_log:
        st.dataframe(pd.DataFrame(st.session_state.exercise_log), use_container_width=True)
        st.info(f"🔥 **Total Calories Burned:** {int(total_burned)} kcal")
        
        col_undo, col_clear = st.columns(2)
        with col_undo:
            if st.button("Undo Last Activity ↩️", use_container_width=True):
                st.session_state.exercise_log.pop()
                st.rerun()
        with col_clear:
            if st.button("Clear All Exercise 🗑️", use_container_width=True):
                st.session_state.exercise_log = []
                st.rerun()

with tab3:
    st.header("📜 Your Wellness History")
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
                st.dataframe(my_history.drop(columns=["username"]), use_container_width=True)
                if not my_history.empty:
                    st.line_chart(my_history, x="Date", y="Net_Calories")
    except Exception as e:
        st.error(f"Could not load history: {e}")
