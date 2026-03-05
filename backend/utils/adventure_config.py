"""
Adventure Configuration

Stores and retrieves the last played adventure for auto-loading.
"""

import json
from pathlib import Path
from typing import Optional
from .file_helpers import read_json_file, write_json_file


CONFIG_FILE = Path(__file__).parent.parent / "data" / "adventure_config.json"


def get_last_adventure() -> Optional[str]:
    """
    Get the last played adventure ID
    
    Returns:
        Adventure ID string or None if not found
    """
    config = read_json_file(CONFIG_FILE)
    if config:
        return config.get("last_adventure_id")
    return None


def save_last_adventure(adventure_id: str) -> None:
    """
    Save the last played adventure ID
    
    Args:
        adventure_id: The adventure ID to save
    """
    # Ensure data directory exists
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    config = read_json_file(CONFIG_FILE) or {}
    config["last_adventure_id"] = adventure_id
    
    write_json_file(CONFIG_FILE, config)
    print(f"💾 Saved last adventure: {adventure_id}")


def clear_last_adventure() -> None:
    """Clear the last played adventure"""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        print("🗑️  Cleared last adventure config")

