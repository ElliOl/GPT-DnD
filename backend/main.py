"""
AI D&D Dungeon Master - FastAPI Backend

Main application entry point.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.dm_agent import DMAgent
from backend.services.ai_factory import AIClientFactory
from backend.services.tts_service import TTSService
from backend.routers import (
    adventures,
    characters,
    game,
    audio,
    config,
)
from game_engine.engine import GameEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    print("🎲 Initializing AI Dungeon Master...")
    
    # Load environment variables
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
    
    # Import dependencies module to set globals
    import backend.routers.dependencies as deps
    
    # Initialize game engine
    deps.game_engine = GameEngine(data_dir="data")
    print("✅ Game engine loaded")
    
    # Initialize TTS service
    deps.tts_service = TTSService(
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
    deps.dm_agent = DMAgent(
        ai_client=ai_client,
        game_engine=deps.game_engine,
        tts_service=deps.tts_service,
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

# Include routers
app.include_router(adventures.router)
app.include_router(characters.router)
app.include_router(game.router)
app.include_router(audio.router)
app.include_router(config.router)


# ============================================================================
# Root and WebSocket endpoints
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


@app.websocket("/ws/game")
async def websocket_game(websocket: WebSocket):
    """
    WebSocket for real-time game state updates
    
    Sends updates when HP changes, combat starts, etc.
    """
    from backend.routers.dependencies import get_game_engine
    
    await websocket.accept()
    
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_json()
            
            # Echo back current game state
            # (In a real implementation, this would push updates when state changes)
            game_engine = get_game_engine()
            if game_engine:
                state = game_engine.get_state()
                await websocket.send_json(state)
    
    except WebSocketDisconnect:
        print("WebSocket disconnected")


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
