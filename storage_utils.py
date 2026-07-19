"""
Filesystem storage utilities for user configs and uploads.

Storage root is BUDGET_STORAGE_ROOT (default: /data). Relative keys use the
same layout as the former GCS bucket: {username}/configs/..., {username}/uploads/...
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import List, Optional


DEFAULT_STORAGE_ROOT = "/data"


def get_storage_root() -> Path:
    """Return the configured storage root directory."""
    return Path(os.environ.get("BUDGET_STORAGE_ROOT", DEFAULT_STORAGE_ROOT))


def _resolve_path(relative_key: str) -> Path:
    """
    Resolve a relative storage key under the storage root.
    Rejects empty keys and path traversal via '..'.
    """
    if not relative_key or not relative_key.strip():
        raise ValueError("Storage key must be a non-empty relative path")

    normalized = relative_key.replace("\\", "/").lstrip("/")
    parts = Path(normalized).parts
    if any(part == ".." for part in parts):
        raise ValueError(f"Path traversal is not allowed: {relative_key!r}")

    root = get_storage_root().resolve()
    full = (root / normalized).resolve()
    try:
        full.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes storage root: {relative_key!r}") from exc
    return full


def get_user_prefix(username: str) -> str:
    """Return the relative prefix for a user's data (e.g. 'username/')."""
    return f"{username}/"


def get_config_prefix(username: str) -> str:
    """Return the relative prefix for a user's config files."""
    return f"{username}/configs/"


def get_uploads_prefix(username: str) -> str:
    """Return the relative prefix for a user's uploaded files."""
    return f"{username}/uploads/"


def get_path_for_config(username: str, config_type: str = "config") -> str:
    """
    Relative path for a user's config file.
    config_type can be 'config' or 'upload_config'.
    """
    prefix = get_config_prefix(username)
    return f"{prefix}{username}_{config_type}.json"


def get_path_for_upload(username: str, filename: str) -> str:
    """Relative path for a user's uploaded file."""
    prefix = get_uploads_prefix(username)
    return f"{prefix}{filename}"


def write_bytes(relative_key: str, content: bytes) -> str:
    """Write bytes to storage. Creates parent directories as needed."""
    path = _resolve_path(relative_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return relative_key


def write_text(relative_key: str, content: str, encoding: str = "utf-8") -> str:
    """Write text to storage. Creates parent directories as needed."""
    return write_bytes(relative_key, content.encode(encoding))


def copy_file(local_path: str, relative_key: str) -> str:
    """Copy a local file into storage. Creates parent directories as needed."""
    path = _resolve_path(relative_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(local_path, path)
    return relative_key


def read_bytes(relative_key: str) -> Optional[bytes]:
    """Read file contents as bytes, or None if the file does not exist."""
    path = _resolve_path(relative_key)
    if not path.is_file():
        return None
    return path.read_bytes()


def read_text(relative_key: str, encoding: str = "utf-8") -> Optional[str]:
    """Read file contents as text, or None if the file does not exist."""
    content = read_bytes(relative_key)
    if content is None:
        return None
    return content.decode(encoding)


def exists(relative_key: str) -> bool:
    """Return True if the relative key exists as a file."""
    return _resolve_path(relative_key).is_file()


def delete(relative_key: str) -> bool:
    """Delete a file. Returns True if it existed and was removed."""
    path = _resolve_path(relative_key)
    if not path.is_file():
        return False
    path.unlink()
    return True


def list_with_prefix(prefix: str) -> List[str]:
    """
    List files under a relative prefix.
    Returns relative keys (posix-style) under the storage root.
    """
    root = get_storage_root().resolve()
    normalized = prefix.replace("\\", "/").lstrip("/")
    if any(part == ".." for part in Path(normalized).parts):
        raise ValueError(f"Path traversal is not allowed: {prefix!r}")

    base = (root / normalized).resolve() if normalized else root
    try:
        base.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes storage root: {prefix!r}") from exc

    if not base.exists():
        return []

    results: List[str] = []
    if base.is_file():
        results.append(base.relative_to(root).as_posix())
        return results

    for path in sorted(base.rglob("*")):
        if path.is_file():
            results.append(path.relative_to(root).as_posix())
    return results


def save_json(data: dict, relative_key: str) -> str:
    """Save a dictionary as JSON. Returns the relative key."""
    return write_text(relative_key, json.dumps(data, indent=2))


def load_json(relative_key: str) -> Optional[dict]:
    """Load JSON from storage. Returns None if missing or invalid."""
    content = read_text(relative_key)
    if content is None:
        return None
    return json.loads(content)
