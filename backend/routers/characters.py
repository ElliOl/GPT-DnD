"""
Character Routes

All /api/characters/* endpoints
"""

from fastapi import APIRouter, HTTPException
from .dependencies import get_game_engine

router = APIRouter(prefix="/api/characters", tags=["characters"])


@router.get("")
async def get_characters():
    """List all player characters"""
    game_engine = get_game_engine()
    return {"characters": game_engine.characters}


@router.get("/{name}")
async def get_character(name: str):
    """Get specific character info"""
    game_engine = get_game_engine()
    
    char = game_engine.get_character(name)
    if "error" in char:
        raise HTTPException(status_code=404, detail=char["error"])
    
    return char

