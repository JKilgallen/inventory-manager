import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(
    page_title="First-Aid Supplies",
    page_icon=":material/medical_services:"
)

conn = st.connection("gsheets", type=GSheetsConnection, ttl=60)

# Reconnect if the remote end closes the connection
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
    df = df[df["Date Removed"].isna()].copy()
    df["Date Added"] = pd.to_datetime(df["Date Added"], format="%d/%m/%Y %H:%M:%S")
    df["Expiration Date"] = pd.to_datetime(df["Expiration Date"], format="%m-%Y")
    return df


def get_status(row):
    if row["Quantity Remaining"] == 0:
        return "Out of Stock"
    elif row["Quantity Expired"] > 0:
        return "Expired"
    elif row["Quantity Remaining"] <= row["Min. Quantity"]:
        return "Running Low"
    elif row["Quantity Expiring"] > 0:
        return "Expiring"
    elif row["Quantity Remaining"] < row["Max. Quantity"]:
        return "Understocked"
    else:
        return "Fully Stocked"

def style_by_status(x):
    c_out_of_stock = '{background-color: #FFCDD2; color: #ab3e41;'
    c_expired = 'background-color: #FFCDD2; color: #ab3e41;'
    c_running_low = 'background-color: #FFF3CD; color: #957313;'
    c_expiring = 'background-color: #FFF9C4; color: #957313;'
    c_fully_stocked = 'background-color: #C8E6C9; color: #4CAF50;'
    c_understocked = ''

    c_df = pd.DataFrame('', index=x.index, columns=x.columns)
    c_df.loc[x["Status"] == "Out of Stock"] = c_out_of_stock
    c_df.loc[x["Status"] == "Expired"] = c_expired
    c_df.loc[x["Status"] == "Running Low"] = c_running_low
    c_df.loc[x["Status"] == "Expiring"] = c_expiring
    c_df.loc[x["Status"] == "Fully Stocked"] = c_fully_stocked
    c_df.loc[x["Status"] == "Understocked"] = c_understocked

    return c_df

def get_operational_limits():
    df = conn.read(worksheet="first_aid_operational_limits")

    df["Min. Quantity"] = df["Min. Quantity"].astype(int)
    df["Max. Quantity"] = df["Max. Quantity"].fillna(df["Min. Quantity"] * 10)
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

def get_alert_df():
    # Build a df with the following cols:
    # Inventory, Location, Item, Quantity, Quantity Expired, Quantity Expiring, Min. Quantity
    supply_df = get_supply_data()
    op_df = get_operational_limits()

    alert_df = supply_df.loc[supply_df["Date Removed"].isna()]
    alert_df["Expiration Date"] = alert_df["Expiration Date"].dt.date

    today = pd.Timestamp.today().date()

    alert_df["Expired"] = alert_df["Expiration Date"] < today
    alert_df["Expiring"] = (alert_df["Expiration Date"] < today + pd.Timedelta("30D")) & (alert_df["Expiration Date"] > today)
    alert_df = alert_df.groupby(["Inventory", "Location", "Item"]).agg(
        quantity = ("Item", "count"),
        expiring = ("Expiring", "sum"),
        expired = ("Expired", "sum"),
    ).reset_index()
    alert_df = alert_df.merge(op_df, on=["Inventory", "Location", "Item"], how="right", suffixes=("_x", None))
    alert_df["quantity"] = alert_df["quantity"].fillna(0).astype(int)
    alert_df["expiring"] = alert_df["expiring"].fillna(0).astype(int)
    alert_df["expired"] = alert_df["expired"].fillna(0).astype(int)
    alert_df["Min. Quantity"] = alert_df["Min. Quantity"].astype(int)
    alert_df["Max. Quantity"] = alert_df["Max. Quantity"].astype(int)
    alert_df["Quantity Remaining"] = alert_df["quantity"] - alert_df["expired"]

    alert_df = alert_df[['Inventory', 'Location', 'Item', 'quantity', 'expired', 'expiring', 'Min. Quantity', 'Max. Quantity', "Quantity Remaining"]]
    alert_df.columns = ['Inventory', 'Location', 'Item', 'Quantity', 'Quantity Expired', 'Quantity Expiring', 'Min. Quantity', 'Max. Quantity', "Quantity Remaining"]

    alert_df["Status"] = alert_df.apply(get_status, axis=1)

    return alert_df


def display_alerts():
    alert_df = get_alert_df()

    expired_items = alert_df[alert_df["Status"] == "Expired"]
    if len(expired_items) > 0:
        st.error(":material/error: The following items have expired:")
        expired_items = expired_items[['Inventory', 'Location', 'Item', 'Quantity Expired', 'Quantity Remaining', 'Min. Quantity']]
        st.dataframe(expired_items.style.set_properties(**{'background-color': '#FFCDD2', 'color': '#ab3e41'}), hide_index=True)

    out_of_stock_items = alert_df[alert_df["Status"] == "Out of Stock"]
    if len(out_of_stock_items) > 0:  
        out_of_stock_items = out_of_stock_items[['Inventory', 'Location', 'Item', 'Min. Quantity']]

        st.error(":material/error: The following items are out of stock:")
        st.dataframe(out_of_stock_items.style.set_properties(**{'background-color': '#FFCDD2', 'color': '#ab3e41'}), hide_index=True)

    expiring_items = alert_df[alert_df["Status"] == "Expiring"]
    if len(expiring_items) > 0:
        expiring_items["Quantity Remaining"] = expiring_items["Quantity"] - expiring_items["Quantity Expiring"]
        expiring_items = expiring_items[['Inventory', 'Location', 'Item', 'Quantity Expiring', 'Quantity Remaining', 'Min. Quantity']]

        st.warning(":material/warning: The following items will expire within 30 days:")
        st.dataframe(expiring_items.style.set_properties(**{'background-color': '#FFF3CD', 'color': '#957313'}), hide_index=True)
    
    low_stock_items = alert_df[alert_df["Status"] == "Running Low"]
    if len(low_stock_items) > 0:
        low_stock_items = low_stock_items[['Inventory', 'Location', 'Item', 'Quantity Remaining', 'Min. Quantity']]

        st.warning(":material/warning: The following items are running low:")
        st.dataframe(low_stock_items.style.set_properties(**{'background-color': '#FFF3CD', 'color': '#957313'}), hide_index=True)

def display_inventory():
    summary_df = get_alert_df()
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
        inventory_df = summary_df[["Item", "Quantity", "Min. Quantity", "Status"]]

        if inv == "All":
            with tab:
                st.dataframe(summary_df.style.apply(style_by_status, axis=None), hide_index=True, 
                             column_order= ["Inventory", "Location", "Item", "Quantity", "Min. Quantity", "Status"])
        else:
            with tab:
                inventory_df = summary_df[summary_df["Inventory"] == inv]
                st.dataframe(inventory_df.style.apply(style_by_status, axis=None), hide_index=True)


def add_items(inv, location, item, expiration_date, quant):
    with st.spinner("Adding items..."):
        supply_df = conn.read(worksheet="first_aid_supplies")

        new_items = pd.DataFrame({'Inventory': [inv] * quant,
                                'Location': [location] * quant,
                                'Item': [item] * quant,
                                'Expiration Date': [expiration_date] * quant,
                                'Date Added': [pd.Timestamp.today()] * quant})
        
        supply_df = pd.concat([supply_df, new_items], ignore_index=True)
        conn.update(data=supply_df, worksheet="first_aid_supplies")
        st.cache_data.clear()

def add_form(inv):

    inv_df = get_alert_df()
    inv_df = inv_df[inv_df["Inventory"] == inv]
    min_filter, max_filter = st.select_slider("Filter by stock level", ["Out of stock", "Running low", "Understocked", "Fully stocked"], 
                                                value=("Out of stock", "Fully stocked"), key=f"{inv}-add-filter")

    if min_filter != "Out of stock":
        inv_df = inv_df[inv_df["Status"] != "Out of Stock"]
        if min_filter != "Running low":
            inv_df = inv_df[inv_df["Status"] != "Running Low"]
            if min_filter != "Understocked":
                inv_df = inv_df[inv_df["Status"] != "Understocked"]

    if max_filter != "Fully stocked":
        inv_df = inv_df[inv_df["Status"] != "Fully Stocked"]
        if max_filter != "Understocked":
            inv_df = inv_df[inv_df["Status"] != "Understocked"]
            if max_filter != "Running low":
                inv_df = inv_df[inv_df["Status"] != "Running Low"]
    
    # Select items not at Max. Quantity
    items = inv_df[inv_df["Quantity"] < inv_df["Max. Quantity"]]["Item"].unique()
    if len(items) == 0:
        st.info("This inventory is at maximum capacity.")
    else:
        item = st.selectbox("Select Item", items, key=f"{inv}-add")
        
        location = inv_df[inv_df["Item"] == item]["Location"].values[0]

        expiration_date = st.date_input("Expiration Date", pd.Timestamp.today(), min_value=pd.Timestamp.today(), key=f"{inv}-add-{item}-expiration")

        current_quant_col, quant_add_col, post_quant_col, min_quant_col, max_quant_col = st.columns([1, 1, 1, 1, 1])
        min_quant = inv_df[inv_df["Item"] == item]["Min. Quantity"].values[0]
        max_quant = inv_df[inv_df["Item"] == item]["Max. Quantity"].values[0]
        current_quant = inv_df[inv_df["Item"] == item]["Quantity"].values[0]

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

        signature = st.text_input("Signature", key=f"{inv}-add-{item}-signature", value=st.session_state.get("signature", ""))
        if not st.session_state.get("signature", False):
            st.session_state.signature = signature
        st.button("Add Item(s)", key=f"{inv}-add-{item}-button", 
                on_click=add_items, args=(inv, location, item, expiration_date, quant), icon=":material/add:",
                    disabled= signature == "")

def mark_removed(inv, items, expiration_dates, signature):
    with st.spinner("Removing items..."):
        supply_df = conn.read(worksheet="first_aid_supplies")
        # Groupby item and expiration date and add count
        remove_df = pd.DataFrame({"Item": items, "Expiration Date": expiration_dates})
        remove_df = remove_df.groupby(["Item", "Expiration Date"]).size().reset_index()

        expiration_dates = pd.to_datetime(supply_df["Expiration Date"], format="%m-%Y").dt.date
        for _, row in remove_df.iterrows():
            item, expiration_date, quant = row["Item"], row["Expiration Date"], row[0]
            idxs = supply_df.loc[
                (supply_df["Inventory"] == inv) &
                (supply_df["Item"] == item) &
                (expiration_dates == expiration_date) &
                (supply_df["Date Removed"].isna())
            ].head(quant).index
            supply_df.loc[idxs, "Date Removed"] = pd.Timestamp.today()
            supply_df.loc[idxs, "Removed By"] = signature
        
        conn.update(data=supply_df, worksheet="first_aid_supplies")
        st.cache_data.clear()


def remove_form(inv):

    inv_df = get_supply_data()
    inv_df = inv_df[inv_df["Inventory"] == inv]
    inv_df["Expiration Date"] = inv_df["Expiration Date"].copy().dt.date
    min_filter, max_filter = st.select_slider("Filter by expiration", ["Expired", "1 month", "6 months", "1 year", "> 1 year"],
                                                value=("Expired", "> 1 year"), key=f"{inv}-remove-filter")

    today = pd.Timestamp.today().date()
    if min_filter == "1 month":
        inv_df = inv_df[inv_df["Expiration Date"] > today]
    elif min_filter == "6 months":
        inv_df = inv_df[inv_df["Expiration Date"] >= today + pd.Timedelta("30D")]
    elif min_filter == "1 year":
        inv_df = inv_df[inv_df["Expiration Date"] >= today + pd.Timedelta("182D")]
    elif min_filter == "> 1 year":
        inv_df = inv_df[inv_df["Expiration Date"] >= today + pd.Timedelta("365D")]
    
    if max_filter == "1 year":
        inv_df = inv_df[inv_df["Expiration Date"] < today + pd.Timedelta("365D")]
    elif max_filter == "6 months":
        inv_df = inv_df[inv_df["Expiration Date"] < today + pd.Timedelta("182D")]
    elif max_filter == "1 month":
        inv_df = inv_df[inv_df["Expiration Date"] < today + pd.Timedelta("30D")]
    elif max_filter == "Expired":
        inv_df = inv_df[inv_df["Expiration Date"] < today]

    items = inv_df["Item"].unique()
    if len(items) == 0:
        st.info("There are not items in this inventory to remove.")
        return
    else:
        item = st.selectbox("Select Item", items, key=f"{inv}-remove")

        item_df = inv_df[inv_df["Item"] == item]
        
        expiration_labels = item_df.value_counts("Expiration Date").reset_index()
        expiration_labels = list(zip(expiration_labels["Expiration Date"], expiration_labels["count"]))

        expiration_date, _ = st.selectbox("Expiration Date", expiration_labels, key=f"{inv}-remove-{item}-expiration", format_func=lambda x: f"{x[0].strftime("%Y/%m/%d")} ({x[1]})")

        # Add two boxes which depend on eachother. One shows quantity being added, one shows quantity after addition
        current_quant_col, quant_remove_col, post_quant_col = st.columns([1, 1, 1])
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

        signature = st.text_input("Signature", key=f"{inv}-remove-{item}-signature", value=st.session_state.get("signature", ""))
        if not st.session_state.get("signature", False):
            st.session_state.signature = signature
        st.button("Remove Item(s)", key=f"{inv}-remove-{item}-button", 
                on_click=mark_removed, args=(inv, [item] * quant, [expiration_date] * quant, signature), icon=":material/remove:",
                disabled= signature == "")

def manage_inventory():
    inventory_df = get_inventory_data()

    inventories = inventory_df["Inventory"].unique()
    inventory_icons = inventory_df["Icon"].unique()

    actions = ["Add", "Remove"]
    action_icons = [":material/add:", ":material/remove:"]

    inv_tabs = st.tabs([f"{icon} {inventory}" for inventory, icon in zip(inventories, inventory_icons)])

    for inv, inv_tab in zip(inventories, inv_tabs):
        with inv_tab:
            add_tab, remove_tab = st.tabs([f"{icon} {action}" for action, icon in zip(actions, action_icons)])

            with add_tab:
                add_form(inv)

            with remove_tab:
                remove_form(inv)

def submit_audit(inv, loc_audits, signature):
    audit_df = conn.read(worksheet="first_aid_audits")
    
    items = []
    expiration_dates = []
    for loc, loc_audit in loc_audits.items():
        loc_audit["Inventory"] = inv
        loc_audit["Location"] = loc
        loc_audit["Present"] = loc_audit["Present"].astype(bool)
        loc_audit["Date Audited"] = pd.Timestamp.today()
        loc_audit["Audited By"] = signature
        audit_df = pd.concat([audit_df, loc_audit], ignore_index=True)

        missing_items = loc_audit[loc_audit["Present"] == False]
        items.extend(missing_items["Item"].tolist())
        expiration_dates.extend(missing_items["Expiration Date"].tolist())
    
    mark_removed(inv, items, expiration_dates, signature)

    audit_df = audit_df.reset_index(drop=True)
    conn.update(data=audit_df, worksheet="first_aid_audits")
    st.cache_data.clear()

    


def audit_inventory():
    # An audit for an inventory should list each item recoreded in the inventory and allow the user to:
    ## - Confirm the existence of the item
    ## - Flag the item as missing and remove it from the inventory

    supply_df = get_supply_data()
    inventory_df = get_inventory_data()
    operational_df = get_operational_limits()

    inventories = inventory_df["Inventory"].unique()
    inventory_icons = inventory_df["Icon"].unique()

    inv_tabs = st.tabs([f"{icon} {inventory}" for inventory, icon in zip(inventories, inventory_icons)])

    for inv, inv_tab in zip(inventories, inv_tabs):
        with inv_tab:
            locations = operational_df[operational_df["Inventory"] == inv]["Location"].unique().tolist()

            loc_audits = {}
            for loc in locations:
                st.write(f"**{loc}**")
                loc_df = supply_df[(supply_df["Inventory"] == inv) & (supply_df["Location"] == loc)]
                # Groupby item and add count
                loc_df = loc_df[["Item", "Expiration Date"]]
                loc_df["Expiration Date"] = loc_df["Expiration Date"].dt.date
                loc_df["Present"] = False

                loc_audits[loc] = st.data_editor(
                    loc_df,
                    column_config={
                        "Present": st.column_config.CheckboxColumn(
                            "Present",
                            help="Check off items that are present",
                            default=False,
                            width="small"
                        ),
                        "Item": st.column_config.TextColumn(
                            "Item",
                            help="Item name",
                            width="medium"
                        ),
                        "Expiration Date": st.column_config.DateColumn(
                            "Expiration Date",
                            help="Expiration Date",
                            width="small"
                        )

                    },
                    disabled=["Item", "Expiration Date"],
                    hide_index=True,
                    use_container_width=True,
                    key=f"{inv}-{loc}",
                )

            signature = st.text_input("Signature", key=f"{inv}-audit-signature", value=st.session_state.get("signature", ""))
            if not st.session_state.get("signature", False):
                st.session_state.signature = signature
            st.button("Submit Audit", key=f"{inv}-audit-submit", 
                    on_click=submit_audit, args=(inv, loc_audits, signature), icon=":material/check_circle:",
                    disabled= signature == "")


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
