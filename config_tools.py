from user_tools import get_user_config_file, get_user_upload_config_file, get_user_config_folder_id
from storage_utils import load_json, save_json


def load_config():
    """Load configuration from storage and return as Python list"""
    config_filename = get_user_config_file()
    config_folder_prefix = get_user_config_folder_id()
    
    if not config_filename or not config_folder_prefix:
        return []
    
    try:
        relative_key = f"{config_folder_prefix}{config_filename}"
        config = load_json(relative_key)
        if config:
            return config.get('search_strings', [])
        return []
    except Exception as e:
        print(f"Error loading config from storage: {e}")
        return []
            

def save_config(search_strings):
    """Save Python list to storage"""
    config_filename = get_user_config_file()
    config_folder_prefix = get_user_config_folder_id()
    
    if not config_filename or not config_folder_prefix:
        return False
    
    config = {"search_strings": search_strings}
    try:
        relative_key = f"{config_folder_prefix}{config_filename}"
        save_json(config, relative_key)
        return True
    except Exception as e:
        print(f"Error saving config to storage: {e}")
        return False

def load_upload_config():
    """Load upload configuration (file mappings) from storage"""
    upload_config_filename = get_user_upload_config_file()
    config_folder_prefix = get_user_config_folder_id()
    
    if not upload_config_filename or not config_folder_prefix:
        return {}
    
    try:
        relative_key = f"{config_folder_prefix}{upload_config_filename}"
        config = load_json(relative_key)
        if config:
            return config.get('file_mappings', {})
        return {}
    except Exception as e:
        print(f"Error loading upload config from storage: {e}")
        return {}

def save_upload_config(file_mappings):
    """Save file mappings to storage"""
    upload_config_filename = get_user_upload_config_file()
    config_folder_prefix = get_user_config_folder_id()
    
    if not upload_config_filename or not config_folder_prefix:
        return False
    
    config = {"file_mappings": file_mappings}
    try:
        relative_key = f"{config_folder_prefix}{upload_config_filename}"
        save_json(config, relative_key)
        return True
    except Exception as e:
        print(f"Error saving upload config to storage: {e}")
        return False
