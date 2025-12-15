"""
Configuration Routes

All /api/config/* and /api/health/* endpoints
"""

import os
import httpx
from fastapi import APIRouter

router = APIRouter(tags=["config"])


@router.get("/api/config/providers")
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


@router.get("/api/health/ollama")
async def check_ollama_health():
    """Check if Ollama server is running and accessible"""
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
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

