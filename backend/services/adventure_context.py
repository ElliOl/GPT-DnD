"""
Adventure Context - Compatibility Shim

This module maintains backward compatibility by re-exporting from the new modular structure.
New code should import from backend.services.adventure instead.
"""

# Re-export from new modular structure
from .adventure import AdventureContext, ContextManager

__all__ = ['AdventureContext', 'ContextManager']
