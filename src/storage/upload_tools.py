from storage.user_tools import get_username, get_user_uploads_folder_id
from storage.config_tools import save_upload_config
from storage.storage_utils import (
    write_text,
    list_with_prefix,
    delete,
    exists,
    get_path_for_upload,
)


def ensure_upload_dir():
    """
    Ensure upload directory prefix is available for the current user.
    Parent directories are created automatically on write.
    """
    return get_user_uploads_folder_id()

def save_uploaded_file(uploaded_file):
    """Save uploaded file to storage and return the relative path"""
    username = get_username()
    if not username:
        raise Exception("No username found in session")
    
    file_content = uploaded_file.getvalue()
    relative_key = get_path_for_upload(username, uploaded_file.name)
    
    write_text(
        relative_key,
        file_content.decode('utf-8') if isinstance(file_content, bytes) else file_content,
    )
    
    return relative_key

def load_uploaded_files():
    """Load list of uploaded files from storage"""
    uploads_prefix = get_user_uploads_folder_id()
    if not uploads_prefix:
        return []
    
    try:
        keys = list_with_prefix(uploads_prefix)
        # Extract just the filename from the full path and filter for CSV files
        csv_files = []
        for key in keys:
            filename = key.split('/')[-1]
            if filename.endswith('.csv'):
                csv_files.append(filename)
        return csv_files
    except Exception as e:
        print(f"Error loading uploaded files from storage: {e}")
        return []

def delete_uploaded_file(filename):
    """Delete a specific uploaded file from storage"""
    username = get_username()
    if not username:
        return False
    
    try:
        relative_key = get_path_for_upload(username, filename)
        if exists(relative_key):
            return delete(relative_key)
        return False
    except Exception as e:
        print(f"Error deleting file from storage: {e}")
        return False

def clear_all_uploads():
    """Delete all uploaded files from storage and clear config"""
    uploads_prefix = get_user_uploads_folder_id()
    if not uploads_prefix:
        return False
    
    try:
        keys = list_with_prefix(uploads_prefix)
        for key in keys:
            if key.endswith('.csv'):
                delete(key)
        
        save_upload_config({})
        return True
    except Exception as e:
        print(f"Error clearing uploads from storage: {e}")
        return False
