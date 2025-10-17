import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta

# ------------------------
# Page Setup
# ------------------------
st.set_page_config(page_title="Customer Counter", layout="centered", initial_sidebar_state="collapsed")

# ------------------------
# 🔒 Password Authentication
# ------------------------
try:
    PASSWORD = st.secrets["auth"]["password"]
except KeyError:
    st.error("Authentication password is not set in secrets.toml.")
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Customer Counter (Login)")
    st.write("Please enter the password set in Streamlit Cloud secrets.")
    pw = st.text_input("Password", type="password")
    if pw:
        if pw == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()

# ------------------------
# ✅ Google Sheet Connection
# ------------------------
@st.cache_resource
def connect_to_google_sheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=scope
        )
        gc = gspread.authorize(credentials)
        return gc
    except Exception as e:
        st.error("Failed to authenticate with Google Sheets. Please check your secrets.toml settings.")
        st.error(f"Details: {e}")
        return None

@st.cache_data(ttl=30)
def get_sheet_data(_worksheet):
    all_values = _worksheet.get_all_values()
    expected_headers = ['Timestamp', 'Count']
    if len(all_values) > 1:
        headers = all_values[0]
        if headers != expected_headers:
            st.warning(f"The spreadsheet headers are not as expected. Expected: {expected_headers}, Found: {headers}")
        df = pd.DataFrame(all_values[1:], columns=expected_headers)
        return df
    else:
        return pd.DataFrame(columns=expected_headers)

gc = connect_to_google_sheet()
if gc is None:
    st.stop()

try:
    SPREADSHEET_NAME = "customer_counter"
    sh = gc.open(SPREADSHEET_NAME)
    worksheet = sh.sheet1
except gspread.exceptions.SpreadsheetNotFound:
    st.error(f"Spreadsheet '{SPREADSHEET_NAME}' not found.")
    st.info("Please create a spreadsheet with the specified name and share it with the service account.")
    st.stop()
except Exception as e:
    st.error(f"An error occurred while opening the spreadsheet: {e}")
    st.stop()

# ------------------------
# 📊 Data Fetching and Calculation
# ------------------------
data = get_sheet_data(worksheet)
total_visitors = 0

if data.empty:
    current_count = 0
else:
    data["Count"] = pd.to_numeric(data["Count"])
    data["Timestamp"] = pd.to_datetime(data["Timestamp"])
    current_count = data["Count"].iloc[-1]
    data["Date"] = data["Timestamp"].dt.date
    data["Hour"] = data["Timestamp"].dt.hour

    # --- ✨ Total visitors calculation logic ---
    # Calculate the difference in count from the previous row
    diffs = data["Count"].diff()
    # Sum only the positive differences (when visitors increase)
    total_visitors = int(diffs[diffs > 0].sum())


# ------------------------
# 🧮 Main Counter UI
# ------------------------
st.title("👥 Customer Counter")

# Display current count and total visitors in two columns
col_metric1, col_metric2 = st.columns(2)
with col_metric1:
    st.metric(label="Current Count", value=f"{current_count} people")
with col_metric2:
    st.metric(label="Total Visitors", value=f"{total_visitors} people", help="This is the total number of new visitors. Past visitors are included even after a reset.")

st.divider()

col_button1, col_button2 = st.columns(2)

def update_sheet(new_count):
    JST = timezone(timedelta(hours=+9))
    timestamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    try:
        worksheet.append_row([timestamp, new_count])
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Failed to write to the spreadsheet: {e}")

with col_button1:
    if st.button("+1 Person", use_container_width=True, type="primary"):
        new_count = current_count + 1
        update_sheet(new_count)
        st.success(f"Count updated to {new_count}.")
        st.rerun()

with col_button2:
    if st.button("−1 Person", use_container_width=True):
        if current_count > 0:
            new_count = current_count - 1
            update_sheet(new_count)
            st.warning(f"Count decreased to {new_count}.")
            st.rerun()
        else:
            st.warning("Current count is already 0.")

# ------------------------
# ⚙️ Admin Reset
# ------------------------
with st.expander("⚠️ Admin Reset"):
    if st.button("Reset to 0", type="secondary"):
        update_sheet(0)
        st.error("Count has been reset to 0.")
        st.rerun()

# ------------------------
# 📈 Graph Display
# ------------------------
if not data.empty:
    st.divider()
    st.subheader("📈 Data Analysis")

    st.write("Daily Visitor Trend")
    daily_counts = data.groupby("Date")["Count"].last()
    st.bar_chart(daily_counts, use_container_width=True)

    st.subheader("Hourly Visitor Changes")
    default_date = data["Date"].max()
    selected_date = st.date_input("Select a date", value=default_date)

    if selected_date:
        hourly_data = data[data["Date"] == selected_date]
        if not hourly_data.empty:
            hourly_counts = hourly_data.set_index("Timestamp")["Count"].resample("h").last().fillna(method='ffill')
            full_day_range = pd.date_range(start=pd.to_datetime(selected_date), end=pd.to_datetime(selected_date) + pd.Timedelta(hours=23), freq='h')
            hourly_counts = hourly_counts.reindex(full_day_range).fillna(0)
            hourly_counts.index = hourly_counts.index.hour
            st.bar_chart(hourly_counts, use_container_width=True)
        else:
            st.info(f"No data available for {selected_date}.")
else:
    st.info("No data has been recorded yet.")
