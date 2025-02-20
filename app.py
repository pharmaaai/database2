import streamlit as st
import requests
import pandas as pd
import json

# Load PayPal credentials from secrets
PAYPAL_CLIENT_ID = st.secrets["paypal"]["PAYPAL_CLIENT_ID"]
PAYPAL_SECRET = st.secrets["paypal"]["PAYPAL_SECRET"]
PAYPAL_MODE = st.secrets["paypal"]["PAYPAL_MODE"]  # Should be 'sandbox' for testing

PAYPAL_API_URL = "https://api-m.sandbox.paypal.com" if PAYPAL_MODE == "sandbox" else "https://api-m.paypal.com"

# Define payment logic
PRICE_PER_25_ROWS = 1  # $1 per 25 rows
MAX_ROWS = 2000  # Maximum rows user can purchase
FREE_LIMIT = 0  # No free rows

# Dummy DataFrame (Replace with Google Sheets Data)
data = {
    "Company": ["Pfizer", "Moderna", "AstraZeneca", "GSK", "Novartis"],
    "Role": ["Scientist", "Analyst", "Researcher", "Manager", "Consultant"],
    "Salary": [100000, 95000, 87000, 120000, 110000],
    "Years of Experience": [5, 4, 3, 6, 7],
}
df = pd.DataFrame(data)

def authenticate_paypal():
    """Get PayPal access token"""
    auth = (PAYPAL_CLIENT_ID, PAYPAL_SECRET)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "client_credentials"}

    response = requests.post(f"{PAYPAL_API_URL}/v1/oauth2/token", headers=headers, data=data, auth=auth)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        st.error(f"PayPal Authentication Failed: {response.json()}")
        return None

def create_paypal_order(amount):
    """Create a PayPal order"""
    access_token = authenticate_paypal()
    if not access_token:
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "amount": {"currency_code": "USD", "value": f"{amount:.2f}"},
            }
        ],
        "application_context": {
            "return_url": "https://your-streamlit-app.com/success",
            "cancel_url": "https://your-streamlit-app.com/cancel",
        },
    }

    response = requests.post(f"{PAYPAL_API_URL}/v2/checkout/orders", headers=headers, json=payload)
    
    if response.status_code == 201:
        order_data = response.json()
        return order_data["links"][1]["href"]  # Redirect URL for user payment
    else:
        st.error(f"Failed to create PayPal order: {response.json()}")
        return None

def verify_payment(order_id):
    """Verify payment status after redirection"""
    access_token = authenticate_paypal()
    if not access_token:
        return False

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(f"{PAYPAL_API_URL}/v2/checkout/orders/{order_id}", headers=headers)

    if response.status_code == 200:
        order_status = response.json().get("status")
        return order_status == "COMPLETED"
    return False

# Streamlit UI
st.title("Pharma Jobs Data Marketplace")

# Query Section
st.sidebar.header("Filter Criteria")

selected_role = st.sidebar.selectbox("Select Role", ["All"] + df["Role"].unique().tolist())
selected_experience = st.sidebar.slider("Minimum Years of Experience", min_value=0, max_value=10, value=0)

# Filter Data
filtered_df = df.copy()
if selected_role != "All":
    filtered_df = filtered_df[filtered_df["Role"] == selected_role]

filtered_df = filtered_df[filtered_df["Years of Experience"] >= selected_experience]

st.write("### Filtered Results (Preview)")
st.dataframe(filtered_df.head(5))  # Show only first 5 rows for preview

# Payment Calculation
total_rows = len(filtered_df)
if total_rows <= FREE_LIMIT:
    st.success("Your query is within the free limit. You can download it now.")
    st.download_button("Download Data", data=filtered_df.to_csv().encode(), file_name="filtered_data.csv", mime="text/csv")
else:
    num_blocks = (total_rows - FREE_LIMIT) // 25 + (1 if (total_rows - FREE_LIMIT) % 25 > 0 else 0)
    total_price = num_blocks * PRICE_PER_25_ROWS
    total_price = min(total_price, (MAX_ROWS // 25) * PRICE_PER_25_ROWS)  # Cap at $80 for 2000 rows

    st.write(f"**Rows:** {total_rows} | **Cost:** ${total_price:.2f}")
    
    if st.button("Pay with PayPal"):
        payment_url = create_paypal_order(total_price)
        if payment_url:
            st.markdown(f"[Click Here to Pay]({payment_url})")
        else:
            st.error("Payment initiation failed. Try again.")

# Payment Verification (After Redirect)
if "order_id" in st.query_params:
    order_id = st.query_params["order_id"]
    if verify_payment(order_id):
        st.success("Payment successful! You can now download the data.")
        st.download_button("Download Data", data=filtered_df.to_csv().encode(), file_name="filtered_data.csv", mime="text/csv")
    else:
        st.error("Payment verification failed. Contact support.")

