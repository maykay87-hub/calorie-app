import streamlit as st
import pandas as pd

# --- PART 1: THE DATA (Brain) ---
food_database = {
    # --- CARBOHYDRATES (Standard: 15g CHO, 2g Prot, ~75 kcal) ---
    "Rice (1/2 cup)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 0},
    "Whole Meal Bread (1 slice)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 1},
    "Oats (3 tablespoons)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 2},
    "Mee / Noodle (1/2 cup)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 1},
    "Potato (1/2 cup)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 0},
    "Corn / Jagung (1/2 cup)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 1},
    "Yam / Keladi (1/2 cup)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 0},
    "Cream Crackers (3 pieces)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 2},
    "Plain Biscuits / Marie (3 pieces)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 2},
    "Bun (1 small plain)": {"Cals": 75, "Prot": 2, "Carbs": 15, "Fat": 2},

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

    # --- PROTEINS (Standard: 7g Prot per exchange) ---
    "Chicken Drumstick (1 piece)": {"Cals": 130, "Prot": 14, "Carbs": 0, "Fat": 8},
    "Meat / Beef / Mutton (Lean - 2 matchbox size)": {"Cals": 65, "Prot": 7, "Carbs": 0, "Fat": 4},
    "Prawns (6 medium)": {"Cals": 50, "Prot": 7, "Carbs": 0, "Fat": 2},
    "Egg (1 whole)": {"Cals": 65, "Prot": 7, "Carbs": 0, "Fat": 5},
    "Fish (1 medium piece)": {"Cals": 80, "Prot": 14, "Carbs": 0, "Fat": 2},
    "Taukua (1 piece)": {"Cals": 130, "Prot": 14, "Carbs": 0, "Fat": 8},
    "Ikan Bilis (2 tbsp)": {"Cals": 65, "Prot": 7, "Carbs": 0, "Fat": 2},
    
    # --- DAIRY / YOGURT ---
    "Yogurt (Natural - 1 cup)": {"Cals": 100, "Prot": 8, "Carbs": 12, "Fat": 2},
    "Low Fat Milk (1 glass)": {"Cals": 120, "Prot": 8, "Carbs": 12, "Fat": 4},
    "Full Cream Milk (1 glass)": {"Cals": 150, "Prot": 8, "Carbs": 12, "Fat": 9},

    # --- FATS ---
    "Cooking Oil (1 tsp)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},
    "Butter / Margarine (1 tsp)": {"Cals": 45, "Prot": 0, "Carbs": 0, "Fat": 5},

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

st.title("🥗 My Diet Exchange Calculator")
st.write("Calculate calories, protein, and carbs using the Malaysian Food Exchange system.")

# Initialize the "Session State" to remember our list
# This is the "Notebook" that keeps data safe!
if 'food_log' not in st.session_state:
    st.session_state.food_log = []

# --- SECTION: ADD FOOD ---
st.subheader("Add Food to Meal")
col1, col2 = st.columns(2)

with col1:
    food_choice = st.selectbox("Select Food Item", list(food_database.keys()))

with col2:
    quantity = st.number_input("Quantity", min_value=0.5, value=1.0, step=0.5)

if st.button("Add to List"):
    # Lookup the data
    item_data = food_database[food_choice]
    
    # Calculate totals
    total_cal = item_data["Cals"] * quantity
    total_prot = item_data["Prot"] * quantity
    total_carbs = item_data["Carbs"] * quantity
    
    # Add to the "Notebook"
    st.session_state.food_log.append({
        "Food": food_choice,
        "Qty": quantity,
        "Calories": total_cal,
        "Protein (g)": total_prot,
        "Carbs (g)": total_carbs
    })
    st.success(f"Added {quantity} x {food_choice}")

# --- SECTION: VIEW TOTALS ---
st.divider()
st.subheader("📝 Your Meal Log")

if st.session_state.food_log:
    # Show the table
    df = pd.DataFrame(st.session_state.food_log)
    st.table(df)

    # Calculate Grand Totals
    grand_cals = df['Calories'].sum()
    grand_prot = df['Protein (g)'].sum()
    grand_carbs = df['Carbs (g)'].sum()
    
    # Display Metrics in 3 nice columns
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Calories", f"{grand_cals} kcal")
    c2.metric("Total Protein", f"{grand_prot} g")
    c3.metric("Total Carbs", f"{grand_carbs} g")
    
    # Clear Button
    if st.button("Clear List"):
        st.session_state.food_log = []
        st.rerun()
else:
    st.info("No food added yet. Start building your meal above!")
