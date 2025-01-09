import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(
    page_title="First-Aid Supplies",
    page_icon=":material/medical_services:"
)

conn = st.connection("gsheets", type=GSheetsConnection)

### Requirements:
### -------------
### This section needs to allow the user to easily:
### - Remove used supplies from the inventory database
### - Add new supplies to the inventory database
### - Check supplies that need attention (low stock, expired, etc.)
### - View the current inventory of supplies in the first-aid kits and stockroom
### - Check the recommended stock levels for each first-aid kit
###
### Additionally, it would be useful to implement functionality that:
### - Allows the user to set up automated alerts for low stock or expired supplies
### -------------
### 
### Functionality:
### --------------
### - To view the current inventory of supplies a table should be displayed where the user can filter by:
###     - Inventory
###     - Status
### - A separate table should be displayed for alerts for items that need, or will soon need attention
### - When adding or removing supplies, there should be a form where the user can input:
###   - The inventory
###   - The item
###   - The action (add or remove)
###   - The quantity (recommended stock levels, current quantity, and quantity after action should be displayed)
###   - The expiry date (if removing supplies, the expiry date should be optional, if unknown it should default to the earliest expiry date of the items being removed in that inventory)
### --------------
###
### Data:
### -----
### The google sheet should have separate sheets for first-aid supplies, vehicles, and equipment
### For the first-aid supplies sheet, the following columns are required:
###     - Inventory
###     - Item
###     - Location
###     - Expiration Date
###     - Date Added
###     - Added By
###     - Removed On
###     - Removed By
###
### There should also be a separate sheet for recommended stock levels for each item in each inventory.
### This sheet should have the following columns:
###     - Inventory
###     - Item
###     - Recommended Stock Level
###     - Minimum Stock Level

def process_supplies(df):
    df = df[df["Date Removed"].isna()]
    df["Date Added"] = pd.to_datetime(df["Date Added"])
    df["Expiration Date"] = pd.to_datetime(df["Expiration Date"])
    return df

def get_summary(df):
    # Get the effective quantity of each item
    summary_df = df[df["Date Removed"].isna()].groupby(["Inventory", "Item"]).size().reset_index()
    summary_df.columns = ["Inventory", "Item", "Quantity"]
    # Add new column for effective quantity (quantity of items that will not expire within 30 days)
    summary_df["Effective Quantity"] = df[(df["Expiration Date"] > pd.Timestamp.today() + pd.Timedelta("30D")) & (df["Date Removed"].isna())].groupby(["Inventory", "Item"]).size().reset_index()[0]
    
    operational_limits_df = get_operational_limits()

    # Merge the summary_df with the operational_limits_df
    summary_df = operational_limits_df.merge(summary_df, on=["Inventory", "Item"], how="left")

    summary_df["Quantity"] = summary_df["Quantity"].fillna(0)
    summary_df["Effective Quantity"] = summary_df["Effective Quantity"].fillna(0)

    summary_df["Status"] = summary_df.apply(get_status, axis=1)
    
    # Make status categorical and ordered
    summary_df["Status"] = pd.Categorical(summary_df["Status"], categories=["Critical", "High Priority", "Medium Priority", "Low Priority", "OK"], ordered=True)

    # Set Quantity columns to integers
    summary_df["Quantity"] = summary_df["Quantity"].astype(int)
    summary_df["Effective Quantity"] = summary_df["Effective Quantity"].astype(int)
    summary_df["Min. Quantity"] = summary_df["Min. Quantity"].astype(int)
    summary_df["Max. Quantity"] = summary_df["Max. Quantity"].astype(int)
    return summary_df

def get_status(row):
    if row["Effective Quantity"] == 0:
        return "Critical"
    elif row["Effective Quantity"] < row["Min. Quantity"]:
        return "High Priority"
    elif row["Effective Quantity"] < row["Max. Quantity"] // 2:
        return "Medium Priority"
    elif row["Effective Quantity"] < row["Max. Quantity"]:
        return "Low Priority"
    else:
        return "OK"

def background_by_status(x):
    c_critical = 'background-color: #FFCDD2'
    c_high = 'background-color: #FFF3CD'
    c_medium = 'background-color: #FFF9C4'
    c_low = 'background-color: #C8E6C9'
    c_ok = ''

    c_df = pd.DataFrame('', index=x.index, columns=x.columns)
    c_df.loc[x["Status"] == "Critical"] = c_critical
    c_df.loc[x["Status"] == "High Priority"] = c_high
    c_df.loc[x["Status"] == "Medium Priority"] = c_medium
    c_df.loc[x["Status"] == "Low Priority"] = c_low
    c_df.loc[x["Status"] == "OK"] = c_ok

    return c_df

def color_by_status(x):
    c_critical = 'color: #ab3e41'
    c_high = 'color: #957313'
    c_medium = 'color: #957313'
    c_low = 'color: #957313'
    c_ok = ''

    c_df = pd.DataFrame('', index=x.index, columns=x.columns)
    c_df.loc[x["Status"] == "Critical"] = c_critical
    c_df.loc[x["Status"] == "High Priority"] = c_high
    c_df.loc[x["Status"] == "Medium Priority"] = c_medium
    c_df.loc[x["Status"] == "Low Priority"] = c_low
    c_df.loc[x["Status"] == "OK"] = c_ok

    return c_df

def get_operational_limits():
    df = conn.read(worksheet="first_aid_operational_limits")

    df["Min. Quantity"] = df["Min. Quantity"].astype(int)
    df["Max. Quantity"] = df["Max. Quantity"].astype(int)
    df["Location"] = df["Location"].astype(str)

    return df

def get_supply_data():
    df = conn.read(worksheet="first_aid_supplies")
    df = process_supplies(df)
    return df

def get_inventory_data():
    df = conn.read(worksheet="first_aid_inventories")
    return df

def get_audit_data():
    df = conn.read(worksheet="first_aid_audits")
    return df

def display_alerts():
    df = get_supply_data()
    summary_df = get_summary(df)
    
    # Change datetime columns to date columns
    df["Expiration Date"] = df["Expiration Date"].dt.date
    # First find the items that are expired or out of stock
    today = pd.Timestamp.today().date()
    expired_items = df[(df["Expiration Date"] < today) & (df["Date Removed"].isna())]

    if len(expired_items) > 0:
        st.error(":material/error: The following items have expired:")
        # Group the exipred items by inventory, item and expiration date
        expired_items = expired_items.groupby(["Inventory", "Item", "Expiration Date"]).size().reset_index()
        expired_items.columns = ["Inventory", "Item", "Expiration Date", "Quantity"]
        st.dataframe(expired_items.style.set_properties(**{'background-color': '#FFCDD2', 'color': '#ab3e41'}), hide_index=True)

    out_of_stock_items = summary_df[summary_df["Quantity"] == 0]
    if len(out_of_stock_items) > 0:
        st.error(":material/error: The following items are out of stock:")
        st.dataframe(out_of_stock_items.style.set_properties(**{'background-color': '#FFCDD2', 'color': '#ab3e41'}), hide_index=True)

    expiring_items = df[(df["Expiration Date"] < today + pd.Timedelta("30D")) & (df["Expiration Date"] > today) & (df["Date Removed"].isna())]
    if len(expiring_items) > 0:
        st.warning(":material/warning: The following items will expire within 30 days:")
        st.dataframe(expiring_items.style.set_properties(**{'background-color': '#FFF3CD', 'color': '#957313'}), hide_index=True)

    low_stock_items = summary_df[(summary_df["Quantity"] < summary_df["Min. Quantity"]) & (summary_df["Quantity"] > 0)]
    if len(low_stock_items) > 0:
        st.warning(":material/warning: The following items are low stock:")
        st.dataframe(low_stock_items.style.set_properties(**{'background-color': '#FFF3CD', 'color': '#957313'}), hide_index=True)

def display_inventory():
    summary_df = get_summary(get_supply_data())
    inventory_df = get_inventory_data()
    # Add a multiselect for filtering by inventory
    # Style the dataframe based on the status; rows with status OK should be green, rows with status Low Priority should be unstyled, rows with status Medium Priority should be yellow, rows with status High Priority should be orange and rows with status Critical should be red
    # Order summary_df by status

    summary_df = summary_df.sort_values("Status", ascending=True)

    inventories = ["All"]
    inventory_icons = [":material/inventory:"]
    inventories = inventories + inventory_df["Inventory"].unique().tolist()
    inventory_icons = inventory_icons + inventory_df["Icon"].unique().tolist()

    tabs = st.tabs([f"{icon} {inventory}" for inventory, icon in zip(inventories, inventory_icons)])

    for inv, tab in zip(inventories, tabs):
        inventory_df = summary_df[["Item", "Quantity", "Effective Quantity", "Min. Quantity", "Max. Quantity", "Status"]]

        if inv == "All":
            with tab:
                st.dataframe(summary_df.style.apply(background_by_status, axis=None).apply(color_by_status, axis=None), hide_index=True)
        else:
            with tab:
                inventory_df = summary_df[summary_df["Inventory"] == inv]
                st.dataframe(inventory_df.style.apply(background_by_status, axis=None).apply(color_by_status, axis=None), hide_index=True)

def add_items(inv, location, item, expiration_date, quant):
    supply_df = conn.read(worksheet="first_aid_supplies")

    new_items = pd.DataFrame({'Inventory': [inv] * quant,
                              'Location': [location] * quant,
                              'Item': [item] * quant,
                              'Expiration Date': [expiration_date] * quant,
                              'Date Added': [pd.Timestamp.today()] * quant})
    
    supply_df = pd.concat([supply_df, new_items], ignore_index=True)
    conn.update(data=supply_df)
    st.cache_data.clear()

def add_form(inv, inv_df):
    # Select items not at Max. Quantity
    items = inv_df[inv_df["Effective Quantity"] < inv_df["Max. Quantity"]]["Item"].unique()
    item = st.selectbox("Select Item", items, key=f"{inv}-add")

    location = inv_df[inv_df["Item"] == item]["Location"].values[0]

    expiration_date = st.date_input("Expiration Date", pd.Timestamp.today(), min_value=pd.Timestamp.today(), key=f"{inv}-add-{item}-expiration")

    current_quant_col, quant_add_col, post_quant_col, min_quant_col, max_quant_col = st.columns([1, 1, 1, 1, 1])
    min_quant = inv_df[inv_df["Item"] == item]["Min. Quantity"].values[0]
    max_quant = inv_df[inv_df["Item"] == item]["Max. Quantity"].values[0]
    current_quant = inv_df[inv_df["Item"] == item]["Effective Quantity"].values[0]

    with current_quant_col:
        st.write("Current Quantity")
        st.write(current_quant)

    with quant_add_col:
        max_quant_add = max_quant - current_quant
        quant = st.select_slider("Quantity Added", 
                                    options=list(range(0, max_quant_add + 1)),
                                    key=f"{inv}-add-{item}-quant")
    with post_quant_col:
        st.write("New Quantity")
        st.write(current_quant + quant)

    with min_quant_col:
        st.write("Min. Quantity")
        st.write(min_quant)

    with max_quant_col:
        st.write("Max. Quantity")
        st.write(max_quant)

    st.button("Add Item(s)", key=f"{inv}-add-{item}-button", on_click=add_items, args=(inv, location, item, expiration_date, quant), icon=":material/add:")

def remove_items(inv, item, expiration_date, quant):
    supply_df = conn.read(worksheet="first_aid_supplies").clear()
    supply_df.loc[supply_df[(supply_df["Inventory"] == inv) & (supply_df["Item"] == item) & (supply_df["Expiration Date"] == expiration_date)].sample(quant).index, "Date Removed"] = pd.Timestamp.today()
    conn.update(data=supply_df)
    st.cache_data.clear()


def remove_form(inv, inv_df):
    items = inv_df["Item"].unique()
    item = st.selectbox("Select Item", items, key=f"{inv}-remove")

    item_df = inv_df[inv_df["Item"] == item]
    expiration_date = st.selectbox("Expiration Date", item_df[item_df["Item"] == item]["Expiration Date"].unique(), key=f"{inv}-remove-{item}-expiration", format_func=lambda x: x.strftime("%Y/%m/%d"))

    # Add two boxes which depend on eachother. One shows quantity being added, one shows quantity after addition
    current_quant_col, quant_remove_col, post_quant_col, min_quant_col, max_quant_col = st.columns([1, 1, 1, 1, 1])
    current_quant = len(item_df[item_df["Expiration Date"] == expiration_date])

    with current_quant_col:
        st.write("Current Quantity")
        st.write(current_quant)

    with quant_remove_col:
        quant = st.select_slider("Quantity Removed", 
                                    options=list(range(0, current_quant + 1)),
                                    key=f"{inv}-remove-{item}-quant")
    with post_quant_col:
        st.write("New Quantity")
        st.write(current_quant - quant)

    st.button("Remove Item(s)", key=f"{inv}-remove-{item}-button", on_click=add_items, args=(inv, item, expiration_date, quant), icon=":material/remove:")

def manage_inventory():
    # Make a form for adding or removing items
    supply_df = get_supply_data()
    inventory_df = get_inventory_data()
    summary_df = get_summary(supply_df)

    inventories = inventory_df["Inventory"].unique()
    inventory_icons = inventory_df["Icon"].unique()

    actions = ["Add", "Remove"]
    action_icons = [":material/add:", ":material/remove:"]

    inv_tabs = st.tabs([f"{icon} {inventory}" for inventory, icon in zip(inventories, inventory_icons)])

    for inv, inv_tab in zip(inventories, inv_tabs):
        with inv_tab:
            add_tab, remove_tab = st.tabs([f"{icon} {action}" for action, icon in zip(actions, action_icons)])

            with add_tab:
                add_form(inv, summary_df[summary_df["Inventory"] == inv])

            with remove_tab:
                remove_form(inv, supply_df[supply_df["Inventory"] == inv])

def change_loc(loc):
    loc_idx = loc

def audit_inventory():
    ## An audit for an inventory should list each item recoreded in the inventory and allow the user to:
    ## - Confirm the existence of the item
    ## - Flag the item as missing and remove it from the inventory

    supply_df = get_supply_data()
    inventory_df = get_inventory_data()
    operational_df = get_operational_limits()

    inventories = inventory_df["Inventory"].unique()
    inventory_icons = inventory_df["Icon"].unique()

    inv_tabs = st.tabs([f"{icon} {inventory}" for inventory, icon in zip(inventories, inventory_icons)])

    for inv, inv_tab in zip(inventories, inv_tabs):
        locations = operational_df[operational_df["Inventory"] == inv]["Location"].unique()
        with inv_tab:
            start = False
            if not start:
                start =  st.button("Begin Audit", key=f"{inv}-audit-begin", icon=":material/play_circle:")
            if start == True:
                loc_idx = 0
                if loc_idx > 1:
                    st.button("Next", key=f"{inv}-audit-next", on_click=change_loc, args=(locations), icon=":material/arrow_forward:")
                if loc_idx < len(locations) - 1:
                    st.button("Previous", key=f"{inv}-audit-prev", on_click=change_loc, args=(locations), icon=":material/arrow_back:")
            

st.title("Manage First-Aid Supplies")
st.write("This section allows you to track and manage first aid supplies.")

alerts, overview, manage, audit = st.tabs([":material/warning: **Alerts**", ":material/overview: **Overview**", ":material/update: **Add/Remove Items**", ":material/search_check_2: **Audit**"])

with alerts:
    display_alerts()

with overview:
    display_inventory()

with manage:
    manage_inventory()

with audit:
    audit_inventory()