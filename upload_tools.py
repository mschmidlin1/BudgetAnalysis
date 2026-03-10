from user_tools import get_user_config_file, get_user_upload_config_file, get_user_upload_dir, get_username
from pathlib import Path
from config_tools import save_upload_config




def ensure_upload_dir():
    """Create upload directory if it doesn't exist"""
    upload_dir = get_user_upload_dir()
    Path(upload_dir).mkdir(parents=True, exist_ok=True)

def save_uploaded_file(uploaded_file):
    """Save uploaded file to local directory and return the path"""
    ensure_upload_dir()
    upload_dir = get_user_upload_dir()
    file_path = Path(upload_dir) / uploaded_file.name
    with open(file_path, 'wb') as f:
        f.write(uploaded_file.getbuffer())
    return str(file_path)

def load_uploaded_files():
    """Load list of uploaded files from the upload directory"""
    ensure_upload_dir()
    upload_dir = get_user_upload_dir()
    upload_path = Path(upload_dir)
    if upload_path.exists():
        return [f.name for f in upload_path.glob('*.csv')]
    return []

def delete_uploaded_file(filename):
    """Delete a specific uploaded file"""
    upload_dir = get_user_upload_dir()
    file_path = Path(upload_dir) / filename
    if file_path.exists():
        file_path.unlink()
        return True
    return False

def clear_all_uploads():
    """Delete all uploaded files and clear config"""
    upload_dir = get_user_upload_dir()
    upload_path = Path(upload_dir)
    if upload_path.exists():
        for file in upload_path.glob('*.csv'):
            file.unlink()
    save_upload_config({})
    return True
