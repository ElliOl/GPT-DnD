"""
Input Validation Helpers
"""

from typing import Any, Dict, List, Optional


def validate_adventure_id(adventure_id: str) -> bool:
    """Validate adventure ID format"""
    if not adventure_id or not isinstance(adventure_id, str):
        return False
    
    # Basic validation: alphanumeric, underscores, hyphens only
    import re
    return bool(re.match(r'^[a-z0-9_-]+$', adventure_id.lower()))


def validate_location_id(location_id: str) -> bool:
    """Validate location ID format"""
    return validate_adventure_id(location_id)  # Same format


def validate_npc_id(npc_id: str) -> bool:
    """Validate NPC ID format"""
    return validate_adventure_id(npc_id)  # Same format


def validate_context_type(context_type: str) -> bool:
    """Validate context type"""
    return context_type in ["minimal", "standard", "detailed"]


def sanitize_string(value: Any, max_length: Optional[int] = None) -> str:
    """Sanitize a string value"""
    if not isinstance(value, str):
        value = str(value)
    
    # Remove control characters
    import re
    value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
    
    if max_length:
        value = value[:max_length]
    
    return value.strip()

