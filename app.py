import streamlit as st
import pandas as pd

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
# --- PART 2: THE APP LOGIC ---

# Brand Header
st.header("🌸 May Bloom Wellness")
st.title("Malaysian Diet Exchange Calculator")
st.write("Calculate calories and macros for your daily meals.")

# --- SECTION: BMR CALCULATOR ---
with st.expander("🔥 Calculate Daily Energy Needs"):
    weight = st.number_input("Your Weight (kg)", min_value=10.0, value=70.0, step=0.5)
    activity_level = st.radio(
        "How active are you?",
        ["Sedentary (Little to no exercise)", "Active (Exercise > 150 mins/week)"]
    )
    if activity_level == "Sedentary (Little to no exercise)":
        daily_needs = weight * 25
    else:
        daily_needs = weight * 30
    st.info(f"Estimated Daily Requirement: **{int(daily_needs)} kcal**")

# Initialize Session State
if 'food_log' not in st.session_state:
    st.session_state.food_log = []

# --- SECTION: ADD FOOD ---
st.divider()
st.subheader("Add Food to Meal")

# New: Select Meal Type
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    meal_type = st.selectbox("Meal Time", ["Breakfast", "Lunch", "Dinner", "Snack"])
with col2:
    food_choice = st.selectbox("Select Food Item", list(food_database.keys()))
with col3:
    quantity = st.number_input("Qty", min_value=0.5, value=1.0, step=0.5)

if st.button("Add to List"):
    item_data = food_database[food_choice]
    st.session_state.food_log.append({
        "Meal": meal_type,
        "Food": food_choice,
        "Qty": quantity,
        "Calories": item_data["Cals"] * quantity,
        "Protein (g)": item_data["Prot"] * quantity,
        "Carbs (g)": item_data["Carbs"] * quantity,
        "Fat (g)": item_data["Fat"] * quantity
    })
    st.success(f"Added {quantity}x {food_choice} to {meal_type}")

# --- SECTION: VIEW TOTALS ---
st.divider()
st.subheader("📝 Daily Food Log")

if st.session_state.food_log:
    # Create DataFrame
    df = pd.DataFrame(st.session_state.food_log)
    
    # Display the table
    st.dataframe(df, use_container_width=True)

    # Undo Button (Removes the last entry)
    if st.button("↩️ Undo Last Entry"):
        st.session_state.food_log.pop()
        st.rerun()

    # Calculate Grand Totals
    grand_cals = df['Calories'].sum()
    grand_prot = df['Protein (g)'].sum()
    grand_carbs = df['Carbs (g)'].sum()
    grand_fat = df['Fat (g)'].sum()
    
    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Calories", f"{grand_cals} kcal", delta=f"{int(daily_needs - grand_cals)} remaining")
    c2.metric("Protein", f"{grand_prot} g")
    c3.metric("Carbs", f"{grand_carbs} g")
    c4.metric("Fat", f"{grand_fat} g")
    
    # Clear All Button
    if st.button("🗑️ Clear Entire List"):
        st.session_state.food_log = []
        st.rerun()
else:
    st.info("Your log is empty. Start adding food above!")
