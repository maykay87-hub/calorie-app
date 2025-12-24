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

# --- PART 1: THE DATA (Brain) ---
food_database = {
    # --- CARBOHYDRATES (Standard: 15g CHO, 2g Prot, ~75 kcal) ---
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

    # --- FRUITS (Standard: 15g CHO, 0g Prot, 60 kcal) ---
    # Portions are estimates for 1 Serving (1 Exchange)
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

    # --- 🥦 VEGETABLES (Sayur) ---
    # Low Calorie (Soups / Ulam / Blanched)
    "Ulam (Cucumber/Raw Greens)":   {"Cals": 0,  "Prot": 0,  "Carbs": 0,  "Fat": 0},
    "Bayam Soup (Spinach)":         {"Cals": 45,  "Prot": 0,  "Carbs": 0,  "Fat": 5},
    "Sawi / Choy Sum (Blanched)":   {"Cals": 0,  "Prot": 0,  "Carbs": 0,  "Fat": 0},
    "Steamed Broccoli/ cauliflower":   {"Cals": 0,  "Prot": 0,  "Carbs": 0,  "Fat": 0},
    "Stir fry vegetables":   {"Cals": 45,  "Prot": 0,  "Carbs": 0,  "Fat": 5},
    
    # --- PROTEINS (Standard: 7g Prot per exchange) ---
    "Chicken Drumstick (1 piece)": {"Cals": 130, "Prot": 14, "Carbs": 0, "Fat": 8},
    "Meat / Beef / Mutton (Lean - 2 matchbox size)": {"Cals": 130, "Prot": 14, "Carbs": 0, "Fat": 8},
    "Prawns (6 medium)": {"Cals": 50, "Prot": 7, "Carbs": 0, "Fat": 2},
    "Egg (1 whole)": {"Cals": 65, "Prot": 7, "Carbs": 0, "Fat": 5},
    "Fish (1 medium piece)": {"Cals": 70, "Prot": 14, "Carbs": 0, "Fat": 2},
    "Taukua (1 piece)": {"Cals": 130, "Prot": 14, "Carbs": 0, "Fat": 8},
    "Ikan Bilis (2 tbsp)": {"Cals": 65, "Prot": 7, "Carbs": 0, "Fat": 2},
    
    # --- DAIRY / YOGURT ---
    "Yogurt (Natural - 1 cup)": {"Cals": 100, "Prot": 8, "Carbs": 12, "Fat": 2},
    "Low Fat Milk (1 glass)": {"Cals": 125, "Prot": 8, "Carbs": 12, "Fat": 5},
    "Full Cream Milk (1 glass)": {"Cals": 150, "Prot": 8, "Carbs": 10, "Fat": 9},
    "Skim Milk (1 glass)": {"Cals": 90, "Prot": 8, "Carbs": 15, "Fat": 0},
    
    # --- FATS ---
    "Cooking Oil (1 tsp)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},
    "Butter / Margarine / Mayonnaise (1 tsp)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},
    "Peanut (20 small)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},
    "Walnut (1 whole)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},
    "Almond/ Cashew nut (6 whole)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},
    "Sesame seed (1 level tablespoon)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},
    "Coconut milk (santan) (2 level tablespoons)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},

    # --- LOCAL FAVORITES (MEALS) ---
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
    
    # --- LOCAL DRINKS ---
    "Teh Tarik (1 glass)": {"Cals": 180, "Prot": 4, "Carbs": 25, "Fat": 6},
    "Kopi O (Black with Sugar)": {"Cals": 60, "Prot": 0, "Carbs": 15, "Fat": 0},
    "Kopi Susu (Coffee with Milk)": {"Cals": 140, "Prot": 3, "Carbs": 20, "Fat": 5},
    "Milo (1 cup)": {"Cals": 150, "Prot": 3, "Carbs": 25, "Fat": 4},
    "Syrup Bandung (1 glass)": {"Cals": 150, "Prot": 2, "Carbs": 25, "Fat": 5},
    "Plain Water": {"Cals": 0, "Prot": 0, "Carbs": 0, "Fat": 0}
}

exercise_database = {
    # High Intensity
    "Zumba / Aerobics": 250,
    "Pound (Cardio Drumming)": 240,   
    "Jogging": 240,
    "Swimming (Laps)": 230,
    "Badminton (Competitive)": 220,
    "Cycling": 200,

    # Moderate Intensity
    "Badminton / Pickleball (Casual)": 150, 
    "Walking (Brisk)": 130,
    "Gardening": 140,

    # Low Intensity / Strength
    "Yoga": 100,                      
    "Pilates": 110,                   
    "House Chores": 90,
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
