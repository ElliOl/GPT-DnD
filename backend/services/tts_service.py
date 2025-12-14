"""
Text-to-Speech Service

Handles audio generation for DM narration.
Supports multiple TTS providers with caching.
"""

import os
import hashlib
from pathlib import Path
from typing import Optional
import aiofiles
from openai import AsyncOpenAI


class TTSService:
    """
    Text-to-Speech service with caching

    Generates audio for DM narration and caches results
    to avoid regenerating the same text.
    """

    def __init__(
        self,
        provider: str = "openai",
        voice: str = "onyx",
        cache_dir: str = "audio_cache",
    ):
        self.provider = provider
        self.voice = voice
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.enabled = False

        # Initialize TTS client
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            # Check if API key is valid (not a placeholder)
            if api_key and api_key not in ["your-key-here", "your_api_key_here", ""]:
                try:
                    self.client = AsyncOpenAI(api_key=api_key)
                    self.enabled = True
                except Exception:
                    self.enabled = False
                    print("⚠️  TTS: OpenAI API key invalid, TTS disabled")
            else:
                self.enabled = False
                print("⚠️  TTS: OpenAI API key not configured, TTS disabled")
        else:
            raise ValueError(f"Unsupported TTS provider: {provider}")

    def _get_cache_key(self, text: str, voice: str) -> str:
        """Generate cache key from text + voice"""
        content = f"{text}:{voice}"
        return hashlib.md5(content.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get path to cached audio file"""
        return self.cache_dir / f"{cache_key}.mp3"

    async def generate(
        self, text: str, voice: Optional[str] = None, use_cache: bool = True
    ) -> Optional[str]:
        """
        Generate audio for text

        Args:
            text: Text to speak
            voice: Voice to use (defaults to service voice)
            use_cache: Whether to use/save cache

        Returns:
            URL to audio file, or None if TTS is disabled/failed
        """
        # Return None if TTS is not enabled
        if not self.enabled:
            return None

        voice = voice or self.voice
        cache_key = self._get_cache_key(text, voice)
        cache_path = self._get_cache_path(cache_key)

        # Check cache
        if use_cache and cache_path.exists():
            return f"/api/audio/{cache_key}.mp3"

        # Generate audio
        try:
            if self.provider == "openai":
                audio_data = await self._generate_openai(text, voice)
            else:
                raise ValueError(f"Unsupported TTS provider: {self.provider}")

            # Save to cache
            async with aiofiles.open(cache_path, "wb") as f:
                await f.write(audio_data)

            return f"/api/audio/{cache_key}.mp3"
        except Exception as e:
            # If TTS generation fails, return None (silent failure)
            print(f"⚠️  TTS generation failed: {e}")
            return None

    async def _generate_openai(self, text: str, voice: str) -> bytes:
        """Generate audio using OpenAI TTS"""
        response = await self.client.audio.speech.create(
            model="tts-1", voice=voice, input=text
        )

        return response.content

    async def get_audio(self, filename: str) -> Optional[bytes]:
        """Retrieve cached audio file"""
        path = self.cache_dir / filename
        if not path.exists():
            return None

        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    def clear_cache(self):
        """Delete all cached audio files"""
        for file in self.cache_dir.glob("*.mp3"):
            file.unlink()


# NPC voice presets (from your campaign_voices.py)
NPC_VOICES = {
    "narrator": "onyx",  # Deep, authoritative
    "gundren_rockseeker": "echo",  # Dwarf merchant
    "sildar_hallwinter": "fable",  # Noble fighter
    "goblin": "shimmer",  # High-pitched, nasty
    "bugbear": "onyx",  # Deep, threatening
}
