from user_tools import get_user_config_file, get_user_upload_config_file
import json




def load_config():
    """Load configuration from JSON file and return as Python list"""
    config_file = get_user_config_file()
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            return config['search_strings']
    except FileNotFoundError:
        return []
            

def save_config(search_strings):
    """Save Python list to JSON file"""
    config_file = get_user_config_file()
    config = {"search_strings": search_strings}
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    return True

def load_upload_config():
    """Load upload configuration (file mappings) from JSON file"""
    upload_config_file = get_user_upload_config_file()
    try:
        with open(upload_config_file, 'r') as f:
            config = json.load(f)
            return config.get('file_mappings', {})
    except FileNotFoundError:
        return {}

def save_upload_config(file_mappings):
    """Save file mappings to JSON file"""
    upload_config_file = get_user_upload_config_file()
    config = {"file_mappings": file_mappings}
    with open(upload_config_file, 'w') as f:
        json.dump(config, f, indent=2)
    return True