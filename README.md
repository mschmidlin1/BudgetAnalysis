# 💰 Budget Analysis App

A Streamlit web application for analyzing credit card transactions and visualizing spending patterns.

## Deployment
This app is currently deployed on streamlit cloud:
- https://budgetanalysis-creditcardtransactions.streamlit.app/

## Features

- User authentication with secure login
- CSV transaction import with flexible column mapping
- Nested category configuration for expense tracking
- Interactive sunburst visualizations
- Cloud-based data storage using Google Sheets and Google Cloud Storage

## Data Storage

User data is stored in the cloud:
- **Google Sheets**: Stores user configurations and transaction data
- **Google Cloud Storage**: Stores uploaded CSV files and generated reports

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.streamlit/secrets.toml` file with your Google Cloud credentials:
   ```toml
   [gcp_service_account]
   type = "service_account"
   project_id = "your-project-id"
   private_key_id = "your-private-key-id"
   private_key = "your-private-key"
   client_email = "your-service-account-email"
   client_id = "your-client-id"
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "your-cert-url"
   ```

3. Run the application:
   ```bash
   streamlit run main.py
   ```

## Usage

1. Register and login
2. Upload CSV transaction files in the Data Import tab
3. Configure spending categories using JSON format
4. View interactive visualizations and reports

## Requirements

- Python 3.9.11
- Google Cloud account with Sheets API and Cloud Storage enabled
