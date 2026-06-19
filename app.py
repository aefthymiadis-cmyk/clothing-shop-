import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="SmartWear Planner Pro", layout="wide")

# ----------------------------
# MONTHLY SALES DATA
# ----------------------------

sales_data = pd.DataFrame({
    "SKU": (
        ["T-shirts"] * 6 +
        ["Shoes"] * 6 +
        ["Hats"] * 6 +
        ["Pants"] * 6
    ),
    "Month": (
        ["January", "February", "March", "April", "May", "June"] * 4
    ),
    "Month_Number": list(range(1, 7)) * 4,
    "Units_Sold": [
        420, 460, 500, 540, 580, 610,   # T-shirts
        180, 200, 220, 250, 270, 300,   # Shoes
        120, 135, 150, 160, 175, 190,   # Hats
        260, 280, 300, 330, 350, 370    # Pants
    ]
})

inventory = pd.DataFrame({
    "SKU": ["T-shirts", "Shoes", "Hats", "Pants"],
    "Stock": [350, 120, 90, 180],
    "Safety_Stock": [120, 60, 40, 80],
    "Unit_Cost": [8, 25, 5, 20],
    "Lead_Time_Months": [1, 1, 1, 1]
})

# ----------------------------
# SUPPLIER DATA CONNECTED TO CLOTHES
# ----------------------------

suppliers = pd.DataFrame({
    "Supplier": [
        "CottonWear Ltd", "Urban Basics Co", "FastPrint Apparel",
        "StepStyle Shoes", "SolePro Imports", "ComfortFoot Ltd",
        "CapHouse Supply", "Urban Basics Co", "Headwear Direct",
        "DenimLine Factory", "Urban Basics Co", "PantsPro Manufacturing"
    ],
    "SKU": [
        "T-shirts", "T-shirts", "T-shirts",
        "Shoes", "Shoes", "Shoes",
        "Hats", "Hats", "Hats",
        "Pants", "Pants", "Pants"
    ],
    "Reliability": [
        0.94, 0.88, 0.91,
        0.90, 0.84, 0.87,
        0.92, 0.88, 0.86,
        0.89, 0.88, 0.93
    ],
    "Unit_Cost": [
        7.50, 8.00, 8.30,
        24.00, 22.50, 25.00,
        4.80, 5.00, 5.30,
        19.50, 20.00, 21.00
    ],
    "Lead_Time_Days": [
        12, 10, 8,
        18, 22, 15,
        9, 10, 14,
        16, 10, 13
    ],
    "MOQ": [
        100, 80, 120,
        50, 70, 40,
        60, 80, 50,
        70, 80, 60
    ],
    "Quality": [
        0.92, 0.88, 0.90,
        0.89, 0.82, 0.88,
        0.90, 0.88, 0.84,
        0.87, 0.88, 0.91
    ]
})

# ----------------------------
# FUNCTIONS
# ----------------------------

def monthly_demand_forecast(df, sku):
    """
    Forecasting demand model based on past monthly sales.
    Uses weighted moving average:
    50% most recent month + 30% previous month + 20% third previous month.
    """
    values = df[df["SKU"] == sku].sort_values("Month_Number")["Units_Sold"].values
    return (0.5 * values[-1]) + (0.3 * values[-2]) + (0.2 * values[-3])

def supplier_score(row, min_cost, max_cost, min_lead, max_lead):
    cost_score = 1 if max_cost == min_cost else 1 - ((row["Unit_Cost"] - min_cost) / (max_cost - min_cost))
    lead_score = 1 if max_lead == min_lead else 1 - ((row["Lead_Time_Days"] - min_lead) / (max_lead - min_lead))

    return (
        0.4 * row["Reliability"] +
        0.3 * cost_score +
        0.2 * lead_score +
        0.1 * row["Quality"]
    )

def export_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Purchase Orders", index=False)
    return output.getvalue()

# ----------------------------
# SUPPLIER SCORING BY SKU
# ----------------------------

supplier_rows = []

for sku in suppliers["SKU"].unique():
    group = suppliers[suppliers["SKU"] == sku].copy()

    min_cost = group["Unit_Cost"].min()
    max_cost = group["Unit_Cost"].max()
    min_lead = group["Lead_Time_Days"].min()
    max_lead = group["Lead_Time_Days"].max()

    group["Score"] = group.apply(
        lambda row: supplier_score(row, min_cost, max_cost, min_lead, max_lead),
        axis=1
    )

    group["Service_Level_%"] = group["Reliability"] * 100
    supplier_rows.append(group)

suppliers = pd.concat(supplier_rows, ignore_index=True)

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
best_suppliers = []

for _, row in inventory_view.iterrows():
    sku = row["SKU"]
    stock = row["Stock"]
    safety = row["Safety_Stock"]
    lead = row["Lead_Time_Months"]

    forecast = monthly_demand_forecast(sales_data, sku)

    demand_during_lead_time = forecast * lead
    reorder_point = demand_during_lead_time + safety

    target_stock = forecast * 2
    suggested_order = max(0, int(target_stock - stock))

    daily_demand = forecast / 30
    days_supply = stock / daily_demand if daily_demand > 0 else 0

    supplier_group = suppliers[suppliers["SKU"] == sku].sort_values("Score", ascending=False)
    best_supplier = supplier_group.iloc[0]["Supplier"]

    if stock < reorder_point:
        risk = "High"
        recommendation = f"Order now from {best_supplier}"
    elif days_supply < 30:
        risk = "Medium"
        recommendation = "Monitor stock closely"
    else:
        risk = "Low"
        recommendation = "No action required"

    forecasts.append(round(forecast, 2))
    reorder_points.append(round(reorder_point, 2))
    suggested_orders.append(suggested_order)
    stockout_risks.append(risk)
    days_of_supply.append(round(days_supply, 1))
    recommendations.append(recommendation)
    best_suppliers.append(best_supplier)

inventory_view["Monthly_Demand_Forecast"] = forecasts
inventory_view["Reorder_Point"] = reorder_points
inventory_view["Suggested_Order"] = suggested_orders
inventory_view["Stockout_Risk"] = stockout_risks
inventory_view["Days_of_Supply"] = days_of_supply
inventory_view["Recommended_Supplier"] = best_suppliers
inventory_view["Recommendation"] = recommendations

# ----------------------------
# FORECAST ACCURACY
# ----------------------------

sales_data = sales_data.sort_values(["SKU", "Month_Number"])
sales_data["Previous_Month_Forecast"] = sales_data.groupby("SKU")["Units_Sold"].shift(1)

sales_data["Forecast_Error"] = abs(
    sales_data["Units_Sold"] - sales_data["Previous_Month_Forecast"]
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
    st.header("Overview")

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
                f"stock {row['Stock']} is below reorder point {row['Reorder_Point']}. "
                f"Recommended action: {row['Recommendation']}."
            )
    else:
        st.success("No urgent stockout risks.")

    for _, row in suppliers.iterrows():
        if row["Reliability"] < 0.85:
            st.warning(
                f"{row['Supplier']} for {row['SKU']} is below the 85% reliability target."
            )

    with st.expander("Planning Logic and Assumptions"):
        st.write("""
        Forecast method:
        - Weighted moving average using previous monthly sales.
        - 50% most recent month, 30% previous month, 20% third previous month.

        Reorder Point:
        - Monthly demand forecast × lead time in months + safety stock.

        Suggested Order:
        - Target stock - current stock.
        - Target stock is assumed as 2 months of forecast demand.

        Supplier Score:
        - 40% reliability
        - 30% cost competitiveness
        - 20% lead-time performance
        - 10% quality

        Thresholds:
        - Stock below reorder point = high stockout risk.
        - Days of supply below 30 days = monitor closely.
        - Supplier reliability below 85% = supplier warning.
        """)

# ----------------------------
# FORECAST SCREEN
# ----------------------------

with tab2:
    st.header("Forecasting")

    selected_sku = st.selectbox("Select SKU", inventory["SKU"])

    history = sales_data[sales_data["SKU"] == selected_sku]
    selected_forecast = monthly_demand_forecast(sales_data, selected_sku)

    st.line_chart(history.set_index("Month")["Units_Sold"])

    st.metric("Next Month Demand Forecast", round(selected_forecast, 2))

    st.info("Can I trust the demand estimate?")

    st.dataframe(
        history[[
            "Month",
            "SKU",
            "Units_Sold",
            "Previous_Month_Forecast",
            "Forecast_Error"
        ]],
        use_container_width=True
    )

    if forecast_accuracy >= 90:
        st.success("Forecast accuracy is strong.")
    elif forecast_accuracy >= 80:
        st.warning("Forecast accuracy is acceptable but should be monitored.")
    else:
        st.error("Forecast accuracy is low. Review the forecasting method.")

    with st.expander("Forecasting demand model"):
        st.write("""
        The app forecasts next-month demand using a weighted moving average based on past monthly sales.

        Formula:
        Next Month Forecast =
        50% × latest month sales
        + 30% × previous month sales
        + 20% × third previous month sales.

        This gives more importance to recent sales while still considering older demand history.
        """)

# ----------------------------
# INVENTORY SCREEN
# ----------------------------

with tab3:
    st.header("Inventory Planning")

    st.info("What should I reorder, how much, when, and why?")

    st.dataframe(
        inventory_view[[
            "SKU",
            "Stock",
            "Safety_Stock",
            "Monthly_Demand_Forecast",
            "Lead_Time_Months",
            "Reorder_Point",
            "Days_of_Supply",
            "Suggested_Order",
            "Stockout_Risk",
            "Recommended_Supplier",
            "Recommendation"
        ]],
        use_container_width=True
    )

    st.markdown("---")
    st.subheader("Create Purchase Order")

    order_sku = st.selectbox("SKU to Order", inventory["SKU"])

    available_suppliers = suppliers[
        suppliers["SKU"] == order_sku
    ].sort_values("Score", ascending=False)

    quantity = st.number_input("Order Quantity", min_value=0, value=50)

    supplier_choice = st.selectbox(
        "Supplier",
        available_suppliers["Supplier"]
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

    st.info("Which suppliers support service reliability?")

    supplier_sku_filter = st.selectbox(
        "View suppliers for product",
        ["All Products"] + list(inventory["SKU"])
    )

    if supplier_sku_filter == "All Products":
        supplier_table = suppliers.sort_values(["SKU", "Score"], ascending=[True, False])
    else:
        supplier_table = suppliers[
            suppliers["SKU"] == supplier_sku_filter
        ].sort_values("Score", ascending=False)

    st.dataframe(
        supplier_table[[
            "SKU",
            "Supplier",
            "Reliability",
            "Service_Level_%",
            "Unit_Cost",
            "Lead_Time_Days",
            "MOQ",
            "Quality",
            "Score"
        ]],
        use_container_width=True
    )

    st.subheader("Recommended Supplier by Product")

    recommended = suppliers.sort_values("Score", ascending=False).groupby("SKU").head(1)

    st.dataframe(
        recommended[[
            "SKU",
            "Supplier",
            "Score",
            "Reliability",
            "Unit_Cost",
            "Lead_Time_Days",
            "MOQ"
        ]],
        use_container_width=True
    )

    for _, row in supplier_table.iterrows():
        if row["Reliability"] < 0.85:
            st.warning(
                f"{row['Supplier']} supplies {row['SKU']} but is below the 85% reliability target."
            )

    with st.expander("Supplier coverage explanation"):
        st.write("""
        Each clothing product has three possible suppliers.

        Urban Basics Co appears under more than one product because it can supply
        T-shirts, Hats and Pants.

        The user can filter suppliers by product to see which supplier provides
        each clothing item, compare cost, lead time, MOQ and reliability, then
        choose the best supplier before creating a purchase order.
        """)

# ----------------------------
# ORDERS SCREEN
# ----------------------------

with tab5:
    st.header("Purchase Order Status")

    st.info("What is late, pending, shipped or received?")

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
    - changing weekly sales history into monthly sales history
    - adding a forecasting demand model based on past monthly sales
    - improving supplier data so each supplier is connected to specific products
    - adding KPI calculations and decision-support alerts
    - making formulas visible inside the app

    Human input was used to:
    - choose the clothing retail context
    - select the SKUs
    - decide the planning logic
    - request monthly demand forecasting
    - check whether each KPI answers a clear decision question

    Limitations:
    - the app uses simulated data
    - forecasts use a weighted moving average
    - supplier scores are simplified
    - it does not connect to live Shopify data
    - it does not include demand seasonality
    """)
