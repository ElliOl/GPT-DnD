"""
AI D&D Dungeon Master - FastAPI Backend

Main application entry point.
"""

import os
from contextlib import asynccontextmanager
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
from backend.models.game_state import PlayerAction, DMResponse, GameState
from game_engine.engine import GameEngine
from pydantic import BaseModel


# Global instances
dm_agent: DMAgent = None
game_engine: GameEngine = None
tts_service: TTSService = None


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

    # Initialize DM Agent
    dm_agent = DMAgent(
        ai_client=ai_client,
        game_engine=game_engine,
        tts_service=tts_service,
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
        response = await dm_agent.process_player_input(
            player_message=action.message,
            voice=action.voice,
            adventure_context=action.adventure_context,
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
