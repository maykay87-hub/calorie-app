import streamlit as st
import pandas as pd

# --- PART 1: THE BRAIN (DATA) ---
# This dictionary contains the exchange values derived from your image.
# Structure: "Food Name": Calorie Value
food_database = {
    # Carbohydrates (Base: 75 kcal)
    "Rice (1/2 cup)": 75,
    "Whole Meal Bread (1 slice)": 75,
    "Cream Crackers (3 pieces)": 75,
    "Oats (3 tablespoons)": 75,
    "Rice Porridge (1 cup)": 75,
    "Mee / Noodle (1/3 cup)": 75,
    "Meehoon / Kway Teow (1/2 cup)": 75,
    "Potato / Sweet Potato (1/2 cup)": 75,
    "Chapati (1/3 piece)": 75,
    "Tosei (1/2 piece)": 75,

    # Proteins (Base: 65 kcal)
    "Chicken Drumstick (1/2 piece, lean)": 65,
    "Fish (1/2 medium, Selar/Kembong)": 65,
    "Prawns (6 medium)": 65,
    "Egg (1 whole)": 65,
    "Taukua (1/2 piece)": 65,
    "Tempeh (1 piece)": 65,
    "Lean Meat (1 matchbox size)": 65,

    # Fruits (Base: 60 kcal)
    "Apple / Orange / Pear (1 medium)": 60,
    "Banana (1 small)": 60,
    "Papaya / Pineapple / Watermelon (1 slice)": 60,
    "Durian (2 medium seeds)": 60,
    "Guava (1/2 fruit)": 60,

    # Vegetables (Base: 0 kcal, unless oil added)
    "Green Leafy Veg (1 cup)": 0,
    "Stir-Fried Veg (1 cup + 1 tsp oil)": 45, 

    # Fats & Sugars
    "Cooking Oil (1 tsp)": 45,
    "Margarine (1 tsp)": 45,
    "Sugar (1 tsp)": 20,
    "Low Fat Milk (1 glass)": 120
}

# --- PART 2: THE APP LOGIC ---

st.title("🥗 My Diet Exchange Calculator")
st.write("Calculate your daily calories using the Malaysian Food Exchange system.")

# Initialize the "Session State" to remember what foods we added
if 'food_log' not in st.session_state:
    st.session_state.food_log = []

# --- SECTION: ADD FOOD ---
st.subheader("Add Food to Meal")

col1, col2 = st.columns(2)

with col1:
    # Dropdown menu populated by our database keys
    food_choice = st.selectbox("Select Food Item", list(food_database.keys()))

with col2:
    # Number input for quantity
    quantity = st.number_input("Quantity", min_value=0.5, value=1.0, step=0.5)

if st.button("Add to List"):
    # Calculate calories for this item
    calories_per_unit = food_database[food_choice]
    total_cal = calories_per_unit * quantity
    
    # Save to our list
    st.session_state.food_log.append({
        "Food": food_choice,
        "Qty": quantity,
        "Calories": total_cal
    })
    st.success(f"Added {quantity} x {food_choice}")

# --- SECTION: VIEW TOTALS ---
st.divider()
st.subheader("📝 Your Meal Log")

if st.session_state.food_log:
    # Convert list to a nice table
    df = pd.DataFrame(st.session_state.food_log)
    st.table(df)

    # Calculate Grand Total
    grand_total = df['Calories'].sum()
    st.metric(label="Total Calories", value=f"{grand_total} kcal")
    
    # Button to clear the list
    if st.button("Clear List"):
        st.session_state.food_log = []
        st.rerun()
else:
    st.info("No food added yet. Select an item above!")
