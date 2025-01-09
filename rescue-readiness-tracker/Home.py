import streamlit as st
from streamlit.column_config import DateColumn, NumberColumn, TextColumn
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(
    page_title="Rescue Readiness Tracker",
    page_icon=":material/done_all:"
)

st.title("Rescue Readiness Tracker")

st.markdown(
    r"""

    This platform is designed to help the **Search Units** of the **Irish Coast Guard** efficiently **track, inspect, and manage critical equipment and supplies**. From **first-aid kits** to **vehicles** and **personal protective equipment (PPE)**, this tool ensures everything is accounted for, up-to-date, and ready when needed most.

    The primary features of this platform include:

    - **:material/notification_important: Inspection Reminders**: Alerts for scheduled checks and maintenance.
    - **:material/calendar_clock: Supply Management**: Track levels and expiry dates of first aid supplies and PPE.
    - **:material/visibility: Asset Oversight**: Monitor the status of vehicles, supplies, and PPE.

    By maintaining readiness and accountability, we can ensure that all assets are ready for use, allowing us to **respond swiftly**, **operate safely**, and **provide aid effectively**.

    The platform is divided into three main sections based on the type of asset:

    - :material/medical_services: **First-Aid Supplies**: Track supplies in first aid kits and the stockroom.
    - :material/ambulance: **Vehicles**: View and record maintenance checks for the unit's vehicles.
    - :material/support: **Equipment**: Track expiration and inspection dates of equipment, and check ownership of PPE.

    Choose a section from the sidebar to get started.
    """)
