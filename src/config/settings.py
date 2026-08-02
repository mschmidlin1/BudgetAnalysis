import streamlit as st

# Legacy credentials file (for migration purposes only)
CREDENTIALS_FILE = "credentials.yaml"
CONFIGS_FOLDER_NAME = "configs"
UPLOADED_FILES_DIR = "uploaded_files"

# Google Sheets configuration
USERS_WORKSHEET = "users"  # Name of the worksheet containing user data

def get_cookie_config():
    """Get cookie configuration from Streamlit secrets"""
    return {
        'name': st.secrets.get("cookie", {}).get("name", "budget_analysis_cookie"),
        'key': st.secrets.get("cookie", {}).get("key", "budget_analysis_secret_key_change_this_in_production"),
        'expiry_days': st.secrets.get("cookie", {}).get("expiry_days", 30)
    }