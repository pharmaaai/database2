import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests

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

# 🔹 Fetch Data from Google Sheets (with validation)
@st.cache_data
def fetch_data(sheet_name):
    client = get_gsheet_client()
    if not client:
        return pd.DataFrame()

    try:
        sheet = client.open(sheet_name).sheet1  # Open the first sheet
        data = sheet.get_all_records()

        if not data:
            st.warning("⚠ No data found in Google Sheets.")
            return pd.DataFrame()

        return pd.DataFrame(data)

    except Exception as e:
        st.error(f"❌ Error fetching data: {e}")
        return pd.DataFrame()

# 🔹 PayPal Payment Processing
def process_paypal_payment(amount, currency="USD"):
    try:
        paypal_creds = st.secrets["paypal"]
        PAYPAL_CLIENT_ID = paypal_creds["PAYPAL_CLIENT_ID"]
        PAYPAL_SECRET = paypal_creds["PAYPAL_SECRET"]
        PAYPAL_MODE = paypal_creds.get("PAYPAL_MODE", "sandbox")

        PAYPAL_BASE_URL = "https://api-m.sandbox.paypal.com" if PAYPAL_MODE == "sandbox" else "https://api-m.paypal.com"

        # Get PayPal Access Token
        auth_response = requests.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            headers={"Accept": "application/json", "Accept-Language": "en_US"},
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={"grant_type": "client_credentials"}
        )

        if auth_response.status_code != 200:
            st.error("❌ Failed to authenticate PayPal")
            return None

        access_token = auth_response.json().get("access_token")

        # Create Payment Order
        payment_response = requests.post(
            f"{PAYPAL_BASE_URL}/v2/checkout/orders",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"},
            json={"intent": "CAPTURE", "purchase_units": [{"amount": {"currency_code": currency, "value": amount}}]}
        )

        if payment_response.status_code == 201:
            order_data = payment_response.json()
            return order_data.get("links", [])[1]["href"]  # Approval URL
        else:
            st.error("❌ Failed to create PayPal order")
            return None

    except Exception as e:
        st.error(f"❌ PayPal API Error: {e}")
        return None

# 🔹 Main Function
def main():
    st.title("📊 H1B Visa Job Listings & Secure Payment")

    # 🔹 Fetch Data from Google Sheets
    SHEET_NAME = "Database"  # Update with your sheet name
    df = fetch_data(SHEET_NAME)

    if df.empty:
        st.warning("⚠ No data available. Check Google Sheets or API credentials.")
        return

    # 🔹 Normalize column names for robust access
    df.columns = df.columns.str.lower().str.strip()

    # 🔹 Define Columns to Search
    required_columns = [
        "company_name", "job_title", "wage_rate_of_pay_from"
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        st.error(f"❌ Missing columns in Google Sheet: {', '.join(missing_columns)}")
        return

    # 🔹 User Input for Search
    st.subheader("🔍 Search for Jobs")
    company_name = st.text_input("Enter Company Name:")
    job_role = st.text_input("Enter Job Role:")
    salary_min = st.number_input("Enter Minimum Salary ($):", min_value=0, step=5000)

    if st.button("Search"):
        if not company_name or not job_role or salary_min <= 0:
            st.warning("⚠ Please enter all fields correctly.")
            return

        # 🔹 Filter Data Based on User Input
        df_filtered = df[
            (df["company_name"].str.contains(company_name, case=False, na=False)) &
            (df["job_title"].str.contains(job_role, case=False, na=False)) &
            (df["wage_rate_of_pay_from"] >= salary_min)
        ]

        num_results = len(df_filtered)

        if num_results == 0:
            st.warning("⚠ No matching jobs found.")
            return

        # 🔹 Show Available Count
        st.success(f"✅ Found {num_results} job listings.")

        # 🔹 Calculate Price ($0.04 per row, min $5)
        total_price = max(5, num_results * 0.04)
        st.write(f"💲 Price: **${total_price:.2f}** for {num_results} job listings.")

        if st.button("Pay with PayPal"):
            payment_url = process_paypal_payment(total_price)
            if payment_url:
                st.success("✅ Payment link generated! Click below:")
                st.markdown(f"[Pay Now]({payment_url})", unsafe_allow_html=True)
            else:
                st.error("⚠ Payment failed. Try again.")

# 🔹 Run the app
if __name__ == "__main__":
    main()
