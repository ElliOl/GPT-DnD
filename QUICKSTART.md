# Quick Start Guide

Get up and running in 5 minutes!

## Step 1: Clone and Setup Backend

```bash
cd dnd-ai-dm/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configure API Keys

```bash
# Copy template
cp .env.example .env

# Edit .env and add your keys
# At minimum, you need:
# - ANTHROPIC_API_KEY or OPENAI_API_KEY (for AI)
# - OPENAI_API_KEY (for TTS)
```

Get API keys:
- Anthropic: https://console.anthropic.com/
- OpenAI: https://platform.openai.com/api-keys

## Step 3: Start Backend

```bash
cd backend
python main.py
```

You should see:
```
🎲 Initializing AI Dungeon Master...
✅ Game engine loaded
✅ TTS service initialized
✅ AI client initialized: anthropic
✅ DM Agent ready
🎭 The Dungeon Master awaits...
📡 Server starting on http://localhost:8000
```

## Step 4: Setup Frontend

Open a NEW terminal:

```bash
cd dnd-ai-dm/frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

## Step 5: Play!

Open your browser to: http://localhost:5173

Try saying:
- "I want to start a new adventure"
- "I search the room for clues"
- "I attack the goblin with my sword"

## Using Different AI Providers

### Use Local Ollama (Free)

```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull a model
ollama pull llama2

# In .env
AI_PROVIDER=ollama
AI_MODEL=llama2
```

### Use LM Studio (Free)

1. Download LM Studio: https://lmstudio.ai/
2. Load a model (try Mistral 7B)
3. Start server (default port 1234)

```env
AI_PROVIDER=lm_studio
AI_MODEL=local-model
```

### Use GPT-4

```env
AI_PROVIDER=openai
AI_MODEL=gpt-4-turbo-preview
OPENAI_API_KEY=sk-...
```

## Adding Characters

Create a file in `data/characters/yourname.json`:

```json
{
  "name": "Thorin Ironforge",
  "race": "Dwarf",
  "char_class": "Fighter",
  "level": 3,
  "max_hp": 28,
  "current_hp": 28,
  "armor_class": 16,
  "abilities": {
    "STR": 16,
    "DEX": 12,
    "CON": 15,
    "INT": 10,
    "WIS": 13,
    "CHA": 8
  },
  "proficiency_bonus": 2,
  "skills": {
    "Athletics": true,
    "Intimidation": true,
    "Perception": true
  },
  "inventory": ["Battleaxe", "Chain mail", "Shield", "50 gold"]
}
```

Restart the backend to load new characters.

## Troubleshooting

### "Module not found" errors

```bash
# Make sure venv is activated
source venv/bin/activate
pip install -r requirements.txt
```

### "Connection refused" in frontend

- Check backend is running on port 8000
- Check console for errors: `python main.py`

### No audio playing

- Check `OPENAI_API_KEY` is set for TTS
- Enable voice toggle in UI
- Check browser console for errors

### AI responses are slow

- Try switching to `claude-3-haiku` for faster responses
- Or use local Ollama (instant, but lower quality)

### "Invalid API key"

- Double-check `.env` file
- Make sure no extra spaces around `=`
- Restart backend after changing `.env`

## Next Steps

- [ ] Port your existing game engine from old project
- [ ] Add your campaign data to `data/campaigns/`
- [ ] Customize DM personality in `backend/prompts/dm_system_prompt.txt`
- [ ] Add voice input support (Web Speech API)
- [ ] Build combat tracker UI component
- [ ] Add dice roller visualization

## Need Help?

Check the full [README.md](README.md) for detailed documentation.
