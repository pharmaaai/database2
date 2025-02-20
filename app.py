
import paypalrestsdk
import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from paypalrestsdk import Payment

# PayPal API Credentials (Replace with actual credentials)
PAYPAL_CLIENT_ID = "AYOIVcJrZDiCFTnyZXBNTmD1NuAzYCwx9drBc_pN1XKMuYA_R0qecAPtsrHlstml32f4kXVv6bAqOVKo"
PAYPAL_CLIENT_SECRET = "EKQUW_Q4VnjcR4wgM5LcXhYRF7UKY2ZmgLJ13yvmL5bwFLwev-RqMbhId6LZJjZ1EF7FJm0FFm6o-2dL"

# Configure PayPal SDK
Payment.configure({
    "mode": "sandbox",  # Change to 'live' for production
    "client_id": PAYPAL_CLIENT_ID,
    "client_secret": PAYPAL_CLIENT_SECRET,
})

# Google Sheets Setup
SERVICE_ACCOUNT_FILE = "database-451514-f4ce49094858.json"  # Update with your actual file
SPREADSHEET_NAME = "Database"  # Update with your sheet name

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"])
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).sheet1

# Function to fetch data
@st.cache_data
def get_data():
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# Pricing Logic
def calculate_price(rows):
    if rows <= 25:
        return 1
    elif rows <= 50:
        return 2
    elif rows <= 100:
        return 4
    elif rows <= 200:
        return 8
    elif rows <= 300:
        return 12
    elif rows <= 400:
        return 16
    else:
        return 20 + ((rows - 500) // 100) * 4

# Load Data
df = get_data()

# Streamlit UI
st.title("Job Search & Purchase System")

st.sidebar.header("Search Filters")
job_title = st.sidebar.text_input("Job Title")
company_name = st.sidebar.text_input("Company Name")
location = st.sidebar.text_input("Location")
years_of_experience = st.sidebar.text_input("Years of Experience")
salary = st.sidebar.text_input("Salary Range (e.g., 50,000-70,000)")

# Filter Data
filtered_df = df
if job_title:
    filtered_df = filtered_df[filtered_df["Job Title"].str.contains(job_title, case=False, na=False)]
if company_name:
    filtered_df = filtered_df[filtered_df["Company Name"].str.contains(company_name, case=False, na=False)]
if location:
    filtered_df = filtered_df[filtered_df["Location"].str.contains(location, case=False, na=False)]
if years_of_experience:
    filtered_df = filtered_df[filtered_df["Years of Experience"].astype(str).str.contains(years_of_experience, na=False)]
if salary:
    filtered_df = filtered_df[filtered_df["Salary"].astype(str).str.contains(salary, na=False)]

# Display Results
rows = len(filtered_df)
st.write(f"### Found *{rows}* matching jobs.")

st.dataframe(filtered_df)

# Pricing & Payment
price = calculate_price(rows)
st.write(f"*Total Price: ${price}*")

if st.button("Proceed to Payment"):
    payment = Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "transactions": [{
            "amount": {"total": str(price), "currency": "USD"},
            "description": f"Payment for {rows} job listings."
        }],
        "redirect_urls": {
            "return_url": "http://localhost:8501",
            "cancel_url": "http://localhost:8501"
        }
    })

    if payment.create():
        st.success("Click below to complete the payment:")
        st.markdown(f"[Pay Now]({payment.links[1].href})", unsafe_allow_html=True)
    else:
        st.error("Payment failed.")

# CSV Download Option After Payment
if st.button("Download Data (after payment)"):
    file_path = "filtered_jobs.csv"
    filtered_df.to_csv(file_path, index=False)
    with open(file_path, "rb") as f:
        st.download_button(label="Download CSV", data=f, file_name="filtered_jobs.csv", mime="text/csv")
