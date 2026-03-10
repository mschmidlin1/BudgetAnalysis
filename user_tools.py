import streamlit as st
import pandas as pd
import json
import os
import shutil
from pathlib import Path
from configs import UPLOADED_FILES_DIR, CONFIGS_FOLDER_NAME, USERS_WORKSHEET
from streamlit_gsheets import GSheetsConnection
from gcs_utils import (
    get_user_prefix,
    get_config_prefix,
    get_uploads_prefix,
    save_json_to_gcs,
    load_json_from_gcs,
    list_blobs_with_prefix,
    copy_local_file_to_gcs,
    get_blob_name_for_config,
    get_blob_name_for_upload
)


#region Google Sheets Connection

def get_gsheets_connection():
    """Get or create Google Sheets connection"""
    return st.connection("gsheets", type=GSheetsConnection)

def load_users_dataframe():
    """Load users data from Google Sheets into a pandas DataFrame"""
    try:
        conn = get_gsheets_connection()
        df = conn.read(worksheet=USERS_WORKSHEET, ttl=0)
        
        # If the sheet is empty or doesn't exist, create default structure
        if df is None or df.empty:
            df = pd.DataFrame(columns=[
                'username', 'email', 'first_name', 'last_name', 
                'password', 'password_hint', 'logged_in', 
                'failed_login_attempts', 'roles'
            ])
        
        return df
    except Exception as e:
        st.error(f"Error loading users from Google Sheets: {e}")
        # Return empty dataframe with expected structure
        return pd.DataFrame(columns=[
            'username', 'email', 'first_name', 'last_name', 
            'password', 'password_hint', 'logged_in', 
            'failed_login_attempts', 'roles'
        ])

def save_users_dataframe(df):
    """Save users DataFrame back to Google Sheets"""
    try:
        conn = get_gsheets_connection()
        conn.update(worksheet=USERS_WORKSHEET, data=df)
        return True
    except Exception as e:
        st.error(f"Error saving users to Google Sheets: {e}")
        return False

def dataframe_to_config(df):
    """Convert users DataFrame to config dictionary format for streamlit-authenticator"""
    config = {
        'credentials': {
            'usernames': {}
        }
    }
    
    for _, row in df.iterrows():
        # Ensure username is always a string
        username = str(row['username']) if pd.notna(row['username']) else ''
        
        # Skip rows with empty usernames
        if not username:
            continue
            
        user_data = {
            'email': str(row.get('email', '')) if pd.notna(row.get('email')) else '',
            'password': str(row.get('password', '')) if pd.notna(row.get('password')) else '',
            'logged_in': bool(row.get('logged_in', False)),
        }
        
        # Add optional fields if they exist
        if pd.notna(row.get('first_name')):
            user_data['first_name'] = str(row['first_name'])
        if pd.notna(row.get('last_name')):
            user_data['last_name'] = str(row['last_name'])
        if pd.notna(row.get('name')):
            user_data['name'] = str(row['name'])
        if pd.notna(row.get('password_hint')):
            user_data['password_hint'] = str(row['password_hint'])
        if pd.notna(row.get('failed_login_attempts')):
            user_data['failed_login_attempts'] = int(row['failed_login_attempts'])
        if pd.notna(row.get('roles')):
            user_data['roles'] = str(row['roles'])
        
        config['credentials']['usernames'][username] = user_data
    
    return config

def update_user_in_dataframe(df, username, updates):
    """Update a specific user's data in the DataFrame"""
    # Ensure username is a string for comparison
    username = str(username)
    if username in df['username'].values:
        idx = df[df['username'] == username].index[0]
        for key, value in updates.items():
            if key in df.columns:
                # Ensure string fields are stored as strings
                if key in ['username', 'email', 'first_name', 'last_name', 'password', 'password_hint', 'roles']:
                    value = str(value) if value is not None else ''
                df.at[idx, key] = value
    return df

def add_user_to_dataframe(df, username, user_data):
    """Add a new user to the DataFrame"""
    new_row = {
        'username': str(username),  # Ensure username is always a string
        'email': str(user_data.get('email', '')),
        'first_name': str(user_data.get('first_name', '')),
        'last_name': str(user_data.get('last_name', '')),
        'password': str(user_data.get('password', '')),
        'password_hint': str(user_data.get('password_hint', '')),
        'logged_in': user_data.get('logged_in', False),
        'failed_login_attempts': user_data.get('failed_login_attempts', 0),
        'roles': str(user_data.get('roles', '')) if user_data.get('roles') else None
    }
    
    # Use pd.concat instead of append (deprecated)
    new_df = pd.DataFrame([new_row])
    df = pd.concat([df, new_df], ignore_index=True)
    return df

#endregion


#region User Methods

def save_credentials(config):
    """Save updated credentials to Google Sheets"""
    df = load_users_dataframe()
    
    # Update DataFrame with config data
    for username, user_data in config['credentials']['usernames'].items():
        if username in df['username'].values:
            # Update existing user
            df = update_user_in_dataframe(df, username, user_data)
        else:
            # Add new user
            df = add_user_to_dataframe(df, username, user_data)
    
    # Save back to Google Sheets
    save_users_dataframe(df)

def get_username():
    """Get the current logged-in username"""
    return st.session_state.get('username', None)

def get_user_folder_id():
    """Get the GCS prefix for the current user"""
    username = get_username()
    if username:
        return get_user_prefix(username)
    return None

def get_user_config_folder_id():
    """Get the GCS prefix for user configs"""
    username = get_username()
    if username:
        return get_config_prefix(username)
    return None

def get_user_uploads_folder_id():
    """Get the GCS prefix for user uploads"""
    username = get_username()
    if username:
        return get_uploads_prefix(username)
    return None

def get_user_config_file():
    """
    Get user-specific config file path (legacy function for compatibility).
    Now returns a tuple of (filename, folder_id) for Google Drive.
    """
    username = get_username()
    if username:
        return f"{username}_config.json"
    return ""

def get_user_upload_config_file():
    """
    Get user-specific upload config file path (legacy function for compatibility).
    Now returns a tuple of (filename, folder_id) for Google Drive.
    """
    username = get_username()
    if username:
        return f"{username}_upload_config.json"
    return ""

def get_user_upload_dir():
    """
    Get user-specific upload directory (legacy function for compatibility).
    Now returns the Google Drive folder ID.
    """
    return get_user_uploads_folder_id()

def initialize_user_config(username):
    """Initialize default configuration files and sample data for a new user in GCS"""
    try:
        # Get blob names for user's config files
        config_blob_name = get_blob_name_for_config(username, "config")
        upload_config_blob_name = get_blob_name_for_config(username, "upload_config")
        
        # Check if config already exists
        existing_config = load_json_from_gcs(config_blob_name)
        
        if not existing_config:
            # Load default configuration
            try:
                with open('default_config.json', 'r') as f:
                    default_config = json.load(f)
            except FileNotFoundError:
                # If default_config.json doesn't exist, create empty config
                default_config = {"search_strings": []}
            
            # Save as user's config in GCS
            save_json_to_gcs(default_config, config_blob_name)
        
        # Check if upload config already exists
        existing_upload_config = load_json_from_gcs(upload_config_blob_name)
        
        if not existing_upload_config:
            # Copy sample CSV file to user's upload directory in GCS
            sample_csv_name = "sample_transactions.csv"
            sample_csv_source = sample_csv_name
            
            if os.path.exists(sample_csv_source):
                sample_blob_name = get_blob_name_for_upload(username, sample_csv_name)
                copy_local_file_to_gcs(sample_csv_source, sample_blob_name)
                
                # Create upload config with sample file mapping
                sample_file_mapping = {
                    sample_csv_name: ["Transaction Date", "Amount", "Description"]
                }
                
                upload_config = {"file_mappings": sample_file_mapping}
                save_json_to_gcs(upload_config, upload_config_blob_name)
            else:
                # Create empty upload config
                upload_config = {"file_mappings": {}}
                save_json_to_gcs(upload_config, upload_config_blob_name)
                
    except Exception as e:
        st.error(f"Error initializing user config in GCS: {e}")
        raise

#endregion
