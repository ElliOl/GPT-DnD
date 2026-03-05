"""
Game Routes

Main game endpoints: /api/action, /api/game-state, /api/reset, /api/additional-rules
"""

import traceback
from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .dependencies import get_dm_agent, get_game_engine, current_adventure, context_manager
from backend.models.game_state import PlayerAction, DMResponse

router = APIRouter(tags=["game"])


@router.post("/api/action", response_model=DMResponse)
async def player_action(action: PlayerAction):
    """
    Player takes an action
    
    The DM processes the action and responds with narration.
    """
    dm_agent = get_dm_agent()
    
    try:
        # If using modular adventure system, get smart context
        adventure_context_str = None
        if current_adventure and context_manager:
            # Use smart context manager to get appropriate context level
            adventure_context_str = context_manager.get_context_for_turn(
                action.message,
                turn_type="auto"  # Auto-detect based on player input
            )
        elif action.adventure_context:
            # Legacy: Use passed adventure_context dict
            adventure_context_str = action.adventure_context
        
        response = await dm_agent.process_player_input(
            player_message=action.message,
            voice=action.voice,
            adventure_context=adventure_context_str,
            session_state=action.session_state,
        )
        
        # Automatically analyze quest updates from DM response
        quest_updates = []
        if response.get("narrative") and action.session_state:
            try:
                from backend.services.quest_log_analyzer import extract_quest_updates_from_narrative
                current_quests = action.session_state.get("quest_log", [])
                quest_updates = extract_quest_updates_from_narrative(
                    response["narrative"],
                    current_quests
                )
            except Exception as e:
                # Don't fail the request if quest analysis fails
                print(f"⚠️  Quest log analysis failed: {e}")
        
        # Include quest updates in response
        response["quest_updates"] = quest_updates
        
        return DMResponse(
            narrative=response["narrative"],
            audio_url=response.get("audio_url"),
            game_state=response["game_state"],
            tool_results=response.get("tool_results", []),
            quest_updates=quest_updates,
        )
    
    except Exception as e:
        error_detail = str(e) if str(e) else f"Unknown error: {type(e).__name__}"
        error_detail += f"\n\n{traceback.format_exc()}"
        print(f"❌ Error in player_action: {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/api/game-state")
async def get_game_state():
    """Get current game state"""
    game_engine = get_game_engine()
    return game_engine.get_state()


@router.post("/api/reset")
async def reset_session():
    """Reset the DM conversation (start fresh)"""
    dm_agent = get_dm_agent()
    dm_agent.reset_conversation()
    return {"message": "Session reset"}


class RestoreConversationRequest(BaseModel):
    messages: List[Dict[str, Any]]


@router.post("/api/restore-conversation")
async def restore_conversation(request: RestoreConversationRequest):
    """Restore conversation history to the DM agent"""
    dm_agent = get_dm_agent()
    try:
        dm_agent.restore_conversation_history(request.messages)
        return {"message": f"Restored {len(request.messages)} messages to conversation history"}
    except Exception as e:
        error_detail = f"Error restoring conversation: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)


class RulesRequest(BaseModel):
    content: str


@router.get("/api/additional-rules")
async def get_additional_rules():
    """Get additional rules that supplement core D&D rules"""
    try:
        data_dir = Path(__file__).parent.parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        rules_path = data_dir / "additional_rules.txt"
        
        if not rules_path.exists():
            return {
                "content": "# Additional Rules\n\nAdd your custom rules here.\nThese will be appended to the core D&D 5e rules.\n",
                "file": "additional_rules.txt"
            }
        
        content = rules_path.read_text(encoding='utf-8')
        return {
            "content": content,
            "file": "additional_rules.txt"
        }
    except Exception as e:
        error_detail = f"Error reading additional rules: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)


@router.post("/api/additional-rules")
async def save_additional_rules(request: RulesRequest):
    """Save additional rules that supplement core D&D rules"""
    if not request.content:
        raise HTTPException(status_code=400, detail="Content is required")
    
    data_dir = Path(__file__).parent.parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    rules_path = data_dir / "additional_rules.txt"
    
    try:
        rules_path.write_text(request.content, encoding='utf-8')
        return {
            "message": "Additional rules saved successfully",
            "length": len(request.content)
        }
    except Exception as e:
        error_detail = f"Error saving additional rules: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)

