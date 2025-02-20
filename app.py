import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import json

# 🔹 Define Google API Scopes
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# 🔹 Authenticate Google Sheets
@st.cache_resource
def get_gsheet_client():
    try:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Google Authentication Error: {e}")
        return None

# 🔹 Fetch Data from Google Sheets
@st.cache_data
def fetch_data(sheet_name):
    client = get_gsheet_client()
    if not client:
        return None
    try:
        sheet = client.open(sheet_name).sheet1
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"❌ Failed to fetch data: {e}")
        return None

# 🔹 Main Function
def main():
    st.title("💼 H1B Visa & Job Data Marketplace")

    # Load Data
    df = fetch_data("H1B_Job_Data")
    if df is None or df.empty:
        st.error("❌ No data available. Please try again later.")
        return

    # Ensure correct columns exist
    required_columns = {"EMPLOYER_NAME", "JOB_TITLE", "WAGE_RATE_OF_PAY_FROM"}
    if not required_columns.issubset(df.columns):
        st.error("❌ Missing required columns in the dataset!")
        return

    # User Query Input
    employer_name = st.text_input("🔍 Enter Employer Name (Optional):").strip()
    job_title = st.text_input("🔍 Enter Job Title (Optional):").strip()
    salary_range = st.number_input("💰 Minimum Salary (USD):", min_value=0, step=1000)

    # Filter Data
    query = True
    if employer_name:
        query &= df["EMPLOYER_NAME"].str.contains(employer_name, case=False, na=False)
    if job_title:
        query &= df["JOB_TITLE"].str.contains(job_title, case=False, na=False)
    if salary_range > 0:
        query &= df["WAGE_RATE_OF_PAY_FROM"] >= salary_range

    df_filtered = df[query]

    # Show Count of Matching Records
    num_records = len(df_filtered)
    st.info(f"✅ {num_records} matching job records found.")

    # Pricing Calculation
    price_per_row = 0.04
    total_price = max(num_records * price_per_row, 5.00)  # Minimum $5
    st.write(f"💲 Total Cost: **${total_price:.2f}**")

    # Payment Processing (Razorpay)
    if st.button("Proceed to Payment"):
        order_data = {
            "amount": int(total_price * 100),  # Convert to cents
            "currency": "USD",
            "receipt": "job_data_purchase"
        }

        headers = {
            "Authorization": f"Basic {st.secrets['razorpay_api_key']}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            "https://api.razorpay.com/v1/orders",
            headers=headers,
            data=json.dumps(order_data)
        )

        if response.status_code == 200:
            payment_link = response.json().get("short_url", "#")
            st.success(f"✅ Payment Successful! Download your data: [Click Here]({payment_link})")
        else:
            st.error("❌ Payment Failed. Please try again.")

if __name__ == "__main__":
    main()
