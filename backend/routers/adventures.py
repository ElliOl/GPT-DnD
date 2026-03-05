"""
Adventure System Routes

All /api/adventures/* endpoints
"""

import json
import traceback
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.adventure import AdventureContext, ContextManager
from backend.routers.dependencies import (
    current_adventure, 
    context_manager,
    get_adventure
)

router = APIRouter(prefix="/api/adventures", tags=["adventures"])


@router.get("/available")
async def get_available_adventures():
    """List all available adventure modules"""
    adventures_dir = Path(__file__).parent.parent / "adventures"
    if not adventures_dir.exists():
        return {"adventures": []}
    
    adventures = []
    for adventure_path in adventures_dir.iterdir():
        if adventure_path.is_dir():
            metadata_path = adventure_path / "adventure.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path) as f:
                        metadata = json.load(f)
                        adventures.append({
                            "id": metadata.get("id", adventure_path.name),
                            "name": metadata.get("name", adventure_path.name),
                            "description": metadata.get("description", ""),
                            "level_range": metadata.get("level_range", [1, 20]),
                            "estimated_sessions": metadata.get("estimated_sessions"),
                        })
                except Exception as e:
                    print(f"Error loading adventure {adventure_path.name}: {e}")
    
    return {"adventures": adventures}


@router.post("/load")
async def load_adventure(request: dict):
    """
    Load an adventure module
    
    Request body:
        {
            "adventure_id": "lost_mines_of_phandelver"
        }
    """
    global current_adventure, context_manager
    
    adventure_id = request.get("adventure_id")
    if not adventure_id:
        raise HTTPException(status_code=400, detail="adventure_id is required")
    
    try:
        # Load adventure
        current_adventure = AdventureContext(adventure_id)
        context_manager = ContextManager(current_adventure)
        
        # Save as last played adventure for auto-loading
        from backend.utils.adventure_config import save_last_adventure
        save_last_adventure(adventure_id)
        
        # Update DM agent with adventure context
        from backend.routers.dependencies import get_dm_agent
        try:
            dm_agent = get_dm_agent()
            dm_agent.adventure_context = current_adventure
        except:
            pass  # DM agent not initialized yet
        
        return {
            "success": True,
            "message": f"Loaded adventure: {current_adventure.metadata['name']}",
            "adventure_info": current_adventure.get_adventure_info(),
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        error_detail = f"Failed to load adventure: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/current")
async def get_current_adventure():
    """
    Get currently loaded adventure info
    If no adventure is loaded, attempts to auto-load the last played adventure
    """
    global current_adventure, context_manager
    
    # If no adventure loaded, try to auto-load the last played one
    if not current_adventure:
        from backend.utils.adventure_config import get_last_adventure
        last_adventure_id = get_last_adventure()
        
        if last_adventure_id:
            try:
                print(f"🔄 Auto-loading last played adventure: {last_adventure_id}")
                current_adventure = AdventureContext(last_adventure_id)
                context_manager = ContextManager(current_adventure)
                
                # Update DM agent with adventure context
                from backend.routers.dependencies import get_dm_agent
                try:
                    dm_agent = get_dm_agent()
                    dm_agent.adventure_context = current_adventure
                except:
                    pass  # DM agent not initialized yet
                
                print(f"✅ Auto-loaded adventure: {current_adventure.metadata['name']}")
            except Exception as e:
                print(f"⚠️  Failed to auto-load last adventure '{last_adventure_id}': {e}")
                return {"loaded": False, "auto_load_failed": True, "last_adventure_id": last_adventure_id}
    
    if not current_adventure:
        return {"loaded": False}
    
    return {
        "loaded": True,
        "adventure_info": current_adventure.get_adventure_info(),
        "metadata": current_adventure.metadata,
    }


@router.post("/update")
async def update_adventure_state(request: dict):
    """
    Update adventure state
    
    Request body can include:
        {
            "location": "new_location_id",
            "chapter": "new_chapter_id",
            "event": "Important event description",
            "met_npc": "npc_id",
            "quest": {"id": "quest1", "status": "completed"},
            "party_knowledge": {"key": "knows_something", "value": true},
            "session_number": 5,
            "party_level": 3
        }
    """
    adventure = get_adventure()
    
    try:
        updates = request
        
        if "location" in updates:
            adventure.update_location(updates["location"])
        
        if "chapter" in updates:
            try:
                force = updates.get("force_chapter_change", False)
                adventure.update_chapter(updates["chapter"], force=force)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        if "event" in updates:
            adventure.add_event(updates["event"])
        
        if "met_npc" in updates:
            adventure.meet_npc(updates["met_npc"])
        
        if "quest" in updates:
            quest = updates["quest"]
            if "status" in quest:
                adventure.update_quest_status(quest["id"], quest["status"])
            else:
                adventure.add_quest(quest)
        
        if "party_knowledge" in updates:
            knowledge = updates["party_knowledge"]
            adventure.update_party_knowledge(knowledge["key"], knowledge["value"])
        
        if "session_number" in updates:
            adventure.update_session_number(updates["session_number"])
        
        if "party_level" in updates:
            adventure.update_party_level(updates["party_level"])
        
        return {
            "success": True,
            "metadata": adventure.metadata,
        }
    except Exception as e:
        error_detail = f"Failed to update adventure: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/context/{context_type}")
async def get_adventure_context(context_type: str):
    """
    Get adventure context at specified detail level
    
    context_type: minimal, standard, or detailed
    """
    adventure = get_adventure()
    
    if context_type == "minimal":
        context = adventure.get_minimal_context()
    elif context_type == "standard":
        context = adventure.get_standard_context()
    elif context_type == "detailed":
        context = adventure.get_detailed_context()
    else:
        raise HTTPException(status_code=400, detail="Invalid context_type. Use minimal, standard, or detailed")
    
    return {"context": context, "type": context_type}


@router.get("/location/{location_id}")
async def get_location_details(location_id: str, area_id: Optional[str] = None):
    """Get detailed information about a location or specific area"""
    adventure = get_adventure()
    
    try:
        details = adventure.get_location_details(location_id, area_id)
        return {"location_id": location_id, "area_id": area_id, "details": details}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/npc/{npc_id}")
async def get_npc_info(npc_id: str):
    """Get information about an NPC"""
    adventure = get_adventure()
    
    try:
        info = adventure.get_npc_info(npc_id)
        return {"npc_id": npc_id, "info": info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chapters")
async def list_chapters():
    """List all available chapters in current adventure"""
    adventure = get_adventure()
    return {"chapters": adventure.list_available_chapters()}


@router.get("/accessible-locations")
async def get_accessible_locations():
    """Get list of locations accessible for travel/freeroaming"""
    adventure = get_adventure()
    
    try:
        accessible = adventure.get_accessible_locations()
        return accessible
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/long-rest")
async def process_long_rest():
    """
    Process a long rest and check for level up eligibility
    
    Returns level up information if party is eligible.
    """
    adventure = get_adventure()
    
    try:
        current_state = adventure.metadata.get("current_state", {})
        current_level = current_state.get("party_level", 1)
        
        result = adventure.leveling.process_long_rest(current_level)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/progression")
async def get_progression_summary():
    """Get summary of party progression across combat, exploration, and social pillars"""
    adventure = get_adventure()
    
    try:
        summary = adventure.leveling.get_progression_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/track-combat")
async def track_combat_encounter(encounter_id: str, xp_value: int = 0):
    """Track a combat encounter completion"""
    adventure = get_adventure()
    
    try:
        adventure.leveling.track_combat_encounter(encounter_id, xp_value)
        return {"success": True, "message": f"Tracked combat encounter: {encounter_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/track-exploration")
async def track_exploration(milestone: str, location_id: Optional[str] = None):
    """Track an exploration milestone"""
    adventure = get_adventure()
    
    try:
        adventure.leveling.track_exploration(milestone, location_id)
        return {"success": True, "message": f"Tracked exploration: {milestone}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/track-social")
async def track_social_interaction(interaction_type: str, npc_id: Optional[str] = None, quest_id: Optional[str] = None):
    """Track a social interaction (NPC met, quest completed, etc.)"""
    adventure = get_adventure()
    
    try:
        adventure.leveling.track_social_interaction(interaction_type, npc_id, quest_id)
        return {"success": True, "message": f"Tracked social interaction: {interaction_type}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/locations")
async def list_locations():
    """List all available locations in current adventure"""
    adventure = get_adventure()
    return {"locations": adventure.list_available_locations()}


@router.get("/npcs")
async def list_npcs():
    """List all available NPCs in current adventure"""
    adventure = get_adventure()
    return {"npcs": adventure.list_available_npcs()}


class QuestLogUpdateRequest(BaseModel):
    narrative: str
    current_quests: List[Dict[str, Any]]


@router.post("/analyze-quest-updates")
async def analyze_quest_updates(request: QuestLogUpdateRequest):
    """
    Analyze DM narrative for quest updates
    
    Request body:
        {
            "narrative": "DM's narrative response",
            "current_quests": [{"id": "...", "name": "...", "status": "...", ...}]
        }
    
    Returns:
        {
            "updates": [
                {
                    "action": "create" | "update" | "complete" | "fail",
                    "quest_id": Optional[str],
                    "name": str,
                    "description": Optional[str],
                    "status": str,
                    "notes": Optional[str]
                }
            ]
        }
    """
    from backend.services.quest_log_analyzer import extract_quest_updates_from_narrative
    
    try:
        updates = extract_quest_updates_from_narrative(
            request.narrative,
            request.current_quests
        )
        return {"updates": updates}
    except Exception as e:
        error_detail = f"Failed to analyze quest updates: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)

