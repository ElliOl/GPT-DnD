"""
File I/O Helper Functions
"""

from pathlib import Path
from typing import Optional


def ensure_directory(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json_file(file_path: Path) -> Optional[dict]:
    """Safely read a JSON file, returning None if it doesn't exist or is invalid"""
    import json
    
    if not file_path.exists():
        return None
    
    try:
        with open(file_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def write_json_file(file_path: Path, data: dict, indent: int = 2) -> bool:
    """Safely write a JSON file, creating parent directories if needed"""
    import json
    
    try:
        ensure_directory(file_path.parent)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=indent)
        return True
    except (IOError, TypeError):
        return False

