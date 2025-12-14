# GPT-DnD

AI-powered Dungeon Master for D&D 5th Edition. Uses Anthropic Claude (or other AI providers) to run D&D campaigns with voice narration and strict rule adherence.

## Installation

### Prerequisites

- Python 3.11+
- Node.js 18+
- API key for your chosen AI provider (Anthropic recommended)
- OpenAI API key (for text-to-speech)

### Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend Setup

```bash
cd frontend
npm install
```

### Configuration

Create a `.env` file in the project root:

```env
AI_PROVIDER=anthropic
AI_MODEL=claude-3-5-haiku-20241022
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
ENABLE_PROMPT_CACHING=true
```

## Running

### Start Backend

```bash
cd backend
source venv/bin/activate
python3 main.py
```

Server runs on http://localhost:8000

### Start Frontend

```bash
cd frontend
npm run dev
```

Frontend runs on http://localhost:5173

## Features

- Multi-provider AI support (Anthropic, OpenAI, Ollama, LM Studio)
- D&D 5e game mechanics (dice rolling, combat, skill checks)
- Voice narration with TTS
- Save points and chat archiving
- Editable DM prompts and campaign rules

## Project Structure

```
backend/          # FastAPI server
frontend/          # React + TypeScript UI
game_engine/       # D&D 5e mechanics
data/              # Characters, NPCs, adventures
```

## License

See LICENSE file for details.
