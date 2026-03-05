"""
Router Dependencies

Shared dependencies for routers (global service instances).
"""

from typing import Optional
from backend.services.dm_agent import DMAgent
from backend.services.tts_service import TTSService
from backend.services.adventure import AdventureContext, ContextManager
from game_engine.engine import GameEngine

# Global instances (set by main.py on startup)
dm_agent: Optional[DMAgent] = None
game_engine: Optional[GameEngine] = None
tts_service: Optional[TTSService] = None
current_adventure: Optional[AdventureContext] = None
context_manager: Optional[ContextManager] = None


def get_dm_agent() -> DMAgent:
    """Get DM agent instance"""
    if dm_agent is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="DM Agent not initialized")
    return dm_agent


def get_game_engine() -> GameEngine:
    """Get game engine instance"""
    if game_engine is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Game engine not initialized")
    return game_engine


def get_tts_service() -> TTSService:
    """Get TTS service instance"""
    if tts_service is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="TTS service not initialized")
    return tts_service


def get_adventure() -> AdventureContext:
    """Get current adventure instance"""
    if current_adventure is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="No adventure loaded")
    return current_adventure


def get_context_manager() -> ContextManager:
    """Get context manager instance"""
    if context_manager is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="No adventure loaded")
    return context_manager

