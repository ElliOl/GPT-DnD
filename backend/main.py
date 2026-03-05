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
    
    # Load environment variables FIRST, before any service initialization
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    print(f"🔍 Loading .env from: {env_path.absolute()}")
    print(f"   .env exists: {env_path.exists()}")
    
    # Load .env file
    result = load_dotenv(env_path, override=True)
    print(f"   .env loaded successfully: {result}")
    
    # Verify key environment variables
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    print(f"   OPENAI_API_KEY loaded: {openai_key is not None} (length: {len(openai_key) if openai_key else 0})")
    print(f"   ANTHROPIC_API_KEY loaded: {anthropic_key is not None} (length: {len(anthropic_key) if anthropic_key else 0})")
    
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
    
    # Auto-load last played adventure if available
    from backend.utils.adventure_config import get_last_adventure
    from backend.services.adventure import AdventureContext, ContextManager
    last_adventure_id = get_last_adventure()
    if last_adventure_id:
        try:
            print(f"🔄 Auto-loading last played adventure: {last_adventure_id}")
            deps.current_adventure = AdventureContext(last_adventure_id)
            deps.context_manager = ContextManager(deps.current_adventure)
            deps.dm_agent.adventure_context = deps.current_adventure
            print(f"✅ Auto-loaded adventure: {deps.current_adventure.metadata['name']}")
        except Exception as e:
            print(f"⚠️  Failed to auto-load last adventure '{last_adventure_id}': {e}")
            print("   Adventure will need to be loaded manually")
    
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
    import sys
    from pathlib import Path
    
    # Check if we're using the venv Python
    venv_python3 = Path(__file__).parent / "venv" / "bin" / "python3"
    current_exec = Path(sys.executable).resolve()
    venv_exec3 = venv_python3.resolve() if venv_python3.exists() else None
    
    # Check if we're using venv
    if venv_exec3 and current_exec != venv_exec3:
        print(f"⚠️  ERROR: Not using venv Python!")
        print(f"   Current: {sys.executable}")
        print(f"   Venv:    {venv_exec3}")
        print(f"   Please restart using: cd backend && venv/bin/python3 main.py")
        print(f"   Or activate venv first: cd backend && source venv/bin/activate && python3 main.py")
        sys.exit(1)
    
    # Verify Anthropic version
    try:
        import anthropic
        if anthropic.__version__ < "0.34.0":
            print(f"⚠️  WARNING: Anthropic SDK version {anthropic.__version__} is too old!")
            print(f"   Need version 0.34.0+ for tools support")
            print(f"   Run: venv/bin/python3 -m pip install --upgrade 'anthropic>=0.34.0'")
    except ImportError:
        print("⚠️  ERROR: Anthropic SDK not found!")
        sys.exit(1)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
    )
