"""
AI Client Factory

Creates appropriate AI client based on provider configuration.
"""

from typing import Optional
from ..config.ai_providers import AIProvider, AIProviderConfig, PROVIDER_DEFAULTS
from .ai_client_base import BaseAIClient
from .anthropic_client import AnthropicClient
from .openai_client import OpenAIClient
from .ollama_client import OllamaClient


class AIClientFactory:
    """Factory for creating AI clients"""

    @staticmethod
    def create_client(config: AIProviderConfig) -> BaseAIClient:
        """
        Create AI client based on configuration

        Args:
            config: Provider configuration

        Returns:
            Initialized AI client

        Raises:
            ValueError: If provider is not supported
        """

        # Get defaults for provider
        defaults = PROVIDER_DEFAULTS.get(config.provider, {})

        # Use provided values or defaults
        base_url = config.base_url or defaults.get("base_url")
        model = config.model or defaults.get("model")

        if config.provider == AIProvider.ANTHROPIC:
            return AnthropicClient(
                api_key=config.api_key,
                base_url=base_url,
                model=model,
            )

        elif config.provider == AIProvider.OPENAI:
            return OpenAIClient(
                api_key=config.api_key,
                base_url=base_url,
                model=model,
            )

        elif config.provider == AIProvider.OLLAMA:
            return OllamaClient(
                base_url=base_url or "http://localhost:11434",
                model=model,
            )

        elif config.provider == AIProvider.LM_STUDIO:
            # LM Studio uses OpenAI-compatible API
            return OpenAIClient(
                api_key="lm-studio",  # LM Studio doesn't require real key
                base_url=base_url or "http://localhost:1234/v1",
                model=model,
            )

        elif config.provider == AIProvider.OPENROUTER:
            # OpenRouter uses OpenAI-compatible API
            return OpenAIClient(
                api_key=config.api_key,
                base_url=base_url or "https://openrouter.ai/api/v1",
                model=model,
            )

        else:
            raise ValueError(f"Unsupported AI provider: {config.provider}")

    @staticmethod
    def from_env(
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> BaseAIClient:
        """
        Create client from environment variables

        Looks for:
        - AI_PROVIDER (default: anthropic)
        - AI_MODEL (default: provider's default model)
        - ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.

        Args:
            provider: Override provider from env
            model: Override model from env

        Returns:
            Initialized AI client
        """
        import os

        provider_name = provider or os.getenv("AI_PROVIDER", "anthropic")
        provider_enum = AIProvider(provider_name)

        defaults = PROVIDER_DEFAULTS.get(provider_enum, {})
        model_name = model or os.getenv("AI_MODEL", defaults.get("model"))

        # Get API key from environment
        api_key = None
        if provider_enum == AIProvider.ANTHROPIC:
            api_key = os.getenv("ANTHROPIC_API_KEY")
        elif provider_enum == AIProvider.OPENAI:
            api_key = os.getenv("OPENAI_API_KEY")
        elif provider_enum == AIProvider.OPENROUTER:
            api_key = os.getenv("OPENROUTER_API_KEY")

        config = AIProviderConfig(
            provider=provider_enum,
            model=model_name,
            api_key=api_key,
        )

        return AIClientFactory.create_client(config)
