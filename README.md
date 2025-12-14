# 🎲 AI D&D Dungeon Master

An AI-powered Dungeon Master for D&D 5th Edition with voice narration, strict rule adherence, and multi-provider AI support.

## Features

✨ **Multi-Provider AI Support**
- Anthropic Claude (best for DMing)
- OpenAI GPT-4
- Local models via Ollama
- Local models via LM Studio
- OpenRouter (access to many models)

🎤 **Voice-to-Voice Gameplay**
- Text-to-speech narration with multiple voices
- NPC-specific voice presets
- Audio caching for performance

🎮 **Strict D&D 5e Rules**
- Actual dice rolling (no hallucination)
- Tool-based combat, skill checks, saves
- Real-time character sheet updates
- Initiative tracking and combat management

🌐 **Modern Web Interface**
- React + TypeScript + Vite
- Beautiful UI with shadcn/ui components
- Real-time game state via WebSocket
- Voice chat support (optional)

## Architecture

```
┌──────────────────┐
│   Web Frontend   │  React + TypeScript
│  (Voice Input)   │  Shadcn/ui components
└────────┬─────────┘
         │ HTTP/WebSocket
┌────────┴─────────┐
│   FastAPI Server │  Python async backend
│                  │
│  ┌────────────┐  │
│  │ DM Agent   │  │  AI with tool calling
│  │ (AI Brain) │  │  Follows .cursorrules
│  └────────────┘  │
│                  │
│  ┌────────────┐  │
│  │Game Engine │  │  D&D 5e mechanics
│  │(Pure Rules)│  │  Dice, combat, skills
│  └────────────┘  │
│                  │
│  ┌────────────┐  │
│  │TTS Service │  │  Voice narration
│  │(OpenAI API)│  │  Audio caching
│  └────────────┘  │
└──────────────────┘
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- API key for your chosen AI provider
- OpenAI API key (for TTS)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp ../.env.example ../.env
# Edit .env with your API keys
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# The frontend will proxy to backend at localhost:8000
```

### Configuration

Edit `.env` in the root directory:

```env
# Choose your AI provider
AI_PROVIDER=anthropic  # or: openai, ollama, lm_studio, openrouter

# Select model
AI_MODEL=claude-3-5-sonnet-20241022

# Add your API keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

## Running the Application

### Start Backend

```bash
cd backend
source venv/bin/activate
python main.py
```

Server starts on http://localhost:8000

### Start Frontend

```bash
cd frontend
npm run dev
```

Frontend starts on http://localhost:5173

### Open in Browser

Navigate to http://localhost:5173

## AI Provider Options

### Anthropic Claude (Recommended)

**Best for:** DMing quality, rule adherence, creativity

```env
AI_PROVIDER=anthropic
AI_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-...
```

**Cost:** ~$5-10 per 4-hour session

**Recommended models:**
- `claude-3-5-sonnet-20241022` - Best balance
- `claude-3-opus-20240229` - Most creative
- `claude-3-haiku-20240307` - Fastest/cheapest

### OpenAI GPT

**Best for:** Fast responses, familiar interface

```env
AI_PROVIDER=openai
AI_MODEL=gpt-4-turbo-preview
OPENAI_API_KEY=sk-...
```

**Cost:** ~$8-15 per 4-hour session

### Ollama (Local, Free)

**Best for:** Privacy, no API costs, offline play

#### Quick Setup

```bash
# Run the setup script (Intel Mac optimized)
./setup_local_ai_intel_mac.sh
```

Or manually:

```bash
# Install Ollama (Mac)
brew install ollama
# Or download from https://ollama.com/download/mac

# Start Ollama server
ollama serve

# Pull a model (Intel Mac recommendations)
ollama pull phi3:mini        # Fastest on Intel (4-8 sec/100 tokens)
# OR
ollama pull llama3.1:8b      # Better quality, slower (8-15 sec/100 tokens)
```

```env
AI_PROVIDER=ollama
AI_MODEL=phi3:mini  # or llama3.1:8b for better quality
OLLAMA_BASE_URL=http://localhost:11434
```

**Cost:** Free (runs on your CPU/GPU)

**Intel Mac Performance:**
- `phi3:mini`: 4-8 seconds per 100 tokens (recommended for speed)
- `llama3.1:8b`: 8-15 seconds per 100 tokens (better quality)
- `mistral:7b-instruct`: 6-12 seconds per 100 tokens (balanced)

**Note:** Intel Macs are slower than Apple Silicon. If responses are too slow, consider using a cloud API (Anthropic/OpenAI) instead.

### LM Studio (Local, Free)

**Best for:** Local models with OpenAI-compatible API

1. Download [LM Studio](https://lmstudio.ai/)
2. Load a model (e.g., Mistral 7B)
3. Start local server on port 1234

```env
AI_PROVIDER=lm_studio
AI_MODEL=local-model
LM_STUDIO_BASE_URL=http://localhost:1234/v1
```

### OpenRouter

**Best for:** Access to many models with one API key

```env
AI_PROVIDER=openrouter
AI_MODEL=anthropic/claude-3.5-sonnet
OPENROUTER_API_KEY=sk-or-...
```

## Game Engine

The game engine is being ported from the original project. Current status:

- ✅ Basic dice rolling
- ✅ Skill checks with advantage/disadvantage
- ✅ Combat system (attacks, damage, HP tracking)
- ✅ Initiative tracking
- ⏳ Advanced combat features (conditions, spells, etc.)
- ⏳ Encounter system
- ⏳ Campaign management

### Porting Game Engine

To port the complete game engine from your existing project:

```bash
# Copy files from old project
cp -r ../dnd-campaign\ test/game_engine/*.py game_engine/
cp -r ../dnd-campaign\ test/dice/*.py game_engine/

# Copy character/encounter data
cp -r ../dnd-campaign\ test/characters/*.json data/characters/
cp -r ../dnd-campaign\ test/npcs/*.json data/npcs/
cp -r ../dnd-campaign\ test/adventures/ data/campaigns/

# Copy DM rules
cp ../dnd-campaign\ test/.cursorrules backend/prompts/dm_system_prompt.txt
```

## Project Structure

```
dnd-ai-dm/
├── backend/               # FastAPI server
│   ├── main.py           # Entry point
│   ├── services/         # Business logic
│   │   ├── dm_agent.py   # AI DM with tool calling
│   │   ├── anthropic_client.py
│   │   ├── openai_client.py
│   │   ├── ollama_client.py
│   │   ├── ai_factory.py # Provider selection
│   │   └── tts_service.py
│   ├── routers/          # API routes
│   ├── models/           # Data models
│   ├── config/           # Configuration
│   └── prompts/          # DM personality
│
├── frontend/             # React app
│   ├── src/
│   │   ├── components/   # UI components
│   │   ├── services/     # API client
│   │   ├── hooks/        # React hooks
│   │   └── lib/          # Utilities
│   └── package.json
│
├── game_engine/          # D&D 5e mechanics
│   └── engine.py         # Core game logic
│
├── data/                 # Game data
│   ├── characters/       # Character sheets (JSON)
│   ├── npcs/             # NPC data
│   ├── encounters/       # Encounter definitions
│   └── campaigns/        # Campaign data
│
└── .env                  # Configuration
```

## Development

### Adding New AI Providers

1. Create client in `backend/services/your_provider_client.py`
2. Extend `BaseAIClient` abstract class
3. Add to `AIProvider` enum in `config/ai_providers.py`
4. Update factory in `services/ai_factory.py`

### Adding New Tools for the AI

Edit `backend/services/dm_agent.py` and add to `_define_tools()`:

```python
ToolDefinition(
    name="your_tool",
    description="What this tool does",
    input_schema={
        "type": "object",
        "properties": {
            "param": {"type": "string"}
        },
        "required": ["param"]
    }
)
```

Then implement in `_execute_tool()`.

## API Endpoints

- `POST /api/action` - Player takes action
- `GET /api/game-state` - Get current game state
- `GET /api/characters` - List all characters
- `GET /api/characters/{name}` - Get character details
- `GET /api/audio/{filename}` - Stream TTS audio
- `POST /api/reset` - Reset conversation
- `GET /api/config/providers` - List available AI providers
- `WS /ws/game` - WebSocket for real-time updates

## Performance

### Why This Is Fast

- **No terminal spawning:** Backend runs continuously
- **No subprocess audio:** Web Audio API in browser
- **Tool calling:** AI directly executes game mechanics
- **Caching:** TTS responses cached, API results memoized
- **Async:** Non-blocking I/O throughout

### Benchmarks

- Player action → DM response: **1-3 seconds**
- TTS generation (cached): **<100ms**
- Combat round (3 attacks): **2-4 seconds**

Compare to original Cursor architecture: **6-10 seconds per action**

## Cost Comparison

| Provider | 4-Hour Session | Notes |
|----------|----------------|-------|
| Claude Sonnet | $5-10 | Recommended |
| Claude Opus | $15-25 | Most creative |
| GPT-4 Turbo | $8-15 | Fast |
| Ollama | $0 | Local, free |
| LM Studio | $0 | Local, free |

TTS (OpenAI): ~$1-2 per session

## Troubleshooting

### Backend won't start

- Check Python version: `python --version` (need 3.11+)
- Activate venv: `source venv/bin/activate`
- Check `.env` file exists and has API keys

### Frontend can't connect

- Ensure backend is running on port 8000
- Check browser console for errors
- Verify proxy settings in `vite.config.ts`

### AI not following rules

- Check `backend/prompts/dm_system_prompt.txt` is loaded
- Verify tools are defined in `dm_agent.py`
- Try a different model (Claude Opus is best)

### TTS not working

- Verify `OPENAI_API_KEY` in `.env`
- Check audio files in `audio_cache/` directory
- Try disabling voice in UI and re-enabling

## Contributing

This is a personal project, but feel free to:
- Fork and modify for your own campaigns
- Report bugs or issues
- Suggest new AI providers or features

## License

MIT License - Use however you want!

## Credits

- Based on original Cursor-based D&D campaign
- Uses Claude AI for DM intelligence
- OpenAI TTS for voice narration
- shadcn/ui for beautiful components

---

**Have fun adventuring!** 🗡️🛡️🎲
