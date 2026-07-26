from user_tools import get_user_config_file, get_user_upload_config_file, get_user_config_folder_id
from storage_utils import load_json, save_json


def _config_relative_key():
    """Return the storage key for the user's main config file, or None if unavailable."""
    config_filename = get_user_config_file()
    config_folder_prefix = get_user_config_folder_id()

    if not config_filename or not config_folder_prefix:
        return None

    return f"{config_folder_prefix}{config_filename}"


def _load_full_config():
    """Load the full user config dict from storage."""
    relative_key = _config_relative_key()
    if not relative_key:
        return {}

    try:
        config = load_json(relative_key)
        return config if isinstance(config, dict) else {}
    except Exception as e:
        print(f"Error loading config from storage: {e}")
        return {}


def _save_full_config(config):
    """Save the full user config dict to storage."""
    relative_key = _config_relative_key()
    if not relative_key:
        return False

    try:
        save_json(config, relative_key)
        return True
    except Exception as e:
        print(f"Error saving config to storage: {e}")
        return False


def load_config():
    """Load configuration from storage and return as Python list"""
    config = _load_full_config()
    return config.get('search_strings', [])


def save_config(search_strings):
    """Save search_strings list to storage, preserving other config keys."""
    config = _load_full_config()
    config['search_strings'] = search_strings
    if 'ignore_strings' not in config:
        config['ignore_strings'] = []
    return _save_full_config(config)


def load_ignore_strings():
    """Load ignore_strings list from storage (empty list if missing)."""
    config = _load_full_config()
    ignore_strings = config.get('ignore_strings', [])
    if not isinstance(ignore_strings, list):
        return []
    return [s for s in ignore_strings if isinstance(s, str)]


def save_ignore_strings(ignore_strings):
    """Save ignore_strings list to storage, preserving other config keys."""
    if not isinstance(ignore_strings, list):
        return False
    cleaned = [s.strip() for s in ignore_strings if isinstance(s, str) and s.strip()]
    config = _load_full_config()
    if 'search_strings' not in config:
        config['search_strings'] = []
    config['ignore_strings'] = cleaned
    return _save_full_config(config)


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
