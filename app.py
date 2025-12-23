import streamlit as st
import pandas as pd

# --- PART 1: THE DATA (Brain) ---
# Now includes Calories, Protein (g), and Carbs (g) per unit
food_database = {
    # Carbohydrates: Base 75 kcal, 2g Protein, 15g CHO
    "Rice (1/2 cup)": {"Cals": 75, "Prot": 2, "Carbs": 15},
    "Whole Meal Bread (1 slice)": {"Cals": 75, "Prot": 2, "Carbs": 15},
    "Oats (3 tablespoons)": {"Cals": 75, "Prot": 2, "Carbs": 15},
    "Mee / Noodle (1/3 cup)": {"Cals": 75, "Prot": 2, "Carbs": 15},
    "Potato (1/2 cup)": {"Cals": 75, "Prot": 2, "Carbs": 15},
    "Cream Crackers (3 pieces)": {"Cals": 75, "Prot": 2, "Carbs": 15},

    # Proteins: Base 65 kcal, 7g Protein, 0g CHO
    "Chicken Drumstick (1/2 piece)": {"Cals": 65, "Prot": 7, "Carbs": 0},
    "Egg (1 whole)": {"Cals": 65, "Prot": 7, "Carbs": 0},
    "Fish (1/2 medium)": {"Cals": 65, "Prot": 7, "Carbs": 0},
    "Taukua (1/2 piece)": {"Cals": 65, "Prot": 7, "Carbs": 0},

    # Fruits: Base 60 kcal, 0g Protein, 15g CHO
    "Apple (1 medium)": {"Cals": 60, "Prot": 0, "Carbs": 15},
    "Banana (1 small)": {"Cals": 60, "Prot": 0, "Carbs": 15},
    "Papaya (1 slice)": {"Cals": 60, "Prot": 0, "Carbs": 15},

    # Fats: 45 kcal, 0g Protein, 0g CHO
    "Cooking Oil (1 tsp)": {"Cals": 45, "Prot": 0, "Carbs": 0},

    # Vegetables: 0 kcal base (assuming plain)
    "Green Leafy Veg (1 cup)": {"Cals": 0, "Prot": 0, "Carbs": 0},
    
    # Milk: 120 kcal, 7g Protein, 12g CHO 
    "Milk (1 glass)": {"Cals": 120, "Prot": 7, "Carbs": 12},

    # --- LOCAL FAVORITES (MEALS) ---
    "Nasi Lemak (1 plate - Standard)": {"Cals": 400, "Prot": 12, "Carbs": 45},
    "Chicken Rice (Roasted - 1 plate)": {"Cals": 600, "Prot": 25, "Carbs": 60},
    "Mee Goreng / Fried Mee (1 plate)": {"Cals": 500, "Prot": 15, "Carbs": 60},
    "Noodle Soup / Mee Soup (1 bowl)": {"Cals": 350, "Prot": 15, "Carbs": 45},
    "Curry Mee (1 bowl)": {"Cals": 550, "Prot": 18, "Carbs": 50},
    "Char Kuey Teow (1 plate)": {"Cals": 740, "Prot": 15, "Carbs": 70},
    "Roti Canai (1 piece + dhal)": {"Cals": 300, "Prot": 6, "Carbs": 35},
    "Tosai (1 piece)": {"Cals": 200, "Prot": 4, "Carbs": 35},
    "Sandwich (Egg Mayo - 2 slices)": {"Cals": 300, "Prot": 10, "Carbs": 30},
    "Satay (Chicken - 5 sticks)": {"Cals": 185, "Prot": 15, "Carbs": 5},

    # --- LOCAL DRINKS ---
    "Teh Tarik (1 glass)": {"Cals": 180, "Prot": 4, "Carbs": 25},
    "Kopi O (Black with Sugar)": {"Cals": 60, "Prot": 0, "Carbs": 15},
    "Kopi Susu (Coffee with Milk)": {"Cals": 140, "Prot": 3, "Carbs": 20},
    "Milo (1 cup)": {"Cals": 150, "Prot": 3, "Carbs": 25},
    "Syrup Bandung (1 glass)": {"Cals": 150, "Prot": 2, "Carbs": 25},
    "Plain Water": {"Cals": 0, "Prot": 0, "Carbs": 0}
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
