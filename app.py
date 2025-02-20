
import os
import json
import gspread
import pandas as pd
from flask import Flask, request, jsonify, send_file
from google.oauth2.service_account import Credentials
from paypalrestsdk import Payment

app = Flask(_name_)

# Google Sheets Setup
SERVICE_ACCOUNT_FILE = "database-451514-f4ce49094858.json"  # Ensure this file is in the repo
SPREADSHEET_NAME = "Database"  # Update this with your sheet name

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"])
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).sheet1

def get_data():
    """Fetch all data from Google Sheets."""
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

# PayPal Setup
PAYPAL_CLIENT_ID = "AYOIVcJrZDiCFTnyZXBNTmD1NuAzYCwx9drBc_pN1XKMuYA_R0qecAPtsrHlstml32f4kXVv6bAqOVKo"
PAYPAL_CLIENT_SECRET = "EKQUW_Q4VnjcR4wgM5LcXhYRF7UKY2ZmgLJ13yvmL5bwFLwev-RqMbhId6LZJjZ1EF7FJm0FFm6o-2dL"
Payment.configure({
    "mode": "sandbox",  # Change to 'live' for production
    "client_id": PAYPAL_CLIENT_ID,
    "client_secret": PAYPAL_CLIENT_SECRET,
})

@app.route("/query", methods=["GET"])
def query_data():
    """Handles user queries and calculates price."""
    query = request.args.get("query", "")
    df = get_data()
    
    filtered_df = df[df.apply(lambda row: row.astype(str).str.contains(query, case=False).any(), axis=1)]
    rows = len(filtered_df)
    price = calculate_price(rows)
    
    return jsonify({"rows": rows, "price": price})

@app.route("/pay", methods=["POST"])
def process_payment():
    """Initiates a PayPal payment."""
    data = request.json
    rows = data.get("rows")
    price = calculate_price(rows)

    payment = Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "transactions": [{
            "amount": {"total": str(price), "currency": "USD"},
            "description": f"Payment for {rows} rows of data."
        }],
        "redirect_urls": {
            "return_url": "http://localhost:5000/success",
            "cancel_url": "http://localhost:5000/cancel"
        }
    })

    if payment.create():
        return jsonify({"approval_url": payment.links[1].href})  # Redirect user to PayPal
    else:
        return jsonify({"error": "Payment failed."}), 500

@app.route("/download", methods=["GET"])
def download_data():
    """Generates and serves a CSV file after payment."""
    query = request.args.get("query", "")
    df = get_data()
    
    filtered_df = df[df.apply(lambda row: row.astype(str).str.contains(query, case=False).any(), axis=1)]
    file_path = "filtered_data.csv"
    filtered_df.to_csv(file_path, index=False)
    
    return send_file(file_path, as_attachment=True)

if _name_ == "_main_":
    app.run(debug=True)
