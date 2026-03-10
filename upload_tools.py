from user_tools import get_user_config_file, get_user_upload_config_file, get_user_upload_dir, get_username, get_user_uploads_folder_id
from pathlib import Path
from config_tools import save_upload_config
from gcs_utils import (
    upload_content_to_gcs,
    list_blobs_with_prefix,
    delete_blob,
    blob_exists,
    get_blob_name_for_upload
)




def ensure_upload_dir():
    """
    Ensure upload directory exists in GCS.
    This is now handled automatically by get_user_uploads_folder_id()
    """
    # GCS folders (prefixes) are created automatically when needed
    return get_user_uploads_folder_id()

def save_uploaded_file(uploaded_file):
    """Save uploaded file to GCS and return the blob name"""
    username = get_username()
    if not username:
        raise Exception("No username found in session")
    
    # Upload file content to GCS
    file_content = uploaded_file.getvalue()
    blob_name = get_blob_name_for_upload(username, uploaded_file.name)
    
    upload_content_to_gcs(
        file_content.decode('utf-8') if isinstance(file_content, bytes) else file_content,
        blob_name,
        content_type='text/csv'
    )
    
    return blob_name

def load_uploaded_files():
    """Load list of uploaded files from GCS"""
    uploads_prefix = get_user_uploads_folder_id()
    if not uploads_prefix:
        return []
    
    try:
        blob_names = list_blobs_with_prefix(uploads_prefix)
        # Extract just the filename from the full blob path and filter for CSV files
        csv_files = []
        for blob_name in blob_names:
            filename = blob_name.split('/')[-1]  # Get last part of path
            if filename.endswith('.csv'):
                csv_files.append(filename)
        return csv_files
    except Exception as e:
        print(f"Error loading uploaded files from GCS: {e}")
        return []

def delete_uploaded_file(filename):
    """Delete a specific uploaded file from GCS"""
    username = get_username()
    if not username:
        return False
    
    try:
        blob_name = get_blob_name_for_upload(username, filename)
        if blob_exists(blob_name):
            return delete_blob(blob_name)
        return False
    except Exception as e:
        print(f"Error deleting file from GCS: {e}")
        return False

def clear_all_uploads():
    """Delete all uploaded files from GCS and clear config"""
    uploads_prefix = get_user_uploads_folder_id()
    if not uploads_prefix:
        return False
    
    try:
        blob_names = list_blobs_with_prefix(uploads_prefix)
        # Delete all CSV files
        for blob_name in blob_names:
            if blob_name.endswith('.csv'):
                delete_blob(blob_name)
        
        # Clear upload config
        save_upload_config({})
        return True
    except Exception as e:
        print(f"Error clearing uploads from GCS: {e}")
        return False
