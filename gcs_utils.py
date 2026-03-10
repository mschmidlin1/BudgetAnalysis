"""
Google Cloud Storage utility functions for storing and retrieving user data.
This module handles all interactions with Google Cloud Storage API.
"""

import streamlit as st
import io
import json
from google.cloud import storage
from google.oauth2 import service_account
from typing import Optional, Dict, List


def get_storage_client():
    """Create and return Google Cloud Storage client using credentials from secrets"""
    try:
        # Get credentials from Streamlit secrets
        credentials_dict = {
            "type": st.secrets["gcp_service_account"]["type"],
            "project_id": st.secrets["gcp_service_account"]["project_id"],
            "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
            "private_key": st.secrets["gcp_service_account"]["private_key"],
            "client_email": st.secrets["gcp_service_account"]["client_email"],
            "client_id": st.secrets["gcp_service_account"]["client_id"],
            "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
            "token_uri": st.secrets["gcp_service_account"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"],
            "universe_domain": st.secrets["gcp_service_account"]["universe_domain"]
        }
        
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict
        )
        
        client = storage.Client(credentials=credentials, project=credentials_dict["project_id"])
        return client
    except Exception as e:
        st.error(f"Error creating Google Cloud Storage client: {e}")
        raise


def get_bucket_name():
    """Get the bucket name from secrets"""
    return st.secrets["gcs"]["bucket_name"]


def get_bucket():
    """Get the GCS bucket object"""
    client = get_storage_client()
    bucket_name = get_bucket_name()
    return client.bucket(bucket_name)


def get_user_prefix(username: str) -> str:
    """
    Get the prefix (path) for a user's data in GCS.
    Returns the prefix string (e.g., 'username/')
    """
    return f"{username}/"


def get_config_prefix(username: str) -> str:
    """
    Get the prefix for a user's config files in GCS.
    Returns the prefix string (e.g., 'username/configs/')
    """
    return f"{username}/configs/"


def get_uploads_prefix(username: str) -> str:
    """
    Get the prefix for a user's uploaded files in GCS.
    Returns the prefix string (e.g., 'username/uploads/')
    """
    return f"{username}/uploads/"


def upload_file_to_gcs(file_path: str, blob_name: str) -> str:
    """
    Upload a file to Google Cloud Storage.
    Returns the blob name.
    """
    bucket = get_bucket()
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(file_path)
    return blob_name


def upload_content_to_gcs(content: str, blob_name: str, content_type: str = 'text/plain') -> str:
    """
    Upload content (string) directly to GCS without creating a local file.
    Returns the blob name.
    """
    bucket = get_bucket()
    blob = bucket.blob(blob_name)
    blob.upload_from_string(content, content_type=content_type)
    return blob_name


def download_blob_as_bytes(blob_name: str) -> Optional[bytes]:
    """
    Download a blob from GCS.
    Returns the blob content as bytes, or None if blob doesn't exist.
    """
    try:
        bucket = get_bucket()
        blob = bucket.blob(blob_name)
        
        if not blob.exists():
            return None
        
        return blob.download_as_bytes()
    except Exception as e:
        st.error(f"Error downloading blob from GCS: {e}")
        return None


def download_blob_as_string(blob_name: str) -> Optional[str]:
    """
    Download a blob from GCS as a string.
    Returns the blob content as string, or None if blob doesn't exist.
    """
    content_bytes = download_blob_as_bytes(blob_name)
    if content_bytes:
        return content_bytes.decode('utf-8')
    return None


def blob_exists(blob_name: str) -> bool:
    """
    Check if a blob exists in GCS.
    Returns True if exists, False otherwise.
    """
    try:
        bucket = get_bucket()
        blob = bucket.blob(blob_name)
        return blob.exists()
    except Exception as e:
        st.error(f"Error checking blob existence: {e}")
        return False


def list_blobs_with_prefix(prefix: str) -> List[str]:
    """
    List all blobs with a given prefix.
    Returns a list of blob names.
    """
    try:
        bucket = get_bucket()
        blobs = bucket.list_blobs(prefix=prefix)
        return [blob.name for blob in blobs]
    except Exception as e:
        st.error(f"Error listing blobs: {e}")
        return []


def delete_blob(blob_name: str) -> bool:
    """
    Delete a blob from GCS.
    Returns True if successful.
    """
    try:
        bucket = get_bucket()
        blob = bucket.blob(blob_name)
        blob.delete()
        return True
    except Exception as e:
        st.error(f"Error deleting blob: {e}")
        return False


def save_json_to_gcs(data: dict, blob_name: str) -> str:
    """
    Save a Python dictionary as JSON to GCS.
    Returns the blob name.
    """
    json_content = json.dumps(data, indent=2)
    return upload_content_to_gcs(json_content, blob_name, content_type='application/json')


def load_json_from_gcs(blob_name: str) -> Optional[dict]:
    """
    Load a JSON file from GCS and return as Python dictionary.
    Returns None if blob doesn't exist.
    """
    try:
        content_str = download_blob_as_string(blob_name)
        if content_str:
            return json.loads(content_str)
        return None
    except Exception as e:
        st.error(f"Error loading JSON from GCS: {e}")
        return None


def copy_local_file_to_gcs(local_path: str, blob_name: str) -> str:
    """
    Copy a local file to GCS.
    Returns the blob name.
    """
    return upload_file_to_gcs(local_path, blob_name)


def get_blob_name_for_config(username: str, config_type: str = "config") -> str:
    """
    Get the blob name for a user's config file.
    config_type can be 'config' or 'upload_config'
    """
    prefix = get_config_prefix(username)
    return f"{prefix}{username}_{config_type}.json"


def get_blob_name_for_upload(username: str, filename: str) -> str:
    """
    Get the blob name for a user's uploaded file.
    """
    prefix = get_uploads_prefix(username)
    return f"{prefix}{filename}"
