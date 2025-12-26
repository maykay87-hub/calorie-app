import streamlit as st
import pandas as pd
import time

# --- AUTHENTICATION LOGIC ---

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["username"] in st.secrets["passwords"] and \
           st.session_state["password"] == st.secrets["passwords"][st.session_state["username"]]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    # Initialize session state variables
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # If already logged in, return True immediately
    if st.session_state["password_correct"]:
        return True

    # Show inputs for username and password
    st.markdown("## 🔒 Client Login")
    st.markdown("Please sign in to access your wellness tracker.")
    
    st.text_input("Username", key="username")
    st.text_input("Password", type="password", key="password")
    
    if st.button("Log In", on_click=password_entered):
        # The logic is handled in the on_click callback
        pass

    if "password_correct" in st.session_state and st.session_state["password_correct"] == False:
        st.error("😕 User not found or password incorrect")
        
    return False

# --- MAIN APP EXECUTION ---

# This line stops the app from running if login fails
if not check_password():
    st.stop()  # Do not run anything below this line!

# ==========================================
# PASTE YOUR ORIGINAL APP CODE BELOW THIS LINE
# ==========================================

# Add a logout button in the sidebar
with st.sidebar:
    st.write(f"Logged in as: **{st.session_state['username']}**")
    if st.button("Log Out"):
        st.session_state["password_correct"] = False
        st.rerun()

# 1. Create a dictionary of allowed users (Username -> Password)
# In a real app, you might hide these in st.secrets, but this works for simple cases
USERS = {
    "jane": "wellness2025",
    "mark": "fitness123",
    "admin": "adminpass"
}

def check_password():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if st.session_state["logged_in"]:
        return True

    st.header("🔒 Client Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Log In"):
        # This specific line tells the app to check the SECRETS, not the code
        if username in st.secrets["passwords"] and password == st.secrets["passwords"][username]:
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.rerun()
        else:
            st.error("Incorrect username or password.")
    return False

# 2. Check if user is already logged in
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# 3. Show Login Form if not logged in
if not st.session_state.logged_in:
    st.title("May Bloom Wellness 🔒")
    st.markdown("Please log in to access your tracker.")
    
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Log In"):
        if check_login(username, password):
            st.session_state.logged_in = True
            st.rerun() # Refresh the app to show content
        else:
            st.error("Incorrect username or password")
            
    # Stop the app here so the rest of your code doesn't run
    st.stop() 

# ==========================================
# YOUR MAIN APP CODE GOES HERE
# ==========================================

st.sidebar.button("Log Out", on_click=lambda: st.session_state.update(logged_in=False))

# --- APP CONFIGURATION ---
st.set_page_config(page_title="May Bloom Advanced", page_icon="🌸", layout="wide")

# --- CUSTOM CSS FOR BRANDING ---
st.markdown("""
<style>
    [data-testid="stMetric"] {
        background-color: #FFF0F5;
        border-radius: 10px;
        padding: 10px;
        border: 1px solid #FFB6C1;
    }
    div.stButton > button {
        background-color: #FFB6C1;
        color: white;
        border: none;
    }
</style>
""", unsafe_allow_html=True)

# --- INITIALIZE SESSION STATES ---
if 'food_log' not in st.session_state:
    st.session_state.food_log = []
if 'exercise_log' not in st.session_state:
    st.session_state.exercise_log = []

# --- PART 1: COMPLETE DATABASES (Your Full List) ---
food_database = {
    # --- CARBOHYDRATES ---
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

    # --- FRUITS ---
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

    # --- VEGETABLES ---
    "Ulam (Cucumber/Raw Greens)":   {"Cals": 0,  "Prot": 0,  "Carbs": 0,  "Fat": 0},
    "Bayam Soup (Spinach)":         {"Cals": 45,  "Prot": 0,  "Carbs": 0,  "Fat": 5},
    "Sawi / Choy Sum (Blanched)":   {"Cals": 0,  "Prot": 0,  "Carbs": 0,  "Fat": 0},
    "Steamed Broccoli/ cauliflower": {"Cals": 0,  "Prot": 0,  "Carbs": 0,  "Fat": 0},
    "Stir fry vegetables":          {"Cals": 45,  "Prot": 0,  "Carbs": 0,  "Fat": 5},
    
    # --- PROTEINS ---
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

# --- PART 2: SIDEBAR (PROFILE) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3050/3050484.png", width=80)
    st.header("👤 Client Profile")
    
    height_cm = st.number_input("Height (cm)", 100.0, 200.0, 160.0)
    weight_kg = st.number_input("Weight (kg)", 30.0, 200.0, 70.0)
    activity = st.selectbox("Activity Level", ["Sedentary (x25)", "Active (x30)"])
    
    st.divider()
    
    # CALCULATE LOGIC (Advanced BMI & Adjusted Weight)
    height_m = height_cm / 100
    bmi = weight_kg / (height_m ** 2)
    
    if bmi < 18.5:
        status = "Underweight"
        st.info(f"BMI: {bmi:.1f} ({status})")
        calc_weight = weight_kg
    elif 18.5 <= bmi < 23:
        status = "Normal"
        st.success(f"BMI: {bmi:.1f} ({status})")
        calc_weight = weight_kg
    elif 23 <= bmi < 25:
        status = "Overweight"
        st.warning(f"BMI: {bmi:.1f} ({status})")
        calc_weight = weight_kg
    else:
        status = "Obese"
        st.error(f"BMI: {bmi:.1f} ({status})")
        ideal_weight = 22 * (height_m ** 2)
        adj_weight = ideal_weight + 0.25 * (weight_kg - ideal_weight)
        calc_weight = adj_weight
        st.caption(f"⚠️ Using Adjusted Weight: {adj_weight:.1f}kg")

    daily_needs = calc_weight * (25 if "Sedentary" in activity else 30)
    st.metric("🔥 Daily Target", f"{int(daily_needs)} kcal")

# --- PART 3: MAIN DASHBOARD ---
st.title("🌸 May Bloom Lifestyle Tracker")

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

# VISUAL DASHBOARD
col1, col2, col3 = st.columns(3)
col1.metric("🍽️ Food Intake", f"{int(total_intake)} kcal")
col2.metric("🔥 Exercise Burn", f"-{int(total_burned)} kcal")
col3.metric("⚖️ Net Calories", f"{int(net_calories)} kcal", delta=f"{int(remaining)} left")

# PROGRESS BAR
st.write("Daily Energy Progress:")
progress = min(max(net_calories / daily_needs, 0.0), 1.0)
st.progress(progress)

if remaining < 0:
    st.error(f"⚠️ You are over your budget by {abs(int(remaining))} kcal!")
else:
    st.info(f"✅ You have **{int(remaining)} kcal** remaining.")

# --- PART 4: LOGGING TABS ---
st.divider()
tab1, tab2 = st.tabs(["🍽️ Food Log", "🏃‍♀️ Exercise Log"])

with tab1:
    c1, c2, c3 = st.columns([2,2,1])
    with c1:
        meal = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snack"])
    with c2:
        food = st.selectbox("Food Item", list(food_database.keys()))
    with c3:
        # Using Dropdown for cleaner mobile experience
        qty = st.selectbox("Serving", [0.5, 1.0, 1.5, 2.0, 2.5, 3.0], index=1)
        
    if st.button("Add Meal ➕", use_container_width=True):
        st.session_state.food_log.append({
            "Meal": meal, "Food": food, "Qty": qty, 
            "Calories": food_database[food]["Cals"] * qty,
            "Protein": food_database[food]["Prot"] * qty,
            "Carbs": food_database[food]["Carbs"] * qty,
            "Fat": food_database[food]["Fat"] * qty
        })
        st.success(f"Added {food}")
        st.rerun()

    if st.session_state.food_log:
        st.dataframe(pd.DataFrame(st.session_state.food_log), use_container_width=True)
        if st.button("Clear Food 🗑️"):
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
        st.success(f"Added {ex_name}")
        st.rerun()
        
    if st.session_state.exercise_log:
        st.dataframe(pd.DataFrame(st.session_state.exercise_log), use_container_width=True)
        if st.button("Clear Exercise 🗑️"):
            st.session_state.exercise_log = []
            st.rerun()
