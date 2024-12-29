import streamlit as st
from streamlit.column_config import DateColumn, NumberColumn, TextColumn
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(
    page_title="First-Aid Inventory Tracker",
    page_icon="🩹"
)

st.write("# First-Aid Inventory Tracker 🩹")

st.markdown(
    f"""
    This website is a simple web app for tracking and updating first-aid supplied for the Fethard On-Sea unit of the Irish Coast Guard.

    The supplies are organized based on the where they're stored, specifically:
    - **📦 Stockroom**: The main storage area for all supplies.
    - **🎒 Training Kit**: The supplies in the training kit used when on exercises.
    - **🚨 Mobile 1/2**: The supplies in the first-aid bag assigned to Mobile 1/2.

    The tracker needs to be updated whenever supplies are *used* or *restocked*. To do this, you will need to:

    1. Select the appropriate inventory.
    2. Locate the item.
    3. Update the count.
    4. Update the expiration date (if restocking an item).
    5. Click the "Sync" button to upload the changes.
    
    Updating both the count and expiration date is important as this way the tracker can send out automated alerts when items are running low or expiring soon. To receive automated email alerts about items that need attention, please add your email address to your account and enable alerts on the user settings page.
    """
)

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data()
def load_inventory():
    return conn.read()

def update_status(df):
    df["Status"] = (df["Count"] - df["Capacity"]).apply(lambda x: "OK" if x == 0 else "Low Stock" if x < 0 else "Out of Stock")
    tmp = df["Expiration Date"].apply(lambda x: "Expired" if x < pd.Timestamp("today") else "Expiring" if x <= pd.Timestamp("today") + pd.Timedelta("30D") else None)
    df["Status"] = tmp.combine_first(df["Status"])
    df["Status"] = pd.Categorical(df["Status"], categories=["OK", "Expiring", "Low Stock", "Expired", "Out of Stock"], ordered=True) 
    return df

def process_inventory(df):

    df["Expiration Date"] = pd.to_datetime(df["Expiration Date"], errors="coerce")
    df["Last Updated"] = pd.to_datetime(df["Last Updated"], errors="coerce")
    df["Count"] = df["Count"].astype(int)
    df["Capacity"] = df["Capacity"].astype(int)
    df = update_status(df)
    return df

def sync_inventory(df):

    updated_rows = (original_df.loc[df.index] != df.loc[df.index]).any(axis=1).index
    df_updated.loc[updated_rows, "Last Updated"]= pd.Timestamp("today")
    original_df.update(df_updated)
    conn.update(data=df_updated)


inventories = ["Full Inventory", "Stockroom", "Training Kit", "Mobile 1", "Mobile 2"]
inventory_icons = ["📋", "📦", "🎒", "🚨", "🚨"]
inventory_options = [" ".join([icon, inventory]) for icon, inventory in list(zip(inventory_icons, inventories))]

status_values = ["OK", "Expiring", "Low Stock", "Expired", "Out of Stock"]
status_colors = {"OK": "color: green",
                 "Expiring": "color: orange",
                 "Low Stock": "color: orange",
                 "Expired": "color: red",
                 "Out of Stock": "color: red"}

def highlight_status(s):
    return status_colors[s]

status_icons = ["🟩", "🟨", "🟨", "🟥", "🟥"]
status_options = [" ".join([icon, status]) for icon, status in list(zip(status_icons, status_values))]

column_order = ["Inventory", "Item", "Type", "Count", "Capacity",  "Expiration Date", "Status"]
column_config = {"Item": TextColumn("Item"),
                 "Inventory": TextColumn("Inventory"),
                 "Count": NumberColumn(min_value=0),
                 "Capacity": NumberColumn(min_value=0),
                 "Expiration Date": DateColumn("Expiration Date", 
                                               format="MM/YY",),
                 "Status": TextColumn("Status")
    }
original_df = load_inventory()
df_processed = process_inventory(original_df)

st.markdown("## ⚠️ Alerts")


high_priority_items = df_processed[(df_processed["Status"] == "Expired") | (df_processed["Status"] == "Out of Stock")]
if not high_priority_items.empty:
    high_priority_items = high_priority_items.style.map(highlight_status, subset=["Status"])
    st.warning(f"The following items need immediate attention:", icon="🟥")
    st.dataframe(high_priority_items,
                    column_config=column_config,
                    column_order=column_order,
                    hide_index=True)

medium_priority_items = df_processed[(df_processed["Status"] == "Expiring") | (df_processed["Status"] == "Low Stock")]
if not medium_priority_items.empty:
    medium_priority_items = medium_priority_items.style.map(highlight_status, subset=["Status"])
    st.warning(f"The following items will need to be restocked soon:", icon="🟨")
    st.dataframe(medium_priority_items, 
                    column_config=column_config,
                    column_order=column_order,
                    hide_index=True)


st.markdown("""
            ## Manage Inventory
            Use the table below to update the count and expiration date of items in the inventories. Remember to click the "Sync" button afterwards to upload your changes.
            """)

active_inventory = st.selectbox("Select which inventory to manage:", inventory_options)

status_filter = st.multiselect("Select which items to manage", status_options, status_options)

inv_name = active_inventory[2:]

if active_inventory == "📋 Full Inventory":
    df_filtered = df_processed
    st.write(f"### {active_inventory}")
else:
    df_filtered = df_processed[df_processed["Inventory"] == inv_name]
    st.write(f"### {active_inventory} Inventory")

df_filtered = df_filtered.sort_values(by=["Status"], ascending=False)
df_updated = st.data_editor(df_filtered.style.map(highlight_status, subset=["Status"]),
                disabled=("Inventory", "Item", "Type", "Capacity", "Status"),
                column_config=column_config,
                column_order=column_order,
                hide_index=True)
sync_button = st.button("🗘 Sync", on_click=sync_inventory(df_updated))

st.write("Inventory last updated on", original_df["Last Updated"].max().strftime("%A, %B %-d, %Y."))
