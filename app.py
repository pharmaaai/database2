import streamlit as st
import gspread
import pandas as pd
import paypalrestsdk
from google.oauth2.service_account import Credentials

# Constants
MIN_PRICE = 5.00  # Minimum charge
PRICE_PER_ROW = 0.04  # Price per record
REQUIRED_COLUMNS = {"EMPLOYER_NAME", "JOB_TITLE", "WAGE_RATE_OF_PAY_FROM"}

# Google Sheets API Credentials
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# PayPal API Credentials (from Streamlit secrets)
PAYPAL_MODE = st.secrets["paypal"]["mode"]  # "sandbox" or "live"
PAYPAL_CLIENT_ID = st.secrets["paypal"]["client_id"]
PAYPAL_CLIENT_SECRET = st.secrets["paypal"]["client_secret"]

# Initialize PayPal SDK
paypalrestsdk.configure({
    "mode": PAYPAL_MODE,
    "client_id": PAYPAL_CLIENT_ID,
    "client_secret": PAYPAL_CLIENT_SECRET
})

# Function to connect to Google Sheets
@st.cache_resource
def connect_to_sheets():
    """Authenticate and connect to Google Sheets."""
    try:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ Failed to connect to Google Sheets: {e}")
        return None

# Function to fetch data
@st.cache_data(ttl=600)  # Cache data for 10 minutes
def fetch_data():
    """Fetch and clean data from Google Sheets."""
    client = connect_to_sheets()
    if not client:
        return None

    try:
        sheet = client.open("H1B_Job_Data").sheet1  # Ensure this matches your actual sheet name
        data = sheet.get_all_records()  # Fetch data as a list of dictionaries
        df = pd.DataFrame(data)

        # Validate required columns
        if not REQUIRED_COLUMNS.issubset(df.columns):
            st.error("❌ Data format issue: Required columns are missing.")
            return None

        # Clean data
        df["WAGE_RATE_OF_PAY_FROM"] = pd.to_numeric(df["WAGE_RATE_OF_PAY_FROM"], errors="coerce")
        df = df.dropna(subset=["WAGE_RATE_OF_PAY_FROM"])  # Drop rows with invalid salary data
        return df

    except Exception as e:
        st.error(f"❌ Failed to fetch data: {e}")
        return None

# Function to create a PayPal payment
def create_paypal_payment(amount, description):
    """Create a PayPal payment and return the approval URL."""
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "transactions": [{
            "amount": {
                "total": f"{amount:.2f}",
                "currency": "USD"
            },
            "description": description
        }],
        "redirect_urls": {
            "return_url": "https://your-streamlit-app-url.com/success",  # Replace with your app URL
            "cancel_url": "https://your-streamlit-app-url.com/cancel"   # Replace with your app URL
        }
    })

    if payment.create():
        return payment
    else:
        st.error(f"❌ PayPal payment creation failed: {payment.error}")
        return None

# Streamlit UI
st.title("🔍 H1B Job Data Search")
st.markdown("### Secure, Pay-Per-Access Employment Records")

# Load data
df = fetch_data()
if df is None or df.empty:
    st.error("❌ No data available. Please try again later.")
    st.stop()

# User Input Fields
st.subheader("🔍 Search for H1B Job Data")
employer_name = st.text_input("Enter Employer Name (or leave blank for all)", help="Partial matches supported")
job_title = st.text_input("Enter Job Title (or leave blank for all)", help="Partial matches supported")
salary_range = st.number_input("Minimum Salary ($)", min_value=0, step=1000, value=0, help="Filter by minimum wage")

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
    total_price = max(num_records * PRICE_PER_ROW, MIN_PRICE)
    st.write(f"💰 **Price: ${total_price:.2f}**")

    # Payment Button
    if st.button("Proceed to Payment", type="primary"):
        # Create PayPal payment
        payment = create_paypal_payment(total_price, f"Payment for {num_records} H1B job records")
        if payment:
            # Redirect user to PayPal approval URL
            for link in payment.links:
                if link.method == "REDIRECT":
                    redirect_url = link.href
                    st.markdown(f"🔗 [Click here to complete your payment on PayPal]({redirect_url})", unsafe_allow_html=True)
                    break
else:
    st.warning("⚠️ No matching records found. Try different search criteria.")

# Data Access After Payment (Simulated)
if st.session_state.get("payment_confirmed"):
    st.subheader("📥 Download Your Data")
    st.download_button(
        label="Download CSV",
        data=filtered_df.to_csv(index=False).encode("utf-8"),
        file_name="h1b_job_data.csv",
        mime="text/csv"
    )
