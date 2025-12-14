"""
AI Provider Configuration and Factory

Supports multiple AI providers:
- Anthropic Claude (claude-3-5-sonnet, claude-3-opus, etc.)
- OpenAI (gpt-4, gpt-3.5-turbo, etc.)
- Ollama (local open-source models)
- LM Studio (local models)
- OpenRouter (access to many models)
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel


class AIProvider(str, Enum):
    """Supported AI providers"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"
    LM_STUDIO = "lm_studio"
    OPENROUTER = "openrouter"


class AIProviderConfig(BaseModel):
    """Configuration for AI provider"""
    provider: AIProvider
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None  # For local/custom endpoints
    temperature: float = 0.7
    max_tokens: int = 2000

    class Config:
        use_enum_values = True


# Default configurations for each provider
PROVIDER_DEFAULTS = {
    AIProvider.ANTHROPIC: {
        "model": "claude-3-5-sonnet-20241022",
        "base_url": "https://api.anthropic.com",
    },
    AIProvider.OPENAI: {
        "model": "gpt-4-turbo-preview",
        "base_url": "https://api.openai.com/v1",
    },
    AIProvider.OLLAMA: {
        "model": "phi3:mini",  # Optimized for Intel Mac (fastest on CPU)
        "base_url": "http://localhost:11434",
    },
    AIProvider.LM_STUDIO: {
        "model": "local-model",
        "base_url": "http://localhost:1234/v1",
    },
    AIProvider.OPENROUTER: {
        "model": "anthropic/claude-3.5-sonnet",
        "base_url": "https://openrouter.ai/api/v1",
    },
}


# Recommended models for D&D DMing
RECOMMENDED_MODELS = {
    AIProvider.ANTHROPIC: [
        "claude-3-5-sonnet-20241022",  # Best balance
        "claude-3-opus-20240229",      # Most creative
        "claude-3-sonnet-20240229",    # Fast, good quality
        "claude-3-haiku-20240307",     # Fastest, cheapest
    ],
    AIProvider.OPENAI: [
        "gpt-4-turbo-preview",
        "gpt-4",
        "gpt-3.5-turbo",
    ],
    AIProvider.OLLAMA: [
        "phi3:mini",           # Best for Intel Mac (fastest, 4-8 sec/100 tokens)
        "llama3.1:8b",         # Good quality, slower on Intel (8-15 sec/100 tokens)
        "mistral:7b-instruct",  # Good balance (6-12 sec/100 tokens)
        "llama2",              # Older, but stable
        "mixtral",             # Larger, slower on Intel
    ],
    AIProvider.LM_STUDIO: [
        "local-model",  # Use whatever model loaded in LM Studio
    ],
    AIProvider.OPENROUTER: [
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-4-turbo-preview",
        "meta-llama/llama-2-70b-chat",
        "mistralai/mixtral-8x7b-instruct",
    ],
}
