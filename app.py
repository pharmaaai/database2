import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests

# 🔹 Google API Scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# 🔹 Function to Authenticate Google Sheets
@st.cache_resource
def get_gsheet_client():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Google Authentication Error: {e}")
        return None

# 🔹 Fetch data from Google Sheets
@st.cache_data
def fetch_data(sheet_name):
    client = get_gsheet_client()
    if client:
        try:
            sheet = client.open(sheet_name).sheet1
            data = sheet.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"❌ Error fetching data: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# 🔹 PayPal Payment Function
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
            st.error("❌ PayPal Authentication Failed")
            return None

        access_token = auth_response.json().get("access_token")

        # Create PayPal Payment Order
        payment_response = requests.post(
            f"{PAYPAL_BASE_URL}/v2/checkout/orders",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            },
            json={
                "intent": "CAPTURE",
                "purchase_units": [{"amount": {"currency_code": currency, "value": amount}}]
            }
        )

        if payment_response.status_code == 201:
            order_data = payment_response.json()
            return order_data.get("links", [])[1]["href"]  # PayPal Approval Link
        else:
            st.error("⚠ PayPal Payment Failed. Try Again.")
            return None

    except Exception as e:
        st.error(f"❌ PayPal API Error: {e}")
        return None

# 🔹 Main App
def main():
    st.title("📊 Filter Job Listings & Pay for Access")

    # Fetch Data from Google Sheets
    SHEET_NAME = "Database"  # Update with your sheet name
    df = fetch_data(SHEET_NAME)

    if df.empty:
        st.warning("⚠ No job data available.")
        return

    # 🔹 Filter Options
    st.subheader("🔍 Filter Jobs")
    
    job_title = st.text_input("🔹 Job Title (Contains):")
    location = st.text_input("📍 Location (Contains):")
    min_salary = st.number_input("💰 Minimum Salary ($)", min_value=0, value=0)
    max_experience = st.number_input("⌛ Max Years of Experience:", min_value=0, value=10)

    # 🔹 Apply Filters
    filtered_df = df.copy()

    if job_title:
        filtered_df = filtered_df[filtered_df["Job Title"].str.contains(job_title, case=False, na=False)]
    if location:
        filtered_df = filtered_df[filtered_df["Location"].str.contains(location, case=False, na=False)]
    if min_salary > 0:
        filtered_df = filtered_df[filtered_df["Salary"].fillna(0).astype(float) >= min_salary]
    if max_experience < 10:
        filtered_df = filtered_df[filtered_df["Years of Experience"].fillna(0).astype(float) <= max_experience]

    # 🔹 Number of Rows After Filtering
    total_rows = len(filtered_df)
    st.info(f"✅ Found **{total_rows}** jobs matching your criteria.")

    # 🔹 Select Number of Rows to Purchase
    if total_rows > 0:
        max_rows = min(total_rows, 2000)  # Limit max purchase to 2000 rows
        num_rows = st.select_slider("📊 Select Number of Rows to Unlock:", 
                                    options=[i for i in range(25, max_rows+1, 25)], 
                                    value=25)
        price = (num_rows // 25) * 1  # $1 per 25 rows

        # 🔹 PayPal Payment Section
        st.subheader("💳 Pay for Access")
        st.write(f"💲 Price: **${price}** for {num_rows} job listings.")

        if st.button("Pay with PayPal"):
            payment_url = process_paypal_payment(price)
            if payment_url:
                st.success("✅ Payment link generated! Click below:")
                st.markdown(f"[Pay Now]({payment_url})", unsafe_allow_html=True)
                st.session_state["paid"] = True  # Mark payment as done
            else:
                st.error("⚠ Payment failed. Try again.")

        # 🔹 Show Data Only After Payment
        if "paid" in st.session_state and st.session_state["paid"]:
            st.success("✅ Payment Successful! Here are your job listings:")
            st.dataframe(filtered_df.head(num_rows))

if __name__ == "__main__":
    main()
