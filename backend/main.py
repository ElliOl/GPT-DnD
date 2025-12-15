"""
AI D&D Dungeon Master - FastAPI Backend

Main application entry point.
"""

import os
import json
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.dm_agent import DMAgent
from backend.services.ai_factory import AIClientFactory
from backend.services.tts_service import TTSService
from backend.services.adventure_context import AdventureContext, ContextManager
from backend.models.game_state import PlayerAction, DMResponse, GameState
from game_engine.engine import GameEngine
from pydantic import BaseModel


# Global instances
dm_agent: DMAgent = None
game_engine: GameEngine = None
tts_service: TTSService = None
current_adventure: AdventureContext = None
context_manager: ContextManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    global dm_agent, game_engine, tts_service

    print("🎲 Initializing AI Dungeon Master...")

    # Load environment variables
    from dotenv import load_dotenv

    # Load .env from project root (parent directory)
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)

    # Initialize game engine
    game_engine = GameEngine(data_dir="data")
    print("✅ Game engine loaded")

    # Initialize TTS service
    tts_service = TTSService(
        provider=os.getenv("TTS_PROVIDER", "openai"),
        voice=os.getenv("TTS_VOICE", "onyx"),
    )
    print("✅ TTS service initialized")

    # Initialize AI client
    ai_client = AIClientFactory.from_env(
        provider=os.getenv("AI_PROVIDER", "anthropic"),
        model=os.getenv("AI_MODEL"),
    )
    print(f"✅ AI client initialized: {os.getenv('AI_PROVIDER', 'anthropic')}")

    # Initialize DM Agent (adventure_context will be set when adventure is loaded)
    dm_agent = DMAgent(
        ai_client=ai_client,
        game_engine=game_engine,
        tts_service=tts_service,
        adventure_context=None,  # Will be updated when adventure is loaded
    )
    print("✅ DM Agent ready")

    print("\n🎭 The Dungeon Master awaits...")
    print(f"📡 Server starting on http://localhost:8000")

    yield

    # Cleanup on shutdown
    print("\n👋 Shutting down AI Dungeon Master...")


# Create FastAPI app
app = FastAPI(
    title="AI D&D Dungeon Master",
    description="AI-powered Dungeon Master with voice narration and D&D 5e mechanics",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite default
        "http://localhost:3000",  # React default
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# API Routes
# ============================================================================


@app.get("/")
async def root():
    """API health check"""
    return {
        "message": "AI D&D Dungeon Master API",
        "status": "ready",
        "ai_provider": os.getenv("AI_PROVIDER", "anthropic"),
        "tts_enabled": True,
    }


@app.post("/api/action", response_model=DMResponse)
async def player_action(action: PlayerAction):
    """
    Player takes an action

    The DM processes the action and responds with narration.
    """
    if not dm_agent:
        raise HTTPException(status_code=503, detail="DM Agent not initialized")

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

        return DMResponse(
            narrative=response["narrative"],
            audio_url=response.get("audio_url"),
            game_state=response["game_state"],
            tool_results=response.get("tool_results", []),
        )

    except Exception as e:
        import traceback
        error_detail = str(e) if str(e) else f"Unknown error: {type(e).__name__}"
        # Always include traceback for debugging
        error_detail += f"\n\n{traceback.format_exc()}"
        print(f"❌ Error in player_action: {error_detail}")  # Log to console
        raise HTTPException(status_code=500, detail=error_detail)


@app.get("/api/game-state")
async def get_game_state():
    """Get current game state"""
    if not game_engine:
        raise HTTPException(status_code=503, detail="Game engine not initialized")

    return game_engine.get_state()


@app.get("/api/characters")
async def get_characters():
    """List all player characters"""
    if not game_engine:
        raise HTTPException(status_code=503, detail="Game engine not initialized")

    return {"characters": game_engine.characters}


@app.get("/api/characters/{name}")
async def get_character(name: str):
    """Get specific character info"""
    if not game_engine:
        raise HTTPException(status_code=503, detail="Game engine not initialized")

    char = game_engine.get_character(name)
    if "error" in char:
        raise HTTPException(status_code=404, detail=char["error"])

    return char


@app.get("/api/audio/{filename}")
async def get_audio(filename: str):
    """
    Serve cached audio files

    Audio is generated by TTS service and cached.
    """
    if not tts_service:
        raise HTTPException(status_code=503, detail="TTS service not initialized")

    audio_data = await tts_service.get_audio(filename)
    if not audio_data:
        raise HTTPException(status_code=404, detail="Audio file not found")

    return StreamingResponse(
        iter([audio_data]),
        media_type="audio/mpeg",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


@app.post("/api/reset")
async def reset_session():
    """Reset the DM conversation (start fresh)"""
    if not dm_agent:
        raise HTTPException(status_code=503, detail="DM Agent not initialized")

    dm_agent.reset_conversation()
    return {"message": "Session reset"}


class RulesRequest(BaseModel):
    content: str


@app.get("/api/additional-rules")
async def get_additional_rules():
    """Get additional rules that supplement core D&D rules"""
    from pathlib import Path
    
    try:
        # Store additional rules in data/additional_rules.txt
        data_dir = Path(__file__).parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        rules_path = data_dir / "additional_rules.txt"
        
        if not rules_path.exists():
            # Return default empty rules
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
        import traceback
        error_detail = f"Error reading additional rules: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)


@app.post("/api/additional-rules")
async def save_additional_rules(request: RulesRequest):
    """Save additional rules that supplement core D&D rules"""
    from pathlib import Path
    
    if not request.content:
        raise HTTPException(status_code=400, detail="Content is required")
    
    # Store in data/additional_rules.txt
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)  # Create data directory if it doesn't exist
    
    rules_path = data_dir / "additional_rules.txt"
    
    try:
        # Save to file
        rules_path.write_text(request.content, encoding='utf-8')
        
        # Note: Additional rules are automatically combined with core D&D rules
        # They'll be picked up on the next request
        
        return {
            "message": "Additional rules saved successfully",
            "length": len(request.content)
        }
    except Exception as e:
        import traceback
        error_detail = f"Error saving additional rules: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)




@app.post("/api/tts/clear-cache")
async def clear_tts_cache():
    """Clear TTS audio cache"""
    if not tts_service:
        raise HTTPException(status_code=503, detail="TTS service not initialized")

    tts_service.clear_cache()
    return {"message": "TTS cache cleared"}


# ============================================================================
# WebSocket for real-time updates
# ============================================================================


@app.websocket("/ws/game")
async def websocket_game(websocket: WebSocket):
    """
    WebSocket for real-time game state updates

    Sends updates when HP changes, combat starts, etc.
    """
    await websocket.accept()

    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_json()

            # Echo back current game state
            # (In a real implementation, this would push updates when state changes)
            if game_engine:
                state = game_engine.get_state()
                await websocket.send_json(state)

    except WebSocketDisconnect:
        print("WebSocket disconnected")


# ============================================================================
# Configuration endpoints
# ============================================================================


@app.get("/api/config/providers")
async def get_available_providers():
    """List available AI providers and models"""
    from backend.config.ai_providers import RECOMMENDED_MODELS, AIProvider

    return {
        "providers": [p.value for p in AIProvider],
        "models": {k.value: v for k, v in RECOMMENDED_MODELS.items()},
        "current": {
            "provider": os.getenv("AI_PROVIDER", "anthropic"),
            "model": os.getenv("AI_MODEL", "claude-3-5-sonnet-20241022"),
        },
    }


@app.get("/api/health/ollama")
async def check_ollama_health():
    """Check if Ollama server is running and accessible"""
    import httpx
    
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            # Try to list models (lightweight check)
            response = await client.get(f"{base_url}/api/tags")
            
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                
                return {
                    "status": "healthy",
                    "base_url": base_url,
                    "available_models": model_names,
                    "model_count": len(model_names),
                }
            else:
                return {
                    "status": "error",
                    "message": f"Ollama returned status {response.status_code}",
                }
    except httpx.ConnectError:
        return {
            "status": "unavailable",
            "message": f"Cannot connect to Ollama at {base_url}. Is the server running?",
            "help": "Run 'ollama serve' to start the Ollama server",
        }
    except httpx.TimeoutException:
        return {
            "status": "timeout",
            "message": f"Connection to Ollama at {base_url} timed out",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


# ============================================================================
# Adventure System Endpoints
# ============================================================================


@app.get("/api/adventures/available")
async def get_available_adventures():
    """List all available adventure modules"""
    from pathlib import Path
    
    adventures_dir = Path(__file__).parent / "adventures"
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


@app.post("/api/adventures/load")
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
        
        # Update DM agent with adventure context
        global dm_agent
        if dm_agent:
            dm_agent.adventure_context = current_adventure
        
        return {
            "success": True,
            "message": f"Loaded adventure: {current_adventure.metadata['name']}",
            "adventure_info": current_adventure.get_adventure_info(),
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        error_detail = f"Failed to load adventure: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)


@app.get("/api/adventures/current")
async def get_current_adventure():
    """Get currently loaded adventure info"""
    if not current_adventure:
        return {"loaded": False}
    
    return {
        "loaded": True,
        "adventure_info": current_adventure.get_adventure_info(),
        "metadata": current_adventure.metadata,
    }


@app.post("/api/adventures/update")
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
    if not current_adventure:
        raise HTTPException(status_code=400, detail="No adventure loaded")
    
    try:
        updates = request
        
        if "location" in updates:
            current_adventure.update_location(updates["location"])
        
        if "chapter" in updates:
            try:
                # Allow force flag for DM override when narrative progression makes sense
                force = updates.get("force_chapter_change", False)
                current_adventure.update_chapter(updates["chapter"], force=force)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        if "event" in updates:
            current_adventure.add_event(updates["event"])
        
        if "met_npc" in updates:
            current_adventure.meet_npc(updates["met_npc"])
        
        if "quest" in updates:
            quest = updates["quest"]
            if "status" in quest:
                current_adventure.update_quest_status(quest["id"], quest["status"])
            else:
                current_adventure.add_quest(quest)
        
        if "party_knowledge" in updates:
            knowledge = updates["party_knowledge"]
            current_adventure.update_party_knowledge(knowledge["key"], knowledge["value"])
        
        if "session_number" in updates:
            current_adventure.update_session_number(updates["session_number"])
        
        if "party_level" in updates:
            current_adventure.update_party_level(updates["party_level"])
        
        return {
            "success": True,
            "metadata": current_adventure.metadata,
        }
    except Exception as e:
        import traceback
        error_detail = f"Failed to update adventure: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)


@app.get("/api/adventures/context/{context_type}")
async def get_adventure_context(context_type: str):
    """
    Get adventure context at specified detail level
    
    context_type: minimal, standard, or detailed
    """
    if not current_adventure:
        raise HTTPException(status_code=400, detail="No adventure loaded")
    
    if context_type == "minimal":
        context = current_adventure.get_minimal_context()
    elif context_type == "standard":
        context = current_adventure.get_standard_context()
    elif context_type == "detailed":
        context = current_adventure.get_detailed_context()
    else:
        raise HTTPException(status_code=400, detail="Invalid context_type. Use minimal, standard, or detailed")
    
    return {"context": context, "type": context_type}


@app.get("/api/adventures/location/{location_id}")
async def get_location_details(location_id: str, area_id: Optional[str] = None):
    """Get detailed information about a location or specific area"""
    if not current_adventure:
        raise HTTPException(status_code=400, detail="No adventure loaded")
    
    try:
        details = current_adventure.get_location_details(location_id, area_id)
        return {"location_id": location_id, "area_id": area_id, "details": details}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/adventures/npc/{npc_id}")
async def get_npc_info(npc_id: str):
    """Get information about an NPC"""
    if not current_adventure:
        raise HTTPException(status_code=400, detail="No adventure loaded")
    
    try:
        info = current_adventure.get_npc_info(npc_id)
        return {"npc_id": npc_id, "info": info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/adventures/chapters")
async def list_chapters():
    """List all available chapters in current adventure"""
    if not current_adventure:
        raise HTTPException(status_code=400, detail="No adventure loaded")
    
    return {"chapters": current_adventure.list_available_chapters()}


@app.get("/api/adventures/accessible-locations")
async def get_accessible_locations():
    """Get list of locations accessible for travel/freeroaming"""
    if not current_adventure:
        raise HTTPException(status_code=400, detail="No adventure loaded")
    
    try:
        accessible = current_adventure.get_accessible_locations()
        return accessible
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/adventures/long-rest")
async def process_long_rest():
    """
    Process a long rest and check for level up eligibility
    
    Returns level up information if party is eligible.
    DM should announce level up and allow players to update character sheets.
    """
    if not current_adventure:
        raise HTTPException(status_code=400, detail="No adventure loaded")
    
    try:
        current_state = current_adventure.metadata.get("current_state", {})
        current_level = current_state.get("party_level", 1)
        
        result = current_adventure.leveling.process_long_rest(current_level)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/adventures/progression")
async def get_progression_summary():
    """Get summary of party progression across combat, exploration, and social pillars"""
    if not current_adventure:
        raise HTTPException(status_code=400, detail="No adventure loaded")
    
    try:
        summary = current_adventure.leveling.get_progression_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/adventures/track-combat")
async def track_combat_encounter(encounter_id: str, xp_value: int = 0):
    """Track a combat encounter completion"""
    if not current_adventure:
        raise HTTPException(status_code=400, detail="No adventure loaded")
    
    try:
        current_adventure.leveling.track_combat_encounter(encounter_id, xp_value)
        return {"success": True, "message": f"Tracked combat encounter: {encounter_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/adventures/track-exploration")
async def track_exploration(milestone: str, location_id: Optional[str] = None):
    """Track an exploration milestone"""
    if not current_adventure:
        raise HTTPException(status_code=400, detail="No adventure loaded")
    
    try:
        current_adventure.leveling.track_exploration(milestone, location_id)
        return {"success": True, "message": f"Tracked exploration: {milestone}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/adventures/track-social")
async def track_social_interaction(interaction_type: str, npc_id: Optional[str] = None, quest_id: Optional[str] = None):
    """Track a social interaction (NPC met, quest completed, etc.)"""
    if not current_adventure:
        raise HTTPException(status_code=400, detail="No adventure loaded")
    
    try:
        current_adventure.leveling.track_social_interaction(interaction_type, npc_id, quest_id)
        return {"success": True, "message": f"Tracked social interaction: {interaction_type}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/adventures/locations")
async def list_locations():
    """List all available locations in current adventure"""
    if not current_adventure:
        raise HTTPException(status_code=400, detail="No adventure loaded")
    
    return {"locations": current_adventure.list_available_locations()}


@app.get("/api/adventures/npcs")
async def list_npcs():
    """List all available NPCs in current adventure"""
    if not current_adventure:
        raise HTTPException(status_code=400, detail="No adventure loaded")
    
    return {"npcs": current_adventure.list_available_npcs()}


# ============================================================================
# Development helpers
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
    )
