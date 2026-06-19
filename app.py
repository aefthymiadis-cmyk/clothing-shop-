import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="SmartWear Planner Pro", layout="wide")

# ----------------------------
# SAMPLE DATA
# ----------------------------

sales_data = pd.DataFrame({
    "SKU": ["T-shirts"]*4 + ["Shoes"]*4 + ["Hats"]*4 + ["Pants"]*4,
    "Week": list(range(1, 5))*4,
    "Units_Sold": [
        100, 120, 140, 130,
        60, 70, 80, 90,
        40, 45, 50, 55,
        80, 85, 90, 95
    ]
})

inventory = pd.DataFrame({
    "SKU": ["T-shirts", "Shoes", "Hats", "Pants"],
    "Stock": [80, 50, 30, 60],
    "Safety_Stock": [40, 20, 15, 30],
    "Unit_Cost": [8, 25, 5, 20],
    "Lead_Time_Weeks": [2, 3, 1, 2]
})

suppliers = pd.DataFrame({
    "Supplier": ["A", "B", "C"],
    "Reliability": [0.95, 0.82, 0.90],
    "Cost_Index": [1.0, 0.9, 1.1],
    "Lead_Time": [2, 3, 1],
    "Quality": [0.90, 0.85, 0.80]
})

# ----------------------------
# FUNCTIONS
# ----------------------------

def moving_average(df, sku):
    values = df[df["SKU"] == sku]["Units_Sold"].values
    return np.mean(values[-3:])

def supplier_score(row):
    return (
        0.4 * row["Reliability"] +
        0.3 * (1 / row["Cost_Index"]) +
        0.2 * (1 / row["Lead_Time"]) +
        0.1 * row["Quality"]
    )

def export_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Purchase Orders", index=False)
    return output.getvalue()

# ----------------------------
# SUPPLIER SCORING
# ----------------------------

suppliers["Score"] = suppliers.apply(supplier_score, axis=1)
suppliers["Service_Level_%"] = suppliers["Reliability"] * 100

# ----------------------------
# SESSION STATE
# ----------------------------

if "orders" not in st.session_state:
    st.session_state.orders = pd.DataFrame(columns=[
        "PO_Number",
        "SKU",
        "Quantity",
        "Supplier",
        "Status"
    ])

# ----------------------------
# INVENTORY CALCULATIONS
# ----------------------------

inventory_view = inventory.copy()

forecasts = []
reorder_points = []
suggested_orders = []
stockout_risks = []
days_of_supply = []
recommendations = []

for _, row in inventory_view.iterrows():
    sku = row["SKU"]
    stock = row["Stock"]
    safety = row["Safety_Stock"]
    lead = row["Lead_Time_Weeks"]

    forecast = moving_average(sales_data, sku)
    demand_during_lead_time = forecast * lead
    reorder_point = demand_during_lead_time + safety
    suggested_order = max(0, int((2 * forecast) - stock))

    daily_demand = forecast / 7
    days_supply = stock / daily_demand if daily_demand > 0 else 0

    if stock < reorder_point:
        risk = "High"
        recommendation = "Order now to avoid stockout"
    elif days_supply < 14:
        risk = "Medium"
        recommendation = "Monitor closely"
    else:
        risk = "Low"
        recommendation = "No action required"

    forecasts.append(round(forecast, 2))
    reorder_points.append(round(reorder_point, 2))
    suggested_orders.append(suggested_order)
    stockout_risks.append(risk)
    days_of_supply.append(round(days_supply, 1))
    recommendations.append(recommendation)

inventory_view["Forecast"] = forecasts
inventory_view["Reorder_Point"] = reorder_points
inventory_view["Suggested_Order"] = suggested_orders
inventory_view["Stockout_Risk"] = stockout_risks
inventory_view["Days_of_Supply"] = days_of_supply
inventory_view["Recommendation"] = recommendations

# ----------------------------
# FORECAST ACCURACY
# ----------------------------

sales_data["Previous_Week_Forecast"] = sales_data.groupby("SKU")["Units_Sold"].shift(1)
sales_data["Forecast_Error"] = abs(
    sales_data["Units_Sold"] - sales_data["Previous_Week_Forecast"]
)

forecast_accuracy = (
    100 -
    sales_data["Forecast_Error"].mean() /
    sales_data["Units_Sold"].mean() * 100
)

forecast_accuracy = round(forecast_accuracy, 1)

# ----------------------------
# KPI CALCULATIONS
# ----------------------------

stockout_risk_count = len(
    inventory_view[inventory_view["Stockout_Risk"] == "High"]
)

inventory_turnover = round(
    sales_data["Units_Sold"].sum() / inventory["Stock"].mean(),
    2
)

average_days_supply = round(
    inventory_view["Days_of_Supply"].mean(),
    1
)

pending_orders = len(
    st.session_state.orders[
        st.session_state.orders["Status"] == "Pending"
    ]
)

late_orders = len(
    st.session_state.orders[
        st.session_state.orders["Status"] == "Late"
    ]
)

# ----------------------------
# APP UI
# ----------------------------

st.title("🛍️ SmartWear Planner Pro")
st.subheader("Supply Chain Planning & Control App for an Online Clothing Retailer")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Overview",
    "📈 Forecast",
    "📦 Inventory",
    "🚚 Suppliers",
    "🧾 Orders",
    "🤖 GenAI Reflection"
])

# ----------------------------
# OVERVIEW
# ----------------------------

with tab1:
    st.header("Manager Overview")

    col1, col2, col3 = st.columns(3)
    col1.metric("Forecast Accuracy", f"{forecast_accuracy}%")
    col2.metric("Stockout Risk SKUs", stockout_risk_count)
    col3.metric("Inventory Turnover", inventory_turnover)

    col4, col5, col6 = st.columns(3)
    col4.metric("Average Days of Supply", average_days_supply)
    col5.metric("Pending Orders", pending_orders)
    col6.metric("Late Orders", late_orders)

    st.markdown("---")
    st.subheader("Urgent Alerts")

    high_risk = inventory_view[inventory_view["Stockout_Risk"] == "High"]

    if len(high_risk) > 0:
        for _, row in high_risk.iterrows():
            st.error(
                f"{row['SKU']} needs attention: "
                f"Stock {row['Stock']} is below reorder point {row['Reorder_Point']}."
            )
    else:
        st.success("No urgent stockout risks.")

    for _, row in suppliers.iterrows():
        if row["Reliability"] < 0.85:
            st.warning(
                f"Supplier {row['Supplier']} reliability is below target "
                f"({round(row['Reliability'] * 100, 1)}%)."
            )

    with st.expander("Planning Logic and Assumptions"):
        st.write("""
        Forecast method:
        - Moving average of the last 3 weeks.

        Reorder Point:
        - Forecast demand × lead time + safety stock.

        Suggested Order:
        - Target stock - current stock.
        - Target stock is assumed as 2 weeks of forecast demand.

        Supplier Score:
        - 40% reliability
        - 30% cost competitiveness
        - 20% lead-time performance
        - 10% quality

        Thresholds:
        - Stock below reorder point = high stockout risk.
        - Days of supply below 14 days = monitor closely.
        - Supplier reliability below 85% = supplier warning.
        """)

# ----------------------------
# FORECAST SCREEN
# ----------------------------

with tab2:
    st.header("Forecasting")

    selected_sku = st.selectbox("Select SKU", inventory["SKU"])

    history = sales_data[sales_data["SKU"] == selected_sku]
    selected_forecast = moving_average(sales_data, selected_sku)

    st.line_chart(history.set_index("Week")["Units_Sold"])

    st.metric("Next Week Forecast", round(selected_forecast, 2))

    st.info("Manager question: Can I trust the demand estimate?")

    st.dataframe(
        history[["Week", "SKU", "Units_Sold", "Previous_Week_Forecast", "Forecast_Error"]],
        use_container_width=True
    )

    if forecast_accuracy >= 90:
        st.success("Forecast accuracy is strong.")
    elif forecast_accuracy >= 80:
        st.warning("Forecast accuracy is acceptable but should be monitored.")
    else:
        st.error("Forecast accuracy is low. Review the forecasting method.")

# ----------------------------
# INVENTORY SCREEN
# ----------------------------

with tab3:
    st.header("Inventory Planning")

    st.info("Manager question: What should I reorder, how much, when, and why?")

    st.dataframe(
        inventory_view[[
            "SKU",
            "Stock",
            "Safety_Stock",
            "Forecast",
            "Lead_Time_Weeks",
            "Reorder_Point",
            "Days_of_Supply",
            "Suggested_Order",
            "Stockout_Risk",
            "Recommendation"
        ]],
        use_container_width=True
    )

    st.markdown("---")
    st.subheader("Create Purchase Order")

    order_sku = st.selectbox("SKU to Order", inventory["SKU"])
    quantity = st.number_input("Order Quantity", min_value=0, value=50)

    supplier_choice = st.selectbox(
        "Supplier",
        suppliers.sort_values("Score", ascending=False)["Supplier"]
    )

    status = st.selectbox(
        "Order Status",
        ["Pending", "Shipped", "Received", "Late"]
    )

    if st.button("Create Purchase Order"):
        po_number = f"PO-{len(st.session_state.orders) + 1:03d}"

        new_order = pd.DataFrame([{
            "PO_Number": po_number,
            "SKU": order_sku,
            "Quantity": quantity,
            "Supplier": supplier_choice,
            "Status": status
        }])

        st.session_state.orders = pd.concat(
            [st.session_state.orders, new_order],
            ignore_index=True
        )

        st.success(f"Purchase Order {po_number} created successfully.")

# ----------------------------
# SUPPLIER SCREEN
# ----------------------------

with tab4:
    st.header("Supplier Management")

    st.info("Manager question: Which suppliers support service reliability?")

    supplier_table = suppliers.sort_values("Score", ascending=False)

    st.dataframe(
        supplier_table[[
            "Supplier",
            "Reliability",
            "Service_Level_%",
            "Cost_Index",
            "Lead_Time",
            "Quality",
            "Score"
        ]],
        use_container_width=True
    )

    best_supplier = supplier_table.iloc[0]

    st.success(
        f"Recommended supplier: Supplier {best_supplier['Supplier']} "
        f"with score {round(best_supplier['Score'], 2)}."
    )

    for _, row in supplier_table.iterrows():
        if row["Reliability"] < 0.85:
            st.warning(
                f"Supplier {row['Supplier']} is below the 85% reliability target."
            )

# ----------------------------
# ORDERS SCREEN
# ----------------------------

with tab5:
    st.header("Purchase Order Status")

    st.info("Manager question: What is late, pending, shipped or received?")

    st.dataframe(
        st.session_state.orders,
        use_container_width=True
    )

    if len(st.session_state.orders) > 0:
        status_summary = st.session_state.orders["Status"].value_counts()

        st.subheader("Order Status Summary")
        st.bar_chart(status_summary)

        excel_file = export_excel(st.session_state.orders)

        st.download_button(
            label="📥 Download Purchase Orders Excel",
            data=excel_file,
            file_name="purchase_orders.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("No purchase orders created yet.")

# ----------------------------
# GENAI REFLECTION SCREEN
# ----------------------------

with tab6:
    st.header("GenAI Declaration and Reflection")

    st.write("""
    GenAI was used to support the design of this prototype by helping structure the
    app modules, formulas, KPI logic and Streamlit layout.

    The final decisions were checked manually against supply chain planning concepts:
    forecasting, reorder point calculation, supplier scoring and KPI interpretation.

    GenAI helped with:
    - creating the first Streamlit prototype
    - adding KPI calculations
    - improving decision-support alerts
    - making formulas visible inside the app

    Human input was used to:
    - choose the clothing retail context
    - select the SKUs
    - decide the planning logic
    - check whether each KPI answers a managerial question

    Limitations:
    - the app uses simulated data
    - forecasts are simple moving averages
    - supplier scores are simplified
    - it does not connect to live Shopify data
    - it does not include demand seasonality
    """)
