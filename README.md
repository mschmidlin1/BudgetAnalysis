# 💰 Budget Analysis App

A Streamlit web application for analyzing credit card transactions and visualizing spending patterns.

## Deployment
Homelab production: `https://budget-analysis.schmidlin.casa` (see [docs/deployment.md](docs/deployment.md)).

Legacy Streamlit Cloud (until retired):
- https://budgetanalysis-creditcardtransactions.streamlit.app/

## Features

- User authentication with secure login
- Bank connection through Plaid (one institution at a time)
- CSV transaction import with flexible column mapping
- Nested category configuration for expense tracking
- Interactive sunburst visualizations
- Google Sheets for users; filesystem (NFS in production) for configs and uploads

## Data Storage

- **Google Sheets**: User accounts / authentication
- **Filesystem** (`/data` in the container, NFS-backed in k3s): uploaded/generated CSVs, per-user configs, and encrypted Plaid access tokens

## Installation

1. Install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Create a `.streamlit/secrets.toml` from `.streamlit/secrets.toml.example` (Sheets, cookie, and Plaid).

3. For local filesystem storage, create a data directory and point the app at it:
   ```bash
   mkdir -p data
   export BUDGET_STORAGE_ROOT="$(pwd)/data"
   streamlit run main.py
   ```

   Or use Docker Compose (mounts `./data` at `/data`):
   ```bash
   docker compose up --build
   ```

## Usage

1. Register and login
2. Connect a bank through Plaid or upload CSV transaction files
3. Configure spending categories using JSON format
4. View interactive visualizations and reports

## Requirements

- Python 3.9+
- Google Cloud service account with Sheets API access (users only)
- Writable storage root (`/data` in production; `./data` locally)
