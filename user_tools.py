import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import streamlit as st
import json
import os
import shutil
from pathlib import Path
from configs import UPLOADED_FILES_DIR, CONFIGS_FOLDER_NAME


#region User Methods


def save_credentials(config):
    """Save updated credentials back to YAML file"""
    with open('credentials.yaml', 'w') as file:
        yaml.dump(config, file, default_flow_style=False)

# Get username from session state (will be set after login)
def get_username():
    """Get the current logged-in username"""
    return st.session_state.get('username', None)

# Configuration file paths - now user-specific
def get_user_config_file():
    """Get user-specific config file path"""
    username = get_username()
    if username:
        return f"configs/{username}_config.json"
    return ""#"config.json"  # Fallback

def get_user_upload_config_file():
    """Get user-specific upload config file path"""
    username = get_username()
    if username:
        return f"configs/{username}_upload_config.json"
    return ""#"upload_config.json"  # Fallback

def get_user_upload_dir():
    """Get user-specific upload directory"""
    username = get_username()
    if username:
        return f"{UPLOADED_FILES_DIR}/{username}"
    return ""#"uploaded_files"  # Fallback

def initialize_user_config(username):
    """Initialize default configuration files and sample data for a new user"""
    # Create configs directory if it doesn't exist
    Path(CONFIGS_FOLDER_NAME).mkdir(exist_ok=True)
    
    # Create user-specific config file path
    user_config_file = f"{CONFIGS_FOLDER_NAME}/{username}_config.json"
    user_upload_config_file = f"{CONFIGS_FOLDER_NAME}/{username}_upload_config.json"
    
    # Only create config if it doesn't already exist
    if not os.path.exists(user_config_file):
        # Load default configuration
        try:
            with open('default_config.json', 'r') as f:
                default_config = json.load(f)
            
            # Save as user's config
            with open(user_config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
        except FileNotFoundError:
            # If default_config.json doesn't exist, create empty config
            with open(user_config_file, 'w') as f:
                json.dump({"search_strings": []}, f, indent=2)
    
    # Create user's upload directory
    user_upload_dir = f"{UPLOADED_FILES_DIR}/{username}"
    Path(user_upload_dir).mkdir(parents=True, exist_ok=True)
    
    # Copy sample CSV file to user's upload directory
    sample_csv_name = "sample_transactions.csv"
    sample_csv_source = sample_csv_name
    sample_csv_dest = f"{user_upload_dir}/{sample_csv_name}"
    
    if not os.path.exists(sample_csv_dest) and os.path.exists(sample_csv_source):
        shutil.copy2(sample_csv_source, sample_csv_dest)
    
    # Create upload config with sample file mapping if it doesn't exist
    if not os.path.exists(user_upload_config_file):
        # Define the column mapping for the sample CSV
        sample_file_mapping = {
            sample_csv_name: ["Transaction Date", "Amount", "Description"]
        }
        
        with open(user_upload_config_file, 'w') as f:
            json.dump({"file_mappings": sample_file_mapping}, f, indent=2)

#endregion
