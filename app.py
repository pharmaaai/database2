import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests

# 🔹 Define Google API Scopes (Google Sheets + Google Drive)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# 🔹 Function to Authenticate Google Sheets
@st.cache_resource  # ✅ Caches credentials efficiently
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

# 🔹 Cached function to fetch data from Google Sheets
@st.cache_data  # ✅ Cache only the fetched data
def fetch_data(sheet_name):
    client = get_gsheet_client()
    if client:
        try:
            sheet = client.open(sheet_name).sheet1  # Open the first sheet
            data = sheet.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"❌ Error fetching data: {e}")
            return pd.DataFrame()  # Return empty DataFrame if error occurs
    return pd.DataFrame()

# 🔹 PayPal Payment Processing Function
def process_paypal_payment(amount, currency="USD"):
    try:
        # Load PayPal Credentials
        paypal_client_id = st.secrets["PAYPAL_CLIENT_ID"]
        paypal_secret = st.secrets["PAYPAL_SECRET"]

        # Get PayPal Access Token
        auth_response = requests.post(
            "https://api-m.sandbox.paypal.com/v1/oauth2/token",
            headers={"Accept": "application/json", "Accept-Language": "en_US"},
            data={"grant_type": "client_credentials"},
            auth=(paypal_client_id, paypal_secret),
        )

        if auth_response.status_code != 200:
            st.error("❌ Failed to authenticate PayPal")
            return None

        access_token = auth_response.json().get("access_token")

        # Create a Payment Order
        payment_response = requests.post(
            "https://api-m.sandbox.paypal.com/v2/checkout/orders",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "intent": "CAPTURE",
                "purchase_units": [{"amount": {"currency_code": currency, "value": amount}}],
            },
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
    st.title("📊 Google Sheets Data & PayPal Payment")

    # 🔹 Fetch Data from Google Sheets
    SHEET_NAME = "Database"  # Change to your sheet name
    df = fetch_data(SHEET_NAME)

    # 🔹 Display Data
    if not df.empty:
        st.success("✅ Data loaded successfully!")
        st.dataframe(df)
    else:
        st.warning("⚠ No data available.")

    # 🔹 PayPal Payment Section
    st.subheader("💳 Make a Payment")
    amount = st.number_input("Enter Amount (USD)", min_value=1.0, step=0.1)
    if st.button("Pay with PayPal"):
        payment_url = process_paypal_payment(amount)
        if payment_url:
            st.success("✅ Payment link generated! Click below:")
            st.markdown(f"[Pay Now]({payment_url})", unsafe_allow_html=True)
        else:
            st.error("⚠ Payment failed. Try again.")

# 🔹 Run the app
if __name__ == "__main__":
    main()
