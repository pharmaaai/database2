import streamlit as st
import gspread
import pandas as pd
import paypalrestsdk
from google.oauth2.service_account import Credentials

# ==============================
# ✅ Configure PayPal API
# ==============================
def configure_paypal():
    try:
        PAYPAL_CLIENT_ID = st.secrets["paypal"]["client_id"]
        PAYPAL_CLIENT_SECRET = st.secrets["paypal"]["client_secret"]
        PAYPAL_MODE = st.secrets["paypal"]["mode"]

        paypalrestsdk.configure({
            "mode": PAYPAL_MODE,
            "client_id": PAYPAL_CLIENT_ID,
            "client_secret": PAYPAL_CLIENT_SECRET
        })
        return True
    except KeyError as e:
        st.error(f"Missing PayPal credential: {e}")
        return False

# ==============================
# ✅ Connect to Google Sheets
# ==============================
@st.cache_resource
def connect_to_sheets():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        client = gspread.authorize(creds)
        SHEET_NAME = "Database"
        return client.open(SHEET_NAME).sheet1
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        return None

# ==============================
# ✅ Fetch Data from Google Sheets
# ==============================
@st.cache_data
def fetch_data(sheet):
    if sheet:
        try:
            return pd.DataFrame(sheet.get_all_records())
        except Exception as e:
            st.error(f"Error fetching data: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# ==============================
# ✅ Calculate Pricing Based on Rows
# ==============================
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

# ==============================
# ✅ Process PayPal Payment
# ==============================
def process_payment(price, rows):
    try:
        payment = paypalrestsdk.Payment({
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
            return payment.links[1].href  # PayPal checkout link
        else:
            st.error("Payment failed.")
            return None
    except Exception as e:
        st.error(f"Error processing payment: {e}")
        return None

# ==============================
# ✅ Streamlit UI
# ==============================
def main():
    st.title("💼 Job Search & Purchase System")

    # ✅ Configure PayPal
    if not configure_paypal():
        return  # Stop execution if PayPal setup fails

    # ✅ Connect to Google Sheets
    sheet = connect_to_sheets()
    if sheet is None:
        return  # Stop execution if Google Sheets connection fails

    # ✅ Load Data
    df = fetch_data(sheet)
    
    # ✅ Sidebar Filters
    st.sidebar.header("🔍 Search Filters")
    job_title = st.sidebar.text_input("Job Title")
    company_name = st.sidebar.text_input("Company Name")
    location = st.sidebar.text_input("Location")
    years_of_experience = st.sidebar.text_input("Years of Experience")
    salary = st.sidebar.text_input("Salary Range (e.g., 50,000-70,000)")

    # ✅ Apply Filters
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

    # ✅ Display Results
    rows = len(filtered_df)
    st.write(f"### 🎯 Found *{rows}* matching jobs.")
    st.dataframe(filtered_df)

    # ✅ Pricing & Payment
    price = calculate_price(rows)
    st.write(f"💰 **Total Price: ${price}**")

    if st.button("🔗 Proceed to Payment"):
        payment_link = process_payment(price, rows)
        if payment_link:
            st.success("Click below to complete the payment:")
            st.markdown(f"[👉 Pay Now]({payment_link})", unsafe_allow_html=True)

    # ✅ CSV Download (Only Available After Payment)
    if st.button("📥 Download Data (after payment)"):
        file_path = "filtered_jobs.csv"
        filtered_df.to_csv(file_path, index=False)
        with open(file_path, "rb") as f:
            st.download_button(label="📂 Download CSV", data=f, file_name="filtered_jobs.csv", mime="text/csv")

# ==============================
# ✅ Run the App
# ==============================
if __name__ == "__main__":
    main()
