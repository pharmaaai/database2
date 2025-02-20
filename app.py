import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# Google Sheets API Credentials
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# Function to connect to Google Sheets
@st.cache_resource
def connect_to_sheets():
    try:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ Failed to connect to Google Sheets: {e}")
        return None

# Function to fetch data
def fetch_data():
    client = connect_to_sheets()
    if not client:
        return None

    try:
        sheet = client.open("H1B_Job_Data").sheet1  # Ensure this matches your actual sheet name
        data = sheet.get_all_records()  # Fetch data as a list of dictionaries
        return pd.DataFrame(data) if data else None
    except Exception as e:
        st.error(f"❌ Failed to fetch data: {e}")
        return None

# Streamlit UI
st.title("H1B Job Data Search")

# Load data
df = fetch_data()
if df is None or df.empty:
    st.error("❌ No data available. Please try again later.")
    st.stop()

# Ensure required columns exist
REQUIRED_COLUMNS = {"EMPLOYER_NAME", "JOB_TITLE", "WAGE_RATE_OF_PAY_FROM"}
if not REQUIRED_COLUMNS.issubset(df.columns):
    st.error("❌ Data format issue: Required columns are missing.")
    st.stop()

# User Input Fields
st.subheader("🔍 Search for H1B Job Data")
employer_name = st.text_input("Enter Employer Name (or leave blank for all)")
job_title = st.text_input("Enter Job Title (or leave blank for all)")
salary_range = st.number_input("Minimum Salary ($)", min_value=0, step=1000, value=0)

# Filter Data
filtered_df = df[
    (df["EMPLOYER_NAME"].str.contains(employer_name, case=False, na=False) if employer_name else True) &
    (df["JOB_TITLE"].str.contains(job_title, case=False, na=False) if job_title else True) &
    (df["WAGE_RATE_OF_PAY_FROM"] >= salary_range)
]

# Show results summary
num_records = len(filtered_df)
st.write(f"🔹 **Matching Records:** {num_records}")

if num_records > 0:
    # Pricing calculation
    total_price = max(num_records * 0.04, 5)  # $0.04 per row, minimum $5
    st.write(f"💰 **Price: ${total_price:.2f}**")

    # Payment Button
    if st.button("Proceed to Payment"):
        st.success("✅ Payment processing... You will receive access after confirmation.")
else:
    st.warning("⚠️ No matching records found. Try different search criteria.")
