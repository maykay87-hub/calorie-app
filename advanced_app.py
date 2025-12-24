import streamlit as st
import pandas as pd

# --- APP CONFIGURATION ---
st.set_page_config(page_title="May Bloom Advanced", page_icon="🌸", layout="centered")

st.header("🌸 May Bloom Wellness")
st.title("Advanced Lifestyle Tracker")
st.write("Complete tracking: Food, Activity, and Net Energy Balance.")

# --- INITIALIZE SESSION STATES ---
if 'food_log' not in st.session_state:
    st.session_state.food_log = []
if 'exercise_log' not in st.session_state:
    st.session_state.exercise_log = []

# --- PART 1: DATABASES ---
food_database = {
    "White Rice (1 small bowl)": {"Cals": 200, "Prot": 4, "Carbs": 44, "Fat": 0},
    "Brown Rice (1 small bowl)": {"Cals": 180, "Prot": 5, "Carbs": 38, "Fat": 1},
    "Nasi Lemak (Rice Only)":    {"Cals": 350, "Prot": 5, "Carbs": 45, "Fat": 15},
    "Mee Goreng (1 plate)":      {"Cals": 500, "Prot": 12, "Carbs": 60, "Fat": 20},
    "Fried Chicken (1 pc)":      {"Cals": 250, "Prot": 18, "Carbs": 5,  "Fat": 18},
    "Grilled Fish":              {"Cals": 120, "Prot": 20, "Carbs": 0,  "Fat": 4},
    "Fried Egg":                 {"Cals": 90,  "Prot": 7,  "Carbs": 1,  "Fat": 7},
    "Ulam/Salad (No Dressing)":  {"Cals": 15,  "Prot": 1,  "Carbs": 3,  "Fat": 0},
    "Kangkung Belacan":          {"Cals": 120, "Prot": 3,  "Carbs": 6,  "Fat": 9},
    "Apple (1 medium)":          {"Cals": 60,  "Prot": 0,  "Carbs": 15, "Fat": 0},
    "Teh Tarik (1 cup)":         {"Cals": 180, "Prot": 3,  "Carbs": 25, "Fat": 6},
}

exercise_database = {
    "Badminton (Casual)": 150, "Badminton (Competitive)": 220,
    "Zumba / Aerobics": 250,   "House Chores": 90,
    "Walking (Brisk)": 130,    "Jogging": 240,
    "Cycling": 200,            "Gardening": 140,
}

# --- PART 2: BMI & BMR ---
st.divider()
st.header("1️⃣ Body Metrics")
col1, col2 = st.columns(2)
with col1:
    height_cm = st.number_input("Height (cm)", 100.0, 160.0)
with col2:
    weight_kg = st.number_input("Weight (kg)", 30.0, 70.0)

# Calculate Logic
bmi = weight_kg / ((height_cm/100)**2)
if bmi >= 25:
    adj_weight = (22 * (height_cm/100)**2) + 0.25 * (weight_kg - (22 * (height_cm/100)**2))
    calc_weight = adj_weight
    st.warning(f"BMI: {bmi:.1f} (Obese). Using Adjusted Weight: {adj_weight:.1f}kg")
else:
    calc_weight = weight_kg
    st.success(f"BMI: {bmi:.1f} (Normal/Overweight). Using Actual Weight.")

activity = st.radio("Activity Level", ["Sedentary (x25)", "Active (x30)"], horizontal=True)
daily_needs = calc_weight * (25 if "Sedentary" in activity else 30)
st.info(f"🔥 Daily Energy Goal: **{int(daily_needs)} kcal**")

# --- PART 3: FOOD LOG ---
st.divider()
st.subheader("🍽️ Food Intake")
f_col1, f_col2, f_col3 = st.columns([1,2,1])
with f_col1:
    meal = st.selectbox("Meal", ["Breakfast", "Lunch", "Dinner", "Snack"])
with f_col2:
    food = st.selectbox("Food", list(food_database.keys()))
with f_col3:
    qty = st.number_input("Qty", 0.5, 1.0, 0.5, key="food_qty")

if st.button("Add Food"):
    st.session_state.food_log.append({
        "Meal": meal, "Food": food, "Qty": qty, 
        "Calories": food_database[food]["Cals"] * qty
    })

if st.session_state.food_log:
    f_df = pd.DataFrame(st.session_state.food_log)
    st.dataframe(f_df, use_container_width=True)
    total_in = f_df["Calories"].sum()
else:
    total_in = 0

# --- PART 4: EXERCISE LOG ---
st.divider()
st.subheader("🏃‍♀️ Exercise Log")
e_col1, e_col2 = st.columns([2,1])
with e_col1:
    ex_name = st.selectbox("Activity", list(exercise_database.keys()))
with e_col2:
    ex_dur = st.number_input("Duration (30 min blocks)", 0.5, 1.0, 0.5, key="ex_qty")

if st.button("Add Exercise"):
    st.session_state.exercise_log.append({
        "Activity": ex_name, 
        "Duration (mins)": ex_dur * 30, 
        "Calories Burned": exercise_database[ex_name] * ex_dur
    })

if st.session_state.exercise_log:
    e_df = pd.DataFrame(st.session_state.exercise_log)
    st.dataframe(e_df, use_container_width=True)
    total_out = e_df["Calories Burned"].sum()
else:
    total_out = 0

# --- PART 5: NET BALANCE ---
st.divider()
st.header("⚖️ Net Energy Balance")
c1, c2, c3 = st.columns(3)
c1.metric("Intake", f"{int(total_in)} kcal")
c2.metric("Burned", f"-{int(total_out)} kcal")
c3.metric("Net Total", f"{int(total_in - total_out)} kcal")

remaining = daily_needs - (total_in - total_out)
st.write(f"Goal Status: **{int(remaining)} kcal** remaining to reach maintenance.")
