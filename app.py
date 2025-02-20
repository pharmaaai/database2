import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests

# Google API Scopes (Sheets & Drive)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Authenticate Google Sheets
@st.cache_resource
def get_gsheet_client():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Google Authentication Error: {e}")
        return None

# Fetch Data from Google Sheets
@st.cache_data
def fetch_data(sheet_name):
    client = get_gsheet_client()
    if client:
        try:
            sheet = client.open(sheet_name).sheet1
            data = sheet.get_all_records()
            df = pd.DataFrame(data)

            # Convert "Years of Experience" to numeric
            if "Years of Experience" in df.columns:
                df["Years of Experience"] = pd.to_numeric(df["Years of Experience"], errors="coerce").fillna(0)
            
            return df
        except Exception as e:
            st.error(f"Error fetching data: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# PayPal Payment Processing
def process_paypal_payment(amount):
    try:
        paypal_creds = st.secrets["paypal"]
        paypal_client_id = paypal_creds["PAYPAL_CLIENT_ID"]
        paypal_secret = paypal_creds["PAYPAL_SECRET"]
        paypal_mode = paypal_creds.get("PAYPAL_MODE", "sandbox")  # Default to sandbox

        # Select API URL based on mode
        base_url = "https://api-m.sandbox.paypal.com" if paypal_mode == "sandbox" else "https://api-m.paypal.com"

        # Authenticate with PayPal
        auth_response = requests.post(
            f"{base_url}/v1/oauth2/token",
            headers={"Accept": "application/json", "Accept-Language": "en_US"},
            data={"grant_type": "client_credentials"},
            auth=(paypal_client_id, paypal_secret),
        )

        if auth_response.status_code != 200:
            st.error(f"PayPal Authentication Failed: {auth_response.text}")
            return None

        access_token = auth_response.json().get("access_token")

        # Create PayPal Order
        payment_response = requests.post(
            f"{base_url}/v2/checkout/orders",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "intent": "CAPTURE",
                "purchase_units": [{"amount": {"currency_code": "USD", "value": amount}}]
            },
        )

        if payment_response.status_code == 201:
            order_data = payment_response.json()
            return order_data.get("links", [])[1]["href"]  # Payment URL
        else:
            st.error(f"Failed to create PayPal order: {payment_response.text}")
            return None

    except Exception as e:
        st.error(f"PayPal API Error: {e}")
        return None

# Main Application
def main():
    st.title("Biotech Job Search Platform")

    # Load Data
    SHEET_NAME = "Database"
    df = fetch_data(SHEET_NAME)

    if df.empty:
        st.warning("No data available.")
        return

    # User Filters
    st.subheader("Search Jobs")

    job_title = st.text_input("Job Title")
    location = st.text_input("Location")
    min_experience, max_experience = st.slider("Years of Experience", 0, 20, (0, 10))

    # Apply Filters
    filtered_df = df[
        (df["Job Title"].str.contains(job_title, case=False, na=False)) &
        (df["Location"].str.contains(location, case=False, na=False)) &
        (df["Years of Experience"].between(min_experience, max_experience))
    ]

    num_results = len(filtered_df)
    st.info(f"Matching Results: {num_results}")

    if num_results == 0:
        st.warning("No matching jobs found. Try adjusting your filters.")
        return

    # Pricing Logic
    max_rows = min(num_results, 2000)  # Max limit 2000 rows
    rows_selected = st.slider("Select Number of Rows to Purchase", 25, max_rows, 25, 25)
    price = (rows_selected // 25) * 1  # $1 per 25 rows

    # Payment Button
    if st.button(f"Pay ${price} to Unlock {rows_selected} Rows"):
        payment_url = process_paypal_payment(price)
        if payment_url:
            st.success("Payment link generated. Click below:")
            st.markdown(f"[Pay Now]({payment_url})", unsafe_allow_html=True)
        else:
            st.error("Payment failed. Try again.")

# Run Application
if __name__ == "__main__":
    main()
